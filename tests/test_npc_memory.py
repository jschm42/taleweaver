"""NPC memory: a few lasting facts per character, written by Pass 1, read by both passes."""

from types import SimpleNamespace

import pytest

from backend.api.routes.adventures.npc_memory_flow import apply_npc_memories
from backend.core.world_validation.context import ValidationContext
from backend.core.world_validation.npc_memory import check_hostile_npc_memory
from backend.engine.blueprint import analyze_blueprint
from backend.engine.interaction.llm_intents import MechanicsIntent
from backend.engine.manifest_apply.npcs import npc_metadata
from backend.engine.rules.npc_memory import (
    MAX_MEMORY_SLOTS,
    MEMORY_TEXT_MAX,
    NPC_MEMORY_STATE_KEY,
    apply_npc_memory_ops,
    memory_slots,
    npc_memory_prompt_block,
    read_memories,
    remember,
)
from backend.engine.rules.rule_engine import GameEvent, NpcMemoryUpdate
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.runner import ScriptRunner
from backend.engine.world.world_schemas import WorldNPCSchema
from backend.models.session_state import SessionState


def _npc(npc_id: str, slots: int | None = None, name: str | None = None) -> SimpleNamespace:
    metadata = {"memory_slots": slots} if slots is not None else {}
    return SimpleNamespace(
        id=npc_id, name=name or npc_id.title(), entity_type="NPC", metadata_json=metadata
    )


class _FakeManager:
    """The few GameTurnManager members the flow uses; ``scene`` holds the visible NPCs."""

    def __init__(self, scene: list, entity_states: dict | None = None, arrival: bool = False):
        self.scene = {n.id: n for n in scene}
        self.state = SessionState(entity_states=entity_states or {})
        self.arrival_narration = arrival
        self.game_id = "s-mem"

    async def _find_scene_npc_by_hint(self, hint: str):
        return self.scene.get(str(hint).upper())

    def _is_npc_defeated(self, npc) -> bool:
        return bool((self.state.entity_states.get(npc.id) or {}).get("is_defeated"))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 0), (0, 0), (3, 3), ("5", 5), (99, MAX_MEMORY_SLOTS), (-2, 0), (True, 4), ("x", 0)],
)
def test_memory_slots_are_normalized(raw, expected):
    # Arrange
    metadata = {"memory_slots": raw}

    # Act
    slots = memory_slots(metadata)

    # Assert
    assert slots == expected


def test_remember_updates_known_key_and_evicts_oldest():
    # Arrange
    states: dict = {}

    # Act
    states = remember(states, "BRAN", "player_name", "The protagonist is called Kael.", 2)
    states = remember(states, "BRAN", "deal", "Kael promised to bring herbs.", 2)
    states = remember(states, "BRAN", "player_name", "The protagonist is called Kael Dorn.", 2)
    states = remember(states, "BRAN", "treatment", "Kael insulted him.", 2)

    # Assert
    facts = read_memories(states, "BRAN")
    assert [f["key"] for f in facts] == ["player_name", "treatment"]
    assert facts[0]["text"] == "The protagonist is called Kael Dorn."


def test_remember_forgets_clips_and_reports_no_change():
    # Arrange
    states = remember({}, "BRAN", "deal", "Kael promised herbs.", 3)

    # Act
    unchanged = remember(states, "BRAN", "deal", "Kael promised herbs.", 3)
    clipped = remember(states, "BRAN", "Old Story!", "word " * 60, 3)
    forgotten = remember(states, "BRAN", "deal", "", 3)

    # Assert
    assert unchanged is states
    long_fact = read_memories(clipped, "BRAN")[-1]
    assert long_fact["key"] == "old_story"
    assert len(long_fact["text"]) <= MEMORY_TEXT_MAX
    assert NPC_MEMORY_STATE_KEY in forgotten
    assert read_memories(forgotten, "BRAN") == []


def test_prompt_block_lists_only_present_memory_npcs():
    # Arrange
    states = remember({}, "BRAN", "player_name", "The protagonist is called Kael.", 4)
    scene = [_npc("BRAN", 4, "Bran"), _npc("MIRA", 2, "Mira"), _npc("GOBLIN")]

    # Act
    mechanics = npc_memory_prompt_block(states, scene, for_mechanics=True)
    narration = npc_memory_prompt_block(states, scene, for_mechanics=False)
    empty = npc_memory_prompt_block(states, [_npc("GOBLIN")], for_mechanics=True)

    # Assert
    assert "Bran (BRAN) [1/4]: player_name=The protagonist is called Kael." in mechanics
    assert "Mira (MIRA) [0/2]: nothing yet" in mechanics
    assert "GOBLIN" not in mechanics and "npc_memories" in mechanics
    assert "- Bran: The protagonist is called Kael." in narration
    assert "Mira" not in narration and "player_name" not in narration
    assert empty == ""


@pytest.mark.asyncio
async def test_flow_stores_valid_facts_and_drops_the_rest():
    # Arrange
    manager = _FakeManager([_npc("BRAN", 3), _npc("GOBLIN")])
    event = GameEvent(
        npc_memories=[
            NpcMemoryUpdate(npc_id="bran", key="player_name", text="Called Kael."),
            NpcMemoryUpdate(npc_id="GOBLIN", key="insult", text="Kael mocked him."),
            NpcMemoryUpdate(npc_id="ELSEWHERE", key="deal", text="Owes Kael."),
        ]
    )

    # Act
    await apply_npc_memories(manager, event)

    # Assert
    store = manager.state.entity_states[NPC_MEMORY_STATE_KEY]
    assert store == {"BRAN": [{"key": "player_name", "text": "Called Kael."}]}
    assert event.npc_memories is None


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["arrival", "defeated", "hidden"])
async def test_flow_ignores_arrival_and_out_of_action_npcs(case):
    # Arrange
    states = {"BRAN": {"is_defeated": case == "defeated", "is_hidden": case == "hidden"}}
    manager = _FakeManager([_npc("BRAN", 3)], states, arrival=case == "arrival")
    event = GameEvent(npc_memories=[NpcMemoryUpdate(npc_id="BRAN", key="k", text="Fact.")])

    # Act
    await apply_npc_memories(manager, event)

    # Assert
    assert NPC_MEMORY_STATE_KEY not in manager.state.entity_states


@pytest.mark.asyncio
async def test_flow_caps_updates_per_message():
    # Arrange
    manager = _FakeManager([_npc("BRAN", 8)])
    updates = [NpcMemoryUpdate(npc_id="BRAN", key=f"k{i}", text=f"Fact {i}.") for i in range(6)]

    # Act
    await apply_npc_memories(manager, GameEvent(npc_memories=updates))

    # Assert
    assert len(read_memories(manager.state.entity_states, "BRAN")) == 3


def test_memory_slots_survive_blueprint_schema_and_manifest():
    # Arrange
    text = "[Scene: INN] Inn\nCozy.\n[NPC: BRAN] Bran\nin: INN\nmemory: 4\n"

    # Act
    blueprint, issues = analyze_blueprint(text)
    npc = next(b for b in blueprint.blocks if b.kind == "npc")
    slots = npc.fields["memory_slots"].value
    schema = WorldNPCSchema.model_fields.get("memory_slots")
    generated = npc_metadata({"id": "BRAN", "memory_slots": slots})
    exported = npc_metadata({"id": "BRAN", "metadata_json": {"memory_slots": 6}})
    without = npc_metadata({"id": "GOBLIN"})

    # Assert
    assert issues == [] and blueprint.issues == []
    assert slots == 4 and schema is not None
    assert generated["memory_slots"] == 4
    assert exported["memory_slots"] == 6
    assert without["memory_slots"] is None


def test_pass1_schema_offers_npc_memories():
    # Arrange / Act
    fields = MechanicsIntent.model_fields

    # Assert
    assert "npc_memories" in fields


def test_validator_warns_about_memory_on_hostile_npcs():
    # Arrange
    payload = {
        "npcs": [
            {
                "id": "OGRE",
                "entity_type": "NPC",
                "metadata_json": {"memory_slots": 4, "attack_mode": "ATTACK_ON_SIGHT"},
            },
            {"id": "BRAN", "entity_type": "NPC", "metadata_json": {"memory_slots": 4}},
        ]
    }

    # Act
    findings = check_hostile_npc_memory(ValidationContext.from_payload(payload))

    # Assert
    assert [f.code for f in findings] == ["npc_memory_on_hostile"]


def _script_context(store: dict | None = None) -> GameContext:
    entities = {
        "BRAN": {
            "id": "BRAN",
            "name": "Bran",
            "entity_type": "NPC",
            "metadata_json": {"memory_slots": 2},
        },
        "OGRE": {"id": "OGRE", "name": "Ogre", "entity_type": "NPC", "metadata_json": {}},
    }
    return GameContext(current_scene_id="INN", entities=entities, npc_memory=store)


def test_script_api_reads_back_and_replays_memory_ops():
    # Arrange
    store = {"BRAN": [{"key": "player_name", "text": "Called Kael."}]}
    ctx = _script_context(store)
    code = """
tw.npcs.remember("BRAN", "deal", "Kael owes him 5 gold.")
known = tw.npcs.recalls("BRAN", "player_name")
debt = tw.npcs.get("Bran").recall("deal")
tw.npcs.remember("OGRE", "insult", "Kael mocked him.")
tw.vars.set("known", known)
tw.vars.set("debt", debt)
"""

    # Act
    ScriptRunner([]).execute_code(code, {"tw": ctx})
    states = {NPC_MEMORY_STATE_KEY: dict(store)}
    apply_npc_memory_ops(states, ctx.changeset.npc_memory_ops)

    # Assert
    assert ctx.changeset.var_updates == {"known": True, "debt": "Kael owes him 5 gold."}
    assert [f["key"] for f in read_memories(states, "BRAN")] == ["player_name", "deal"]
    assert read_memories(states, "OGRE") == []
    assert ctx.changeset.has_changes


def test_script_api_forgets_one_or_all_facts():
    # Arrange
    store = {
        "BRAN": [{"key": "player_name", "text": "Called Kael."}, {"key": "deal", "text": "Owes."}]
    }
    ctx = _script_context(store)
    states = {NPC_MEMORY_STATE_KEY: dict(store)}

    # Act
    ctx.npcs.forget("BRAN", "deal")
    after_one = [m["key"] for m in ctx.npcs.memories("BRAN")]
    ctx.npcs.get("BRAN").forget()
    apply_npc_memory_ops(states, ctx.changeset.npc_memory_ops)

    # Assert
    assert after_one == ["player_name"]
    assert ctx.npcs.memories("BRAN") == []
    assert read_memories(states, "BRAN") == []
