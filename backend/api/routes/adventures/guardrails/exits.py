"""Exit unlock guard: locked exits open only when their requirements are met."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, or_, select

from backend.api.routes.adventures.guardrails.locks import LockSpec
from backend.engine.rules.rule_engine import ExitUpdate, GameEvent
from backend.models.world_entity import WorldExit

_CODE_FAILURE = "{name} answers with a cold red blink. That code won't open the way."


@dataclass
class SceneExit:
    """An exit as seen from the current scene (bidirectional exits may be stored reversed)."""

    row: WorldExit
    from_scene_id: str
    to_scene_id: str

    def matches(self, update: ExitUpdate) -> bool:
        return update.from_scene_id == self.from_scene_id and update.to_scene_id == self.to_scene_id


class ExitGuardMixin:
    """Validates GM unlocks and traversals of locked exits."""

    async def _scene_exits(self) -> list[SceneExit]:
        current = self.state.current_scene_id
        res = await self.db.execute(
            select(WorldExit).where(
                WorldExit.session_id == self.game_id,
                or_(
                    WorldExit.from_scene_id == current,
                    and_(WorldExit.to_scene_id == current, WorldExit.exit_type == "bidirectional"),
                ),
            )
        )
        exits = []
        for row in res.scalars().all():
            forward = row.from_scene_id == current
            exits.append(
                SceneExit(
                    row=row,
                    from_scene_id=row.from_scene_id if forward else row.to_scene_id,
                    to_scene_id=row.to_scene_id if forward else row.from_scene_id,
                )
            )
        return exits

    @staticmethod
    def _exit_spec(scene_exit: SceneExit, being_unlocked: bool) -> LockSpec:
        row = scene_exit.row
        return LockSpec(
            script_target_id=str(row.id),
            name=row.label,
            code=str(row.code_to_unlock or "").strip(),
            item_id=str(row.item_to_unlock or "").strip().upper(),
            rule=str(row.rule_to_unlock or "").strip(),
            expression=str(row.unlock_expression or "").strip(),
            failure_script=str(row.on_unlock_failure_script or ""),
            failure_text=str(row.on_unlock_failure_text or ""),
            being_unlocked=being_unlocked,
            explicit_unlock_required=False,
            rule_uses_switch_flags=False,
            code_failure_text=_CODE_FAILURE.format(name=row.label),
            rule_failure_text=f"{row.label} is locked.",
        )

    @staticmethod
    def _set_exit_lock(event: GameEvent, scene_exit: SceneExit, locked: bool) -> None:
        updates = [up for up in event.updated_exits or [] if not scene_exit.matches(up)]
        updates.append(
            ExitUpdate(
                from_scene_id=scene_exit.from_scene_id,
                to_scene_id=scene_exit.to_scene_id,
                is_locked=locked,
            )
        )
        event.updated_exits = updates

    def _block_exit(self, event: GameEvent, scene_exit: SceneExit) -> None:
        self._set_exit_lock(event, scene_exit, locked=True)
        if event.new_scene_id == scene_exit.to_scene_id:
            event.new_scene_id = None
            event.exit_label = None
            event.scene_label = None
        self._revoke_turn_rewards(event)

    async def _guard_exit(
        self, event: GameEvent, lowered: str, scene_exit: SceneExit
    ) -> str | None:
        if not scene_exit.row.is_locked:
            return None
        being_unlocked = any(
            scene_exit.matches(up) and not up.is_locked for up in event.updated_exits or []
        )
        if not being_unlocked and event.new_scene_id != scene_exit.to_scene_id:
            return None

        spec = self._exit_spec(scene_exit, being_unlocked)
        reason = await self._lock_failure(spec, lowered, set())
        if reason is None:
            # Requirements met: persist the unlock so the exit stays open.
            self._set_exit_lock(event, scene_exit, locked=False)
            return None
        self._block_exit(event, scene_exit)
        return await self._run_lock_failure_hooks(spec, reason)

    async def _enforce_exit_unlock_guardrails(self, event: GameEvent, user_msg: str) -> list[str]:
        """Blocks traversal/unlock of locked exits whose code, key item, rule or guard is not satisfied."""
        lowered = (user_msg or "").strip().lower()
        if not lowered:
            return []
        reasons: list[str] = []
        for scene_exit in await self._scene_exits():
            reason = await self._guard_exit(event, lowered, scene_exit)
            if reason is not None:
                reasons.append(reason)
        return reasons
