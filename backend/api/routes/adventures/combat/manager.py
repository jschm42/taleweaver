"""Turn-based combat facade used by the game turn manager."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import backend.api.routes.adventures.gameplay_logic as gl
from backend.api.routes.adventures.combat.banter import CombatBanterMixin
from backend.api.routes.adventures.combat.combatants import CombatCombatantMixin
from backend.api.routes.adventures.combat.consumables import CombatConsumableMixin
from backend.api.routes.adventures.combat.context import (
    CombatContextMixin,
    engaged_enemies,
    find_enemy,
    system_event,
)
from backend.api.routes.adventures.combat.enemy_ai import CombatEnemyMixin
from backend.api.routes.adventures.combat.loot import CombatLootMixin
from backend.api.routes.adventures.combat.narration import CombatNarrationMixin
from backend.api.routes.adventures.combat.player_actions import (
    INVALID_ACTION_MSG,
    CombatPlayerMixin,
    parse_combat_command,
)
from backend.api.routes.adventures.combat.rounds import CombatRoundMixin
from backend.api.routes.adventures.combat.setup import CombatSetupMixin
from backend.api.routes.adventures.combat.special_scripts import CombatSpecialScriptMixin
from backend.api.routes.adventures.combat.triggers import CombatTriggerMixin
from backend.api.routes.adventures.combat.unlocks import CombatUnlockMixin

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

FLEE_HP_RATIO = 0.2
FLEE_CHANCE = 0.10


class TurnCombatManager(
    CombatTriggerMixin,
    CombatUnlockMixin,
    CombatSpecialScriptMixin,
    CombatSetupMixin,
    CombatPlayerMixin,
    CombatEnemyMixin,
    CombatRoundMixin,
    CombatBanterMixin,
    CombatCombatantMixin,
    CombatConsumableMixin,
    CombatLootMixin,
    CombatNarrationMixin,
    CombatContextMixin,
):
    """Manages multi-enemy encounters, initiative, special attacks and loot."""

    def __init__(self, manager: GameTurnManager) -> None:
        self.manager = manager
        self._last_consumable_deltas: dict[str, int] = {}

    async def _handle_loot_phase(
        self, user_msg: str, combat: dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        pre_resolve_outcome = combat.get("outcome")
        loot_msg = await self._resolve_loot_command(user_msg, combat)
        if not loot_msg:
            async for chunk in self._reply(
                "Loot phase active. Use /loot take, /loot leave, or /loot done."
            ):
                yield chunk
            return

        yield system_event(loot_msg)
        if user_msg.lower().strip().startswith("/loot done"):
            combat_after_loot = self._read_combat_state() or combat
            # Re-inject the outcome for narration when it was just popped.
            if not combat_after_loot.get("outcome") and pre_resolve_outcome:
                combat_after_loot["outcome"] = pre_resolve_outcome
            async for chunk in self._emit_combat_aftermath_narration(combat_after_loot):
                yield chunk
        async for chunk in self._emit_combat_final(loot_msg):
            yield chunk

    async def _resolve_casualties(
        self, combat: dict[str, Any], target_id: str | None
    ) -> AsyncGenerator[str, None]:
        """Processes defeated enemies and lets a badly wounded target flee."""
        for enemy in list(combat.get("enemies") or []):
            if (
                not enemy.get("defeated")
                and not enemy.get("fled")
                and int(enemy.get("hp") or 0) <= 0
            ):
                async for chunk in self._on_enemy_out(combat, enemy, fled=False):
                    yield chunk

        target = find_enemy(combat, target_id)
        if not target or target not in engaged_enemies(combat):
            return
        max_hp = int(target.get("max_hp") or 100)
        if (
            int(target.get("hp") or 0) <= max_hp * FLEE_HP_RATIO
            and gl.random.random() < FLEE_CHANCE
        ):
            async for chunk in self._on_enemy_out(combat, target, fled=True):
                yield chunk

    async def _finish_escape(self, combat: dict[str, Any]) -> AsyncGenerator[str, None]:
        combat["active"] = False
        combat["outcome"] = "escaped"
        combat["status_note"] = f"{self.avatar.name} escapes from combat."
        self._set_combat_state(combat)
        yield system_event(combat["status_note"])
        async for chunk in self._emit_combat_aftermath_narration(combat):
            yield chunk
        async for chunk in self._emit_combat_final(combat["status_note"]):
            yield chunk

    async def _player_turn(
        self, combat: dict[str, Any], user_msg: str
    ) -> AsyncGenerator[str, None]:
        verb, arg = parse_combat_command(user_msg)
        handler = self._player_action_handler(verb)
        result = await handler(combat, arg) if handler else {"error": INVALID_ACTION_MSG}
        if result.get("error"):
            async for chunk in self._reply(result["error"]):
                yield chunk
            return

        self._sync_combat_player_snapshot(combat)
        self._append_combat_log(combat, result["text"], result["type"], result.get("data"))
        yield system_event(result["text"])
        if (result.get("data") or {}).get("kind") == "special":
            async for chunk in self._special_script_events(combat, result["data"]):
                yield chunk
        follow_up = (
            self._finish_escape(combat)
            if result.get("escaped")
            else self._after_player_action(combat, result)
        )
        async for chunk in follow_up:
            yield chunk

    async def _after_player_action(
        self, combat: dict[str, Any], result: dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._resolve_casualties(
            combat, (result.get("data") or {}).get("target")
        ):
            yield chunk
        if self.avatar.hp <= 0:
            await self._handle_player_defeat(combat, "The protagonist falls. Game Over.")
        elif self._check_victory(combat):
            self._set_combat_state(combat)
        else:
            async for chunk in self._advance_until_player(combat, skip_current=True):
                yield chunk
        note = None if combat.get("active") else combat.get("status_note")
        async for chunk in self._emit_combat_final(note):
            yield chunk

    async def _active_combat_problem(self, combat: dict[str, Any]) -> str | None:
        if not combat.get("active"):
            return "No active combat. Use /fight to start."
        if combat.get("enemies") or await self._upgrade_legacy_combat(combat):
            return None
        combat.update(active=False, outcome="escaped", status_note="Combat closed.")
        self._set_combat_state(combat)
        return "The opponent is gone. The fight is over."

    async def _handle_combat_turn(self, user_msg: str) -> AsyncGenerator[str, None]:
        combat = self._read_combat_state()
        if not combat.get("active") and (combat.get("loot_pending") or combat.get("outcome")):
            async for chunk in self._handle_loot_phase(user_msg, combat):
                yield chunk
            return
        problem = await self._active_combat_problem(combat)
        if problem:
            async for chunk in self._reply(problem):
                yield chunk
            return
        if combat.get("turn") != "player":
            # Resume NPC turns that were interrupted (e.g. a fight restored from an old save).
            async for chunk in self._advance_until_player(combat, skip_current=False):
                yield chunk
        if not combat.get("active"):
            async for chunk in self._emit_combat_final(combat.get("status_note")):
                yield chunk
            return
        async for chunk in self._player_turn(combat, user_msg):
            yield chunk

    async def _upgrade_legacy_combat(self, combat: dict[str, Any]) -> bool:
        """Converts a saved single-enemy fight into the multi-enemy format."""
        legacy = combat.get("enemy") or {}
        npc = await self._load_session_entity(legacy.get("id"))
        if not npc:
            return False
        entry = await self._build_enemy_entry(npc, engaged=True)
        for key in ("hp", "mana", "stamina"):
            if isinstance(legacy.get(key), int):
                entry[key] = legacy[key]
        combat["enemies"] = [entry]
        combat["target_id"] = npc.id
        self._sync_combat_player_snapshot(combat)
        self._roll_round_initiative(combat)
        return True

    # --- Debug shortcuts ----------------------------------------------------------

    async def force_victory(self) -> int | None:
        """Defeats every engaged enemy (debug). Returns the XP gained or None without a fight."""
        combat = self._read_combat_state()
        if not combat.get("active") or not combat.get("enemies"):
            return None
        for enemy in engaged_enemies(combat):
            enemy["hp"] = 0
            self._persist_enemy_resources(enemy)
            async for _chunk in self._on_enemy_out(combat, enemy, fled=False):
                pass
        self._check_victory(combat)
        combat["status_note"] = f"Combat won via debug command. (+{combat.get('xp_gained', 0)} XP)"
        self._set_combat_state(combat)
        return int(combat.get("xp_gained") or 0)

    async def handle_debug_victory(self) -> AsyncGenerator[str, None]:
        """Handles ``/debug win_fight``: wins the fight and opens the loot phase."""
        xp_gained = await self.force_victory()
        msg = (
            "DEBUG: No active combat to win."
            if xp_gained is None
            else f"DEBUG: Combat forced to VICTORY (loot phase enabled). (+{xp_gained} XP)"
        )
        async for chunk in self._reply(msg):
            yield chunk
