from backend.core import prompts


def test_game_master_system_prompt_keeps_walkthrough_confidentiality_guardrail() -> None:
    template = prompts.GAME_MASTER_SYSTEM_PROMPT_TEMPLATE
    assert "WALKTHROUGH CONFIDENTIALITY (CRITICAL)" in template
    assert "Never reveal it verbatim" in template
    assert "never provide exact step-by-step solutions" in template
    assert "provide subtle hints and broad strategy only" in template


def test_chat_narration_suffix_enforces_hint_only_behavior() -> None:
    suffix = prompts.GM_CHAT_NARRATION_SUFFIX
    assert "Never reveal the internal walkthrough directly" in suffix
    assert "give only hints and rough guidance" in suffix


def test_chat_tool_intent_suffix_blocks_walkthrough_spoilers() -> None:
    suffix = prompts.GM_CHAT_TOOL_INTENT_SUFFIX
    assert "Never output or expose the secret walkthrough verbatim" in suffix
    assert "prefer hint-level guidance only" in suffix


def test_mechanics_and_rule_pass_prompts_block_solution_path_spoilers() -> None:
    mechanics = prompts.GM_MECHANICS_SUFFIX
    story_mechanics = prompts.GM_STORY_MECHANICS_SUFFIX
    chat_rule_pass = prompts.GM_CHAT_MINIMAL_RULE_PASS_PROMPT

    assert "never provide exact step-by-step solution paths" in mechanics
    assert "never provide exact step-by-step solution paths" in story_mechanics
    assert "never provide exact step-by-step solution paths" in chat_rule_pass


def test_puzzle_json_enforcement_block_covers_required_engine_fields() -> None:
    block = prompts.PUZZLE_JSON_ENFORCEMENT_BLOCK

    required_fields = [
        "is_locked",
        "lock_description",
        "combination_ingredients",
        "reveals_item_id",
        "is_hidden",
        "reveal_rule",
        "is_portable",
        "spatial_position",
        "wearable_slots",
        "item_type",
        "stat_modifier_strength",
        "metadata_json.code_to_unlock",
        "metadata_json.item_to_unlock",
        "voice",
        "extra_time_minutes",
    ]

    for field_name in required_fields:
        assert field_name in block


def test_puzzle_design_patterns_block_contains_all_pattern_ids() -> None:
    block = prompts.PUZZLE_DESIGN_PATTERNS_BLOCK

    for pattern_id in ("A1", "A2", "A3", "B1", "B2", "C1", "C2", "C3", "D1", "D2"):
        assert f"{pattern_id} " in block


def test_world_and_gm_prompts_include_puzzle_contract_and_patterns() -> None:
    puzzle_contract = prompts.PUZZLE_JSON_ENFORCEMENT_BLOCK
    puzzle_patterns = prompts.PUZZLE_DESIGN_PATTERNS_BLOCK

    prompt_targets = [
        prompts.WORLD_GENERATION_SYSTEM_PROMPT,
        prompts.GM_MECHANICS_SUFFIX,
        prompts.GM_STORY_MECHANICS_SUFFIX,
        prompts.GM_CHAT_TOOL_INTENT_SUFFIX,
        prompts.GM_CHAT_MINIMAL_RULE_PASS_PROMPT,
    ]

    for prompt_text in prompt_targets:
        assert puzzle_contract in prompt_text
        assert puzzle_patterns in prompt_text