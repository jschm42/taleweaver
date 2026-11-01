"""NPC allies: group members and helpers who join a fight without being attacked."""

from __future__ import annotations

from typing import Any

from backend.api.routes.adventures.combat.context import engaged_enemies, is_enemy_alive
from backend.engine.combat.groups import (
    joining_allies,
    normalize_group,
    resolve_assist_mode,
)
from backend.models.world_entity import WorldEntity


class CombatAlliesMixin:
    """Reads an NPC's combat group and pulls its allies into the fight."""

    def _npc_combat_group(self, npc: WorldEntity) -> str | None:
        override = self._entity_override(npc.id, "combat_group")
        if override is not None:
            return normalize_group(override)
        meta = npc.metadata_json if isinstance(npc.metadata_json, dict) else {}
        return normalize_group(meta.get("combat_group"))

    def _npc_assist_mode(self, npc: WorldEntity) -> str:
        override = self._entity_override(npc.id, "assist_mode")
        meta = npc.metadata_json if isinstance(npc.metadata_json, dict) else {}
        mode = override if override is not None else meta.get("assist_mode")
        return resolve_assist_mode(self._npc_combat_group(npc), mode)

    def _rally_allies(self, combat: dict[str, Any], helped: dict[str, Any] | None = None) -> None:
        """Engages every idle combatant whose group or assist mode makes it join the fight."""
        engaged = engaged_enemies(combat)
        idle = [
            e for e in combat.get("enemies") or [] if not e.get("engaged") and is_enemy_alive(e)
        ]
        for ally in joining_allies(idle, engaged):
            ally["engaged"] = True
            self._append_combat_log(
                combat, _join_text(ally, helped), "turn", {"kind": "engage", "entity": ally["id"]}
            )


def _join_text(ally: dict[str, Any], helped: dict[str, Any] | None) -> str:
    group = ally.get("combat_group")
    if helped and group and group == helped.get("combat_group"):
        return f"{ally['name']} rushes to help {helped['name']}!"
    return f"{ally['name']} joins the fight!"
