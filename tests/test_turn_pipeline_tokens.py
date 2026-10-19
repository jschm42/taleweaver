"""Unit tests for the token-optimized turn pipeline building blocks."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.adventures.turn_pass_flow import (
    advance_in_game_turn,
    crossed_turn_boundary,
    extract_usage_tokens,
    turn_anchor,
)
from backend.api.routes.adventures.turn_prompt_layout import (
    build_outcome_json,
    build_pass1_user_prompt,
    format_recent_narration,
)
from backend.core.llm_request_tuning import apply_prompt_cache_markers, compact_json_schema
from backend.engine.llm_intents import ChatProgressionIntent, MechanicsIntent, to_game_event
from backend.engine.location_context import build_location_context
from backend.engine.rule_engine import GameEvent, SkillCheckRequest


def _state(scene: str = "START", sequence: str | None = "SEQ_1") -> SimpleNamespace:
    return SimpleNamespace(current_scene_id=scene, active_sequence_id=sequence, in_game_time=0)


# --- In-game turn clock ---------------------------------------------------------------


def test_turn_boundary_only_on_scene_or_sequence_change() -> None:
    # Arrange
    state = _state()
    anchor = turn_anchor(state)

    # Act / Assert: same scene and sequence -> same in-game turn
    assert crossed_turn_boundary(state, anchor) is False

    state.current_scene_id = "CELLAR"
    assert crossed_turn_boundary(state, anchor) is True

    state.current_scene_id = "START"
    state.active_sequence_id = "SEQ_2"
    assert crossed_turn_boundary(state, anchor) is True


@pytest.mark.asyncio
async def test_advance_in_game_turn_runs_end_time_ticks_start_in_order() -> None:
    # Arrange
    calls: list[str] = []
    changeset = SimpleNamespace(has_changes=True)
    runner = MagicMock()
    runner.scripts = [{"trigger": "on_turn_start"}]
    runner.run_trigger = MagicMock(
        side_effect=lambda trigger, _ctx: calls.append(trigger) or changeset
    )

    manager = SimpleNamespace(
        state=_state(),
        adventure=SimpleNamespace(time_per_turn=7),
        avatar=SimpleNamespace(status_effects=["Poisoned"], hp=50, stamina=10, mana=10),
        _build_script_context=AsyncMock(return_value=object()),
        _apply_script_changeset=AsyncMock(return_value=[]),
        _finalize_session=AsyncMock(),
    )

    # Act
    events = [event async for event in advance_in_game_turn(manager, runner)]

    # Assert
    assert calls == ["on_turn_end", "on_turn_start"]
    assert manager.state.in_game_time == 7
    assert manager.avatar.hp == 45  # Poisoned tick applied once
    assert any("[Poisoned]" in event for event in events)


@pytest.mark.asyncio
async def test_advance_in_game_turn_without_scripts_only_moves_clock() -> None:
    # Arrange
    runner = MagicMock()
    runner.scripts = []
    manager = SimpleNamespace(
        state=_state(),
        adventure=SimpleNamespace(time_per_turn=None),
        avatar=SimpleNamespace(status_effects=[], hp=50, stamina=10, mana=10),
    )

    # Act
    events = [event async for event in advance_in_game_turn(manager, runner)]

    # Assert
    assert events == []
    assert manager.state.in_game_time == 5  # default pace
    runner.run_trigger.assert_not_called()


# --- Trimmed Pass 1 schemas ----------------------------------------------------------


def test_mechanics_intent_omits_backend_and_generator_fields() -> None:
    # Arrange
    excluded = {
        "skill_check_results",
        "attack_results",
        "tool_results",
        "requested_adventure_generation",
        "request_available_image_styles",
        "scene_label",
        "image_prompt",
    }

    # Act
    fields = set(MechanicsIntent.model_fields)
    schema_size = len(json.dumps(MechanicsIntent.model_json_schema()))
    full_size = len(json.dumps(GameEvent.model_json_schema()))

    # Assert
    assert not (fields & excluded)
    assert {"requested_skill_checks", "updated_exits", "discovered_entity_ids"} <= fields
    assert schema_size < full_size * 0.75


def test_chat_progression_intent_supports_exit_unlocks() -> None:
    # Arrange / Act
    intent = ChatProgressionIntent.model_validate(
        {"updated_exits": [{"from_scene_id": "A", "to_scene_id": "B", "is_locked": False}]}
    )

    # Assert
    assert "requested_adventure_generation" not in ChatProgressionIntent.model_fields
    assert intent.updated_exits[0].to_scene_id == "B"


def test_to_game_event_keeps_aliases_and_nested_models() -> None:
    # Arrange
    intent = MechanicsIntent.model_validate(
        {
            "removed_items": ["KEY"],
            "extra_time": 10,
            "requested_skill_checks": [{"stat": "strength", "dc": 12, "reason": "Lift"}],
        }
    )

    # Act
    event = to_game_event(intent)

    # Assert
    assert isinstance(event, GameEvent)
    assert event.removed_inventory_item_ids == ["KEY"]
    assert event.extra_time_minutes == 10
    assert isinstance(event.requested_skill_checks[0], SkillCheckRequest)


# --- Prompt layout -------------------------------------------------------------------


def test_pass1_user_prompt_contains_state_recent_narration_and_action() -> None:
    # Arrange
    history = [
        {"role": "assistant", "content": "A chest sits under the window."},
        {"role": "user", "content": "open it"},
    ]

    # Act
    prompt = build_pass1_user_prompt("CURRENT STATE:\nX", "open it", history, ("OPEN QUESTS: []",))

    # Assert
    assert prompt.startswith("CURRENT STATE:")
    assert "OPEN QUESTS: []" in prompt
    assert "A chest sits under the window." in prompt
    assert prompt.endswith("PLAYER ACTION:\nopen it")


def test_recent_narration_is_truncated_to_tail() -> None:
    # Arrange
    long_text = "x" * 1000 + "THE END"

    # Act
    block = format_recent_narration([{"role": "assistant", "content": long_text}])

    # Assert
    assert block.endswith("THE END")
    assert len(block) < 500


def test_outcome_json_drops_planning_fields() -> None:
    # Arrange
    event = GameEvent(
        narrative_description="Draft",
        requested_skill_checks=[SkillCheckRequest(stat="dexterity", dc=10, reason="Climb")],
        hp_change=-3,
    )

    # Act
    draft, outcome_json = build_outcome_json(event)

    # Assert
    assert draft == "Draft"
    assert json.loads(outcome_json) == {"hp_change": -3}


def test_full_location_context_hides_lock_secrets() -> None:
    # Arrange
    scene = SimpleNamespace(
        id="VAULT", label="Vault", description="Steel walls.", decorative_objects=[]
    )
    exits = [
        SimpleNamespace(
            label="Door",
            to_scene_id="OUT",
            is_locked=True,
            lock_description="A keypad glows.",
            code_to_unlock="1234",
            item_to_unlock=None,
            rule_to_unlock=None,
        )
    ]

    # Act
    narration = build_location_context(scene, [], exits, "full")
    mechanics = build_location_context(scene, [], exits, "concise")

    # Assert
    assert "1234" not in narration
    assert "A keypad glows." in narration
    assert "code:1234" in mechanics


# --- Request tuning ------------------------------------------------------------------


def test_compact_json_schema_strips_titles_but_keeps_title_fields() -> None:
    # Arrange
    schema = {
        "title": "Model",
        "properties": {"title": {"title": "Title", "type": "string"}},
    }

    # Act
    compacted = compact_json_schema(schema)

    # Assert
    assert compacted == {"properties": {"title": {"type": "string"}}}


def test_cache_markers_only_for_anthropic_models() -> None:
    # Arrange
    anthropic_msgs = [
        {"role": "system", "content": "static"},
        {"role": "assistant", "content": "previous"},
        {"role": "user", "content": "now"},
    ]
    openai_msgs = [dict(m) for m in anthropic_msgs]

    # Act
    apply_prompt_cache_markers(anthropic_msgs, "anthropic", "claude-sonnet-5-5")
    apply_prompt_cache_markers(openai_msgs, "openai", "gpt-4o")

    # Assert
    assert anthropic_msgs[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert anthropic_msgs[1]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert anthropic_msgs[2]["content"] == "now"
    assert openai_msgs[0]["content"] == "static"


def test_extract_usage_tokens_reads_cached_tokens_and_ignores_mocks() -> None:
    # Arrange
    usage = SimpleNamespace(
        prompt_tokens=1200,
        completion_tokens=150,
        prompt_tokens_details=SimpleNamespace(cached_tokens=1024),
    )

    # Act / Assert
    assert extract_usage_tokens(usage) == {
        "prompt_tokens": 1200,
        "completion_tokens": 150,
        "cached_prompt_tokens": 1024,
    }
    assert extract_usage_tokens(MagicMock()) == {}
    assert extract_usage_tokens(None) == {}
