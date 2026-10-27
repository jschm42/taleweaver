"""Reading items (on_read hooks) and the legacy READ_ITEM / FIND_ITEM special-action unlocks."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.combat.unlocks import unlock_message
from backend.models.world_entity import WorldEntity


def _is_readable(item: dict[str, Any], meta: dict[str, Any]) -> bool:
    item_type = str(item.get("item_type") or meta.get("item_type") or "").upper()
    return item_type == "READABLE" or bool(
        item.get("text_log_content") or meta.get("text_log_content")
    )


class ReadingMixin:
    """Runs read hooks and unlocks special actions tied to reading or finding items."""

    def _mark_read(self, item_id: str) -> bool:
        """Records the item as read; returns whether it had been read before."""
        if not item_id:
            return False
        states = dict(self.state.entity_states or {})
        entry = dict(states.get(item_id) or {})
        already_read = bool(entry.get("is_read"))
        entry["is_read"] = True
        states[item_id] = entry
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")
        return already_read

    async def _execute_read_payload(
        self, item_id: str, script: str | None, text: str | None
    ) -> None:
        # Read hooks fire on the first read only (shared with the text viewer's read endpoint).
        if not self._mark_read(item_id):
            await self._run_read_hooks(item_id, script, text)
        await self._check_special_action_unlocks("READ_ITEM", item_id)

    async def _run_read_hooks(self, item_id: str, script: str | None, text: str | None) -> None:
        if script:
            await self.manager._execute_inline_script(script, "on_read", item_id)
        if text:
            await self._save_chat_message("system", text)

    async def _read_from_inventory(self, target_lower: str) -> bool:
        for item in self.avatar.inventory or []:
            if not isinstance(item, dict):
                continue
            if target_lower not in (
                (item.get("name") or "").lower(),
                (item.get("id") or "").lower(),
            ):
                continue
            meta = item.get("metadata_json") if isinstance(item.get("metadata_json"), dict) else {}
            if _is_readable(item, meta):
                script = item.get("on_read_script") or meta.get("on_read_script")
                text = item.get("on_read_text") or meta.get("on_read_text")
                await self._execute_read_payload(item.get("id"), script, text)
                return True
        return False

    async def _handle_read_action_unlock(self, read_target: str) -> None:
        """Runs the read hooks of the item being read (inventory first, then the scene)."""
        target_lower = read_target.strip().lower()
        if await self._read_from_inventory(target_lower):
            return
        res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type == "OBJECT",
                WorldEntity.is_hidden.is_(False),
                WorldEntity.item_type == "READABLE",
            )
        )
        candidate = next(
            (
                c
                for c in res.scalars().all()
                if target_lower in ((c.id or "").lower(), (c.name or "").lower())
            ),
            None,
        )
        if candidate:
            meta = dict(candidate.metadata_json or {})
            await self._execute_read_payload(
                candidate.id, meta.get("on_read_script"), meta.get("on_read_text")
            )

    async def _check_special_action_unlocks(self, condition_type: str, target_id: str) -> None:
        """Unlocks special actions whose legacy READ_ITEM/FIND_ITEM condition targets this item."""
        if not target_id:
            return
        stats = dict(self.avatar.stats or {})
        unlocked = list(stats.get("unlocked_actions") or [])
        newly = [
            action
            for action in stats.get("special_actions") or []
            if action.get("id") not in unlocked
            and action.get("is_locked", False)
            and action.get("unlock_condition_type") == condition_type
            and action.get("unlock_condition_target") == target_id
        ]
        if not newly:
            return
        for action in newly:
            unlocked.append(action.get("id"))
            await self._save_chat_message("system", unlock_message(action))
        stats["unlocked_actions"] = unlocked
        self.avatar.stats = stats
        flag_modified(self.avatar, "stats")
        await self.db.commit()
