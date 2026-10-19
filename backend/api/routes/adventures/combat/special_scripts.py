"""Optional success/failure scripts and texts attached to special attacks."""

from __future__ import annotations

import logging
from typing import Any

from backend.api.routes.adventures.combat.context import system_event
from backend.engine.combat.initiative import PLAYER_ID

logger = logging.getLogger(__name__)


class CombatSpecialScriptMixin:
    """Runs ``on_success_*`` / ``on_failure_*`` hooks after a special attack resolves."""

    async def _raw_special(self, actor_id: str, action_id: str) -> dict[str, Any]:
        """Looks up the stored definition (normalized copies do not carry scripts)."""
        if actor_id == PLAYER_ID:
            source = (self.avatar.stats or {}).get("special_actions") or []
        else:
            npc = await self._load_session_entity(actor_id)
            meta = npc.metadata_json if npc and isinstance(npc.metadata_json, dict) else {}
            source = meta.get("special_actions") or []
        return next((a for a in source if isinstance(a, dict) and a.get("id") == action_id), {})

    def _refresh_combatants_from_state(self, combat: dict[str, Any]) -> None:
        """Pulls script-made HP changes (avatar and NPC overrides) back into the fight."""
        self._sync_combat_player_snapshot(combat)
        states = self.state.entity_states or {}
        for enemy in combat.get("enemies") or []:
            override = states.get(enemy["id"]) or {}
            if isinstance(override.get("hp"), int):
                enemy["hp"] = override["hp"]
            if override.get("is_defeated"):
                enemy["hp"] = 0

    async def _run_special_scripts(
        self, combat: dict[str, Any], result: dict[str, Any]
    ) -> list[str]:
        actor_id = str(result.get("actor") or "")
        action = await self._raw_special(actor_id, str(result.get("action_id") or ""))
        prefix = "on_success" if result.get("success") else "on_failure"
        script = str(action.get(f"{prefix}_script") or "").strip()
        text = str(action.get(f"{prefix}_text") or "").strip()
        messages = [text] if text else []
        if script:
            scope = {
                "special": {
                    "id": result.get("action_id"),
                    "name": result.get("action_name"),
                    "caster": actor_id,
                    "target": result.get("target"),
                    "success": bool(result.get("success")),
                    "crit": bool(result.get("crit")),
                    "fumble": bool(result.get("fumble")),
                    "roll": result.get("total"),
                    "dc": result.get("dc"),
                }
            }
            try:
                messages.extend(
                    await self.manager._execute_inline_script(
                        script, f"special_{prefix}", str(result.get("action_id")), extra_scope=scope
                    )
                )
            except Exception:
                logger.exception("[Turn %s] Special attack script failed", self.game_id)
            self._refresh_combatants_from_state(combat)

        for msg in messages:
            self._append_combat_log(combat, msg, "special")
            await self._save_chat_message("system", msg)
        return messages

    async def _special_script_events(self, combat: dict[str, Any], result: dict[str, Any]):
        for msg in await self._run_special_scripts(combat, result):
            yield system_event(msg)
