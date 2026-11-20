"""World memories stay bounded and only reach the prompt when they matter right now."""

from backend.engine.rules.world_memories import (
    MAX_PROMPT_MEMORIES,
    MAX_STORED_MEMORIES,
    MEMORY_DESCRIPTION_MAX,
    add_world_memory,
    make_world_memory,
    world_memories_prompt_block,
)


def test_add_world_memory_clips_skips_duplicates_and_drops_oldest():
    # Arrange
    memories: list = []

    # Act
    for i in range(MAX_STORED_MEMORIES + 5):
        memories, _ = add_world_memory(memories, make_world_memory(f"Event {i}"))
    memories, duplicate_added = add_world_memory(
        memories, make_world_memory(f"event {MAX_STORED_MEMORIES + 4}")
    )
    long_entry = make_world_memory("word " * 80)
    empty = make_world_memory("   ")

    # Assert
    assert len(memories) == MAX_STORED_MEMORIES
    assert memories[0]["description"] == "Event 5"
    assert duplicate_added is False
    assert long_entry is not None and len(long_entry["description"]) <= MEMORY_DESCRIPTION_MAX
    assert empty is None


def test_prompt_block_filters_by_scene_and_present_npc_and_caps_lines():
    # Arrange
    memories = [
        make_world_memory("The wizard hates you.", npc_id="WIZARD", emotion="negative"),
        make_world_memory("The bridge collapsed.", scope="local", scene_id="BRIDGE"),
        *[make_world_memory(f"Global event {i}") for i in range(MAX_PROMPT_MEMORIES + 2)],
    ]

    # Act
    away = world_memories_prompt_block(memories, "TOWER", [])
    with_wizard = world_memories_prompt_block(memories[:2], "TOWER", ["wizard"])

    # Assert
    assert "wizard" not in away and "bridge" not in away
    assert len(away.strip().splitlines()) == 1 + MAX_PROMPT_MEMORIES
    assert "- The wizard hates you. (negative)" in with_wizard
    assert "bridge" not in with_wizard
    assert world_memories_prompt_block([], "TOWER") == ""
