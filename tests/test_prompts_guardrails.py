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