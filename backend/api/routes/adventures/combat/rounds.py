"""Initiative order, round progression and encounter outcomes."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from backend.api.routes.adventures.combat.context import (
    engaged_enemies,
    find_enemy,
    system_event,
)
from backend.engine.combat.initiative import PLAYER_ID, describe_initiative, roll_initiative
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)

MAX_TURN_STEPS = 64
LOOT_HINT = "Victory! Loot available. Use /loot take <item>, /loot leave <item>, /loot done"


class CombatRoundMixin:
    """Keeps the initiative order moving and detects victory or defeat."""

    def _initiative_participants(self, combat: dict[str, Any]) -> list[dict[str, Any]]:
        player = combat.get("player") or {}
        player_dex = int((player.get("stats") or {}).get("dexterity", self.avatar.dexterity or 0))
        player_dex += int((player.get("modifiers") or {}).get("dexterity", 0))
        participants = [{"id": PLAYER_ID, "name": self.avatar.name, "dexterity": player_dex}]
        for enemy in engaged_enemies(combat):
            dex = int(enemy.get("dexterity_mod") or 0) + int(
                (enemy.get("modifiers") or {}).get("dexterity", 0)
            )
            participants.append({"id": enemy["id"], "name": enemy["name"], "dexterity": dex})
        return participants

    def _roll_round_initiative(self, combat: dict[str, Any]) -> None:
        order = roll_initiative(self._initiative_participants(combat))
        combat["initiative"] = order
        combat["turn_index"] = 0
        round_no = int(combat.get("round") or 1)
        self._append_combat_log(
            combat,
            describe_initiative(order, round_no),
            "initiative",
            {"kind": "initiative", "round": round_no, "order": order},
        )

    @staticmethod
    def _current_actor_id(combat: dict[str, Any]) -> str | None:
        order = combat.get("initiative") or []
        idx = int(combat.get("turn_index") or 0)
        return order[idx]["id"] if 0 <= idx < len(order) else None

    def _set_turn_marker(self, combat: dict[str, Any]) -> None:
        actor = self._current_actor_id(combat)
        combat["active_actor"] = actor
        combat["turn"] = "player" if actor == PLAYER_ID else "enemy"

    def _enemy_can_act(self, combat: dict[str, Any], actor_id: str | None) -> bool:
        enemy = find_enemy(combat, actor_id)
        return bool(enemy and enemy in engaged_enemies(combat))

    async def _advance_until_player(
        self, combat: dict[str, Any], skip_current: bool
    ) -> AsyncGenerator[str, None]:
        """Walks the initiative order, resolving NPC turns until the player acts or combat ends."""
        if skip_current:
            combat["turn_index"] = int(combat.get("turn_index") or 0) + 1

        for _ in range(MAX_TURN_STEPS):
            if not combat.get("active"):
                break
            if int(combat.get("turn_index") or 0) >= len(combat.get("initiative") or []):
                await self._maybe_round_banter(combat)
                combat["round"] = int(combat.get("round") or 1) + 1
                self._roll_round_initiative(combat)
                continue
            actor = self._current_actor_id(combat)
            if actor == PLAYER_ID:
                self._announce_player_turn(combat)
                break
            if self._enemy_can_act(combat, actor):
                self._set_turn_marker(combat)
                async for chunk in self._resolve_enemy_turn(actor, combat):
                    yield chunk
            combat["turn_index"] = int(combat.get("turn_index") or 0) + 1

        self._set_turn_marker(combat)
        self._set_combat_state(combat)

    def _announce_player_turn(self, combat: dict[str, Any]) -> None:
        self._set_turn_marker(combat)
        text = f"Round {combat.get('round', 1)}: {self.avatar.name}'s turn."
        self._append_combat_log(combat, text, "turn", {"kind": "turn", "actor": PLAYER_ID})

    # --- Outcomes -----------------------------------------------------------------

    def _award_combat_victory_xp(self, enemy_ent: WorldEntity) -> int:
        metadata = dict(enemy_ent.metadata_json or {})
        xp_gained = metadata.get("exp_reward") or metadata.get("xp_reward")
        if xp_gained is None:
            xp_gained = max(50, enemy_ent.max_hp or 100)
        self.avatar.exp = (self.avatar.exp or 0) + xp_gained
        return xp_gained

    def _mark_npc_out_of_fight(self, enemy_ent: WorldEntity) -> None:
        values: dict[str, Any] = {"inventory": []}
        if self._is_npc_killable(enemy_ent):
            # Permanently defeated NPCs cannot be re-engaged.
            values.update(is_defeated=True, is_attackable=False)
        self._update_entity_state(enemy_ent.id, **values)

    async def _run_defeat_script(self, enemy_ent: WorldEntity) -> list[str]:
        meta = dict(enemy_ent.metadata_json or {})
        messages: list[str] = []
        script = meta.get("on_defeat_script")
        if script:
            try:
                messages.extend(
                    await self.manager._execute_inline_script(script, "on_defeat", enemy_ent.id)
                    or []
                )
            except Exception as exc:
                logger.warning("[Turn %s] on_defeat script failed: %s", self.game_id, exc)
        if meta.get("on_defeat_text"):
            messages.append(str(meta["on_defeat_text"]))
        return messages

    async def _on_enemy_out(
        self, combat: dict[str, Any], enemy: dict[str, Any], fled: bool
    ) -> AsyncGenerator[str, None]:
        """Handles an NPC that was defeated or fled: XP, loot, scripts and messages."""
        enemy_ent = await self._load_session_entity(enemy["id"])
        enemy["defeated" if not fled else "fled"] = True
        if not enemy_ent:
            return

        xp_gained = self._award_combat_victory_xp(enemy_ent)
        combat["xp_gained"] = int(combat.get("xp_gained") or 0) + xp_gained
        loot = await self._normalize_loot_items(
            list(enemy.get("inventory") or enemy_ent.inventory or [])
        )
        enemy["inventory"] = []
        if fled:
            for item in loot:
                await self._spawn_scene_item(item)
        else:
            combat["loot_items"] = [*list(combat.get("loot_items") or []), *loot]
        self._mark_npc_out_of_fight(enemy_ent)

        verb = "flees in panic" if fled else "is defeated"
        self._append_combat_log(
            combat,
            f"{enemy['name']} {verb}. (+{xp_gained} XP)",
            "outcome",
            {"kind": "fled" if fled else "defeat", "entity": enemy["id"], "xp": xp_gained},
        )
        messages = [f"Defeated {enemy['name']}!", f"you gained {xp_gained} XP"]
        messages.extend(await self._run_defeat_script(enemy_ent))
        for msg in messages:
            await self._save_chat_message("system", msg)
            yield system_event(msg)

    def _check_victory(self, combat: dict[str, Any]) -> bool:
        if engaged_enemies(combat):
            return False
        out = [e for e in combat.get("enemies") or [] if e.get("defeated") or e.get("fled")]
        names = ", ".join(e["name"] for e in out) or "The enemy"
        xp = int(combat.get("xp_gained") or 0)
        combat["active"] = False
        combat["outcome"] = "victory"
        combat["loot_pending"] = True
        combat["turn"] = "player"
        if len(out) == 1:
            verb = "flees in panic! You won the battle." if out[0].get("fled") else "is defeated."
            combat["status_note"] = f"{names} {verb} (+{xp} XP)"
        else:
            combat["status_note"] = f"All enemies have been overcome: {names}. (+{xp} XP)"
        self._append_combat_log(combat, combat["status_note"], "outcome", {"kind": "victory"})
        if combat.get("loot_items"):
            self._append_combat_log(combat, LOOT_HINT, "loot")
        return True

    async def _handle_player_defeat(
        self, combat: dict[str, Any], note: str, log_outcome: bool = True
    ) -> None:
        await self._finalize_session("game_over", f"{self.avatar.name} has fallen in battle.")
        self._sync_combat_player_snapshot(combat)
        combat["active"] = False
        combat["outcome"] = "defeat"
        combat["status_note"] = "Game Over" if log_outcome else note
        if log_outcome:
            self._append_combat_log(combat, note, "outcome", {"kind": "game_over"})
        self._set_combat_state(combat)
