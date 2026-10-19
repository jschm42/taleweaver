"""Initiative rolls for multi-combatant encounters."""

from __future__ import annotations

import random
from typing import Any

PLAYER_ID = "PLAYER"


def initiative_bonus(dexterity: int) -> int:
    return max(0, int(dexterity or 0) // 2)


def roll_initiative(participants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rolls d20 + DEX bonus for every participant and returns them in acting order.

    ``participants`` entries need ``id``, ``name`` and ``dexterity``. Ties favour the
    protagonist, then the original participant order.
    """
    rolled = []
    for position, entry in enumerate(participants):
        roll = random.randint(1, 20)
        bonus = initiative_bonus(entry.get("dexterity", 0))
        rolled.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "roll": roll,
                "bonus": bonus,
                "total": roll + bonus,
                "_position": position,
            }
        )
    rolled.sort(key=lambda e: (-e["total"], 0 if e["id"] == PLAYER_ID else 1, e["_position"]))
    for entry in rolled:
        entry.pop("_position", None)
    return rolled


def describe_initiative(order: list[dict[str, Any]], round_no: int) -> str:
    parts = [f"{e['name']} {e['total']}" for e in order]
    return f"Round {round_no} initiative: " + " > ".join(parts) + "."
