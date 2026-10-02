"""Unit tests for Sequence Hard Rules (Deterministic Completion Triggers)."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.schemas.adventure import SequenceSchema
from backend.engine.world_schemas import SequenceSchema as ManifestSequenceSchema
from backend.engine.rule_engine import GameEvent, WorldEntityUpdate
from backend.api.routes.adventures.turn_state_applier import TurnStateApplier
from backend.core.world_validator import validate_adventure


def _setup_mock_manager(active_seq_id="SEQ_1"):
    mock_manager = MagicMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalars.return_value.first.return_value = MagicMock(exit_type="one_way", label="Crypt", name="NPC")
    mock_manager.db = MagicMock()
    mock_manager.db.execute = AsyncMock(return_value=mock_res)
    mock_manager.db.flush = AsyncMock()
    mock_manager.db.add = MagicMock()
    mock_manager.game_id = "test_game"
    mock_manager.state = MagicMock()
    mock_manager.state.session_id = "test_game"
    mock_manager.state.template_id = "test_adv"
    mock_manager.state.active_sequence_id = active_seq_id
    mock_manager.state.entity_states = {}
    mock_manager.state.current_scene_id = "START_ROOM"

    mock_manager.avatar = MagicMock()
    mock_manager.avatar.hp = 100
    mock_manager.avatar.stamina = 100
    mock_manager.avatar.mana = 100
    mock_manager.avatar.exp = 0
    mock_manager.avatar.inventory = []

    mock_manager.adventure = MagicMock()
    mock_manager.adventure.sequences = []
    mock_manager.adventure.awards = []

    mock_manager._save_chat_message = AsyncMock()
    mock_manager._collect_existing_item_ids = AsyncMock(return_value=set())
    mock_manager._apply_adventure_generator_tools = AsyncMock()
    mock_manager._queue_checkpoint = MagicMock()
    mock_manager._award_combat_victory_xp = MagicMock(return_value=50)

    return mock_manager


def test_sequence_schema_hard_rules():
    """Verify SequenceSchema accepts and defaults hard rule fields."""
    seq = SequenceSchema(
        id="SEQ_1",
        order=1,
        title="Chapter 1",
        end_condition="Soft narrative trigger",
        required_item_id="GOLDEN_KEY",
        required_scene_id="DUNGEON_CELL",
        required_defeated_npc_id="ORC_GUARD",
    )
    assert seq.required_item_id == "GOLDEN_KEY"
    assert seq.required_scene_id == "DUNGEON_CELL"
    assert seq.required_defeated_npc_id == "ORC_GUARD"

    # Test defaults
    seq_default = SequenceSchema(id="SEQ_2", order=2, title="Chapter 2")
    assert seq_default.required_item_id == ""
    assert seq_default.required_scene_id == ""
    assert seq_default.required_defeated_npc_id == ""

    # Test manifest schema
    man_seq = ManifestSequenceSchema(
        id="SEQ_1",
        order=1,
        title="Chapter 1",
        required_item_id="IRON_KEY",
    )
    assert man_seq.required_item_id == "IRON_KEY"


@pytest.mark.asyncio
async def test_hard_rule_required_item_completion():
    """Verify that having the required item triggers sequence completion deterministically."""
    mock_manager = _setup_mock_manager("SEQ_1")
    mock_manager.avatar.inventory = [{"id": "RUSTY_SWORD", "name": "Rusty Sword"}]
    mock_manager.adventure.sequences = [
        {
            "id": "SEQ_1",
            "order": 1,
            "title": "Finding the Sword",
            "required_item_id": "RUSTY_SWORD",
            "exp_reward": 75,
        },
        {
            "id": "SEQ_2",
            "order": 2,
            "title": "Next Chapter",
            "exp_reward": 50,
        },
    ]

    applier = TurnStateApplier(mock_manager)

    # Turn 1: LLM sets sequence_completed=False, but protagonist already has RUSTY_SWORD
    event = GameEvent(narrative_description="I pick up the sword.", sequence_completed=False)
    await applier._apply_game_event(event)

    # Hard rule satisfied -> sequence completes!
    assert event.sequence_completed is True
    assert mock_manager.avatar.exp == 75
    assert mock_manager.state.active_sequence_id == "SEQ_2"


@pytest.mark.asyncio
async def test_hard_rule_required_item_reverts_unmet_completion():
    """Verify that if required item is NOT present, sequence completion is blocked even if LLM claimed success."""
    mock_manager = _setup_mock_manager("SEQ_1")
    mock_manager.avatar.inventory = [{"id": "WOODEN_STICK", "name": "Wooden Stick"}]
    mock_manager.adventure.sequences = [
        {
            "id": "SEQ_1",
            "order": 1,
            "title": "Need the Key",
            "required_item_id": "GOLD_KEY",
            "exp_reward": 100,
        },
    ]

    applier = TurnStateApplier(mock_manager)

    # LLM hallucinates sequence_completed=True without the key
    event = GameEvent(narrative_description="You feel like you finished.", sequence_completed=True)
    await applier._apply_game_event(event)

    # Hard rule enforced -> completion reverted to False
    assert event.sequence_completed is False
    assert mock_manager.avatar.exp == 0


@pytest.mark.asyncio
async def test_hard_rule_required_scene_completion():
    """Verify that entering the required scene triggers sequence completion."""
    mock_manager = _setup_mock_manager("SEQ_1")
    mock_manager.adventure.sequences = [
        {
            "id": "SEQ_1",
            "order": 1,
            "title": "Enter the Crypt",
            "required_scene_id": "CRYPT_MAIN",
            "exp_reward": 50,
        },
        {
            "id": "SEQ_2",
            "order": 2,
            "title": "Inside the Crypt",
            "exp_reward": 50,
        },
    ]

    applier = TurnStateApplier(mock_manager)

    # Moving to CRYPT_MAIN
    event = GameEvent(new_scene_id="CRYPT_MAIN", sequence_completed=False)
    await applier._apply_game_event(event)

    assert event.sequence_completed is True
    assert mock_manager.state.active_sequence_id == "SEQ_2"


@pytest.mark.asyncio
async def test_hard_rule_defeated_npc_completion():
    """Verify that defeating the required NPC triggers sequence completion."""
    mock_manager = _setup_mock_manager("SEQ_1")
    mock_manager.state.entity_states = {"BOSS_DRAGON": {"hp": 100, "is_defeated": False}}
    mock_manager.adventure.sequences = [
        {
            "id": "SEQ_1",
            "order": 1,
            "title": "Slay the Dragon",
            "required_defeated_npc_id": "BOSS_DRAGON",
            "exp_reward": 500,
        },
    ]

    applier = TurnStateApplier(mock_manager)

    # Turn with entity update marking BOSS_DRAGON defeated
    event = GameEvent(
        updated_entities=[WorldEntityUpdate(entity_id="BOSS_DRAGON", is_defeated=True)],
        sequence_completed=False,
    )
    await applier._apply_game_event(event)

    assert event.sequence_completed is True
    assert event.game_completed is True  # Final sequence completed!
    assert mock_manager.avatar.exp == 500


def test_world_validator_catches_missing_sequence_references():
    """Verify that the world validator emits errors when sequences reference non-existent items, scenes, or NPCs."""
    payload = {
        "adventure": {
            "title": "Validation Test",
            "start_scene_id": "START",
            "rule_enforcement_mode": "rpg",
            "generate_scene_images": False,
            "generate_npc_images": False,
            "generate_item_images": False,
            "teaser": "A teaser",
            "rules": "x" * 200,
            "plot": "Plot",
            "intro_text": "Intro",
            "walkthrough": "x" * 100,
            "completed_condition": "Done",
            "gameover_condition": "Lost",
            "tts_director_notes": "Notes",
            "quests": [],
            "sequences": [
                {
                    "id": "SEQ_1",
                    "order": 1,
                    "title": "Chapter 1",
                    "required_item_id": "MISSING_KEY",
                    "required_scene_id": "MISSING_ROOM",
                    "required_defeated_npc_id": "MISSING_BOSS",
                }
            ],
        },
        "scenes": [{"id": "START", "label": "Start", "decorative_objects": []}],
        "npcs": [],
        "objects": [],
        "exits": [],
        "entities_all": [],
    }

    findings = validate_adventure(payload)
    item_errs = [f for f in findings if f.code == "sequence_references_missing_item"]
    scene_errs = [f for f in findings if f.code == "sequence_references_missing_scene"]
    npc_errs = [f for f in findings if f.code == "sequence_references_missing_npc"]

    assert len(item_errs) == 1
    assert item_errs[0].context["required_item_id"] == "MISSING_KEY"

    assert len(scene_errs) == 1
    assert scene_errs[0].context["required_scene_id"] == "MISSING_ROOM"

    assert len(npc_errs) == 1
    assert npc_errs[0].context["required_defeated_npc_id"] == "MISSING_BOSS"


def test_world_generator_extract_sequences_with_hard_rules():
    """Verify that WorldGenerator._extract_sequences_from_prompt parses hard rule tags."""
    from backend.engine.world_generator import WorldGenerator

    prompt = (
        "A dark fantasy story.\n\n"
        "[Sequence 1] Escape the Cell\n"
        "The protagonist wakes up in a prison cell.\n"
        "Required Item: CELL_KEY\n"
        "Required Scene: PRISON_HALLWAY\n"
        "End Condition: Unlock the cell door and step out.\n\n"
        "[Sequence: 2] Defeat the Warden\n"
        "Fight your way through the guard post.\n"
        "Defeat NPC: WARDEN_MORG\n"
        "Condition: The warden falls in battle.\n"
    )

    cleaned_prompt, sequences = WorldGenerator._extract_sequences_from_prompt(prompt)
    assert cleaned_prompt == "A dark fantasy story."
    assert len(sequences) == 2

    seq1 = sequences[0]
    assert seq1["title"] == "Escape the Cell"
    assert "The protagonist wakes up in a prison cell." in seq1["description"]
    assert "Required Item:" not in seq1["description"]
    assert seq1["required_item_id"] == "CELL_KEY"
    assert seq1["required_scene_id"] == "PRISON_HALLWAY"
    assert seq1["required_defeated_npc_id"] == ""
    assert seq1["end_condition"] == "Unlock the cell door and step out."

    seq2 = sequences[1]
    assert seq2["title"] == "Defeat the Warden"
    assert seq2["required_defeated_npc_id"] == "WARDEN_MORG"
    assert seq2["end_condition"] == "The warden falls in battle."


def test_world_generator_preprocess_manifest_normalizes_sequence_hard_rules():
    """Verify that preprocess_manifest_object_ids strips ## and normalizes empty/null hard rules."""
    from backend.engine.world_generator import WorldGenerator

    manifest_dict = {
        "objects": [{"id": "GOLD_KEY"}],
        "sequences": [
            {
                "id": "SEQ_1",
                "title": "Find the GOLD_KEY in the room",
                "description": "Look for the GOLD_KEY.",
                "required_item_id": "##GOLD_KEY",
                "required_scene_id": "none",
                "required_defeated_npc_id": "NULL",
            }
        ]
    }

    WorldGenerator.preprocess_manifest_object_ids(manifest_dict)
    seq = manifest_dict["sequences"][0]

    # Description and title got tokenized with ##
    assert "##GOLD_KEY" in seq["description"]
    # Hard rule ID fields are stripped of ## and normalized
    assert seq["required_item_id"] == "GOLD_KEY"
    assert seq["required_scene_id"] == ""
    assert seq["required_defeated_npc_id"] == ""

