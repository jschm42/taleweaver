"""An open loot phase must not follow the player out of the fight scene."""

from types import SimpleNamespace
from typing import Any

import pytest

from backend.api.routes.adventures.combat.loot import CombatLootMixin


class _LootStub(CombatLootMixin):
    def __init__(self, combat: dict[str, Any] | None) -> None:
        entity_states = {"__combat__": combat} if combat is not None else {}
        self.state = SimpleNamespace(
            entity_states=entity_states, combat_json=combat, current_scene_id="FIGHT_ROOM"
        )
        self.spawned: list[tuple[str, str]] = []

    def _read_combat_state(self) -> dict[str, Any]:
        return dict(self.state.entity_states.get("__combat__") or {})

    async def _spawn_scene_item(self, item: dict[str, Any]) -> None:
        self.spawned.append((item["name"], self.state.current_scene_id))


@pytest.mark.asyncio
async def test_open_loot_phase_is_left_behind_in_the_fight_scene(monkeypatch):
    # Arrange
    monkeypatch.setattr("backend.api.routes.adventures.combat.loot.flag_modified", lambda *_: None)
    stub = _LootStub(
        {
            "active": False,
            "loot_pending": True,
            "outcome": "victory",
            "loot_items": [{"id": "RUSTY_AXE", "name": "Rusty Axe"}],
        }
    )

    # Act
    note = await stub.settle_loot_on_scene_exit()

    # Assert
    assert note == "You leave the remaining loot behind: Rusty Axe"
    assert stub.spawned == [("Rusty Axe", "FIGHT_ROOM")]
    assert "__combat__" not in stub.state.entity_states
    assert stub.state.combat_json is None


@pytest.mark.asyncio
async def test_active_fight_and_missing_fight_are_left_alone():
    # Arrange
    active = _LootStub({"active": True, "loot_pending": False, "loot_items": []})
    empty = _LootStub(None)

    # Act
    active_note = await active.settle_loot_on_scene_exit()
    empty_note = await empty.settle_loot_on_scene_exit()

    # Assert
    assert active_note is None
    assert empty_note is None
    assert "__combat__" in active.state.entity_states
