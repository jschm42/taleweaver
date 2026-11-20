"""The play-agent's OBJECTIVES block: quest log, current chapter and clock."""

from types import SimpleNamespace

from backend.api.routes.adventures.agent_objectives import format_objectives


def _adventure(clock_enabled=True):
    return SimpleNamespace(
        clock_enabled=clock_enabled,
        time_per_turn=5,
        time_system="calendar",
        time_config={},
        sequence_progression_mode="linear",
        sequences=[
            {"id": "SEQ_1", "order": 1, "title": "Lure Mom Out", "description": "Get Mom out of her office.",
             "walkthrough": "SECRET: bribe Tina with the drink."},
        ],
    )  # fmt: skip


def _state(quests=None):
    return SimpleNamespace(
        active_sequence_id="SEQ_1",
        in_game_time=95,
        entity_states={},
        time_system=None,
        time_config=None,
        quests=quests
        or [
            {
                "id": "Q1",
                "title": "Peace and Quiet",
                "description": "Calm the dog.",
                "status": "open",
            },
            {
                "id": "Q2",
                "title": "Ming Restoration",
                "goal": "Glue the dish.",
                "status": "completed",
            },
        ],
    )


def test_objectives_show_chapter_quests_and_clock_without_walkthrough():
    text = format_objectives(_adventure(), _state())

    assert "CURRENT CHAPTER: Lure Mom Out - Get Mom out of her office." in text
    assert "- [OPEN] Peace and Quiet: Calm the dog." in text
    assert "- [DONE] Ming Restoration: Glue the dish." in text
    assert "CURRENT TIME:" in text
    assert "costs about 5 in-game minutes" in text
    assert "SECRET" not in text  # walkthrough stays behind the XP unlock


def test_no_clock_lines_without_a_clock():
    text = format_objectives(_adventure(clock_enabled=False), _state())

    assert "CURRENT TIME" not in text
    assert "Always work towards the CURRENT CHAPTER goal first" in text
