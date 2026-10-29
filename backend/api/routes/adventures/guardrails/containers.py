"""Container lock state, free-text container lookup and the container unlock guard."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select

from backend.api.routes.adventures.guardrails.locks import LockSpec
from backend.engine.rules.rule_engine import GameEvent, WorldEntityUpdate
from backend.models.world_entity import WorldEntity

_REQUIREMENT_KEYS = ("code_to_unlock", "item_to_unlock", "rule_to_unlock")
_RULE_FAILURE = "{name} stays shut. The moment does not feel right yet. A different approach might open a window."
_CODE_FAILURE = "{name} gives a mocking click. That code won't do the trick."


def _requirements(metadata: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(metadata.get("code_to_unlock") or "").strip(),
        str(metadata.get("item_to_unlock") or "").strip().upper(),
        str(metadata.get("rule_to_unlock") or "").strip(),
    )


def _metadata_of(container: Any) -> dict[str, Any]:
    if isinstance(container, dict):
        meta = container.get("metadata_json")
    else:
        meta = getattr(container, "metadata_json", None)
    return dict(meta) if isinstance(meta, dict) else {}


class ContainerGuardMixin:
    """Locked containers only open when every configured requirement is met."""

    @staticmethod
    def _is_container_item(item: Any) -> bool:
        return isinstance(item, dict) and str(item.get("item_type") or "").upper() == "CONTAINER"

    def _is_container_locked(
        self, scene_container: WorldEntity | None, inventory_container: dict[str, Any] | None
    ) -> bool:
        states = self.state.entity_states or {}
        container: Any = scene_container if scene_container is not None else inventory_container
        if container is None:
            return False
        container_id = (
            scene_container.id
            if scene_container is not None
            else str(inventory_container.get("id") or "").strip()
        )
        state_locked = (states.get(container_id) or {}).get("locked") if container_id else None
        if isinstance(state_locked, bool):
            return state_locked
        item_locked = inventory_container.get("locked") if inventory_container is not None else None
        if scene_container is None and isinstance(item_locked, bool):
            return item_locked
        return any(_requirements(_metadata_of(container)))

    @staticmethod
    def _extract_access_code(text: str) -> str | None:
        if not text:
            return None
        quoted = re.search(r"[\"']([A-Za-z0-9]{1,32})[\"']", text)
        if quoted:
            return quoted.group(1)
        match = re.search(r"\b(\d{3,8})\b", text)
        return match.group(1) if match else None

    async def _scene_containers(self, only_visible_here: bool) -> list[WorldEntity]:
        conditions = [
            WorldEntity.session_id == self.game_id,
            WorldEntity.entity_type == "OBJECT",
            WorldEntity.item_type == "CONTAINER",
        ]
        if only_visible_here:
            conditions += [
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(False),
            ]
        res = await self.db.execute(select(WorldEntity).where(*conditions))
        return list(res.scalars().all())

    def _container_candidates(self, scene: list[WorldEntity]) -> list[tuple[str, str, Any, bool]]:
        """Returns (id, name, container, is_scene) for scene containers and carried containers."""
        candidates: list[tuple[str, str, Any, bool]] = [
            (str(ent.id or ""), str(ent.name or ""), ent, True) for ent in scene
        ]
        for item in self.avatar.inventory or []:
            if self._is_container_item(item):
                candidates.append(
                    (
                        str(item.get("id") or "").strip(),
                        str(item.get("name") or "").strip(),
                        item,
                        False,
                    )
                )
        return candidates

    async def _resolve_container_from_free_text(
        self, text: str
    ) -> tuple[str, str, str, str, str, bool] | None:
        """Finds the container whose ID or name appears in the text (longest match wins)."""
        lowered = (text or "").strip().lower()
        if not lowered:
            return None
        best: tuple[int, tuple[str, str, str, str, str, bool]] | None = None
        for cid, cname, container, is_scene in self._container_candidates(
            await self._scene_containers(True)
        ):
            token = next((t for t in (cid.lower(), cname.lower()) if t and t in lowered), None)
            if not token:
                continue
            locked = (
                self._is_container_locked(container, None)
                if is_scene
                else self._is_container_locked(None, container)
            )
            code, item, rule = _requirements(_metadata_of(container))
            resolved_id = cid if is_scene else (cid or cname)
            resolved_name = cname or cid or ("" if is_scene else "container")
            if best is None or len(token) > best[0]:
                best = (len(token), (resolved_id, resolved_name, code, item, rule, locked))
        return best[1] if best else None

    def _container_spec(
        self, container: Any, cid: str, name: str, being_unlocked: bool
    ) -> LockSpec:
        metadata = _metadata_of(container)
        code, item, rule = _requirements(metadata)
        return LockSpec(
            script_target_id=cid,
            name=name,
            code=code,
            item_id=item,
            rule=rule,
            expression=str(metadata.get("unlock_expression") or "").strip(),
            failure_script=str(metadata.get("on_unlock_failure_script") or ""),
            failure_text=str(metadata.get("on_unlock_failure_text") or ""),
            being_unlocked=being_unlocked,
            explicit_unlock_required=True,
            rule_uses_switch_flags=True,
            code_failure_text=_CODE_FAILURE.format(name=name),
            rule_failure_text=_RULE_FAILURE.format(name=name),
        )

    @staticmethod
    def _force_container_locked(event: GameEvent, container_id: str) -> None:
        updates = [
            up
            for up in event.updated_entities or []
            if not (up.entity_id == container_id and up.locked is False)
        ]
        updates.append(WorldEntityUpdate(entity_id=container_id, locked=True))
        event.updated_entities = updates

    async def _guard_container(
        self,
        event: GameEvent,
        lowered: str,
        entry: tuple[str, str, Any, bool],
        switch_flags: set[str],
    ) -> str | None:
        cid, cname, container, is_scene = entry
        if not cid:
            return None
        locked = (
            self._is_container_locked(container, None)
            if is_scene
            else self._is_container_locked(None, container)
        )
        if not locked:
            return None
        being_unlocked = any(
            up.entity_id == cid and up.locked is False for up in event.updated_entities or []
        )
        mentioned = any(tok and tok in lowered for tok in (cid.lower(), cname.lower()))
        if not being_unlocked and not mentioned:
            return None

        spec = self._container_spec(
            container, cid, cname or ("Container" if not is_scene else cid), being_unlocked
        )
        reason = await self._lock_failure(spec, lowered, switch_flags)
        if reason is None:
            return None
        self._force_container_locked(event, cid)
        self._revoke_turn_rewards(event)
        return await self._run_lock_failure_hooks(spec, reason)

    async def _enforce_container_unlock_guardrails(
        self, event: GameEvent, user_msg: str
    ) -> list[str]:
        """Re-locks containers the GM opened without the configured code, key item, rule or guard."""
        lowered = (user_msg or "").strip().lower()
        switch_flags = await self._get_switch_story_flags()
        reasons: list[str] = []
        for entry in self._container_candidates(await self._scene_containers(False)):
            reason = await self._guard_container(event, lowered, entry, switch_flags)
            if reason is not None:
                reasons.append(reason)
        return reasons
