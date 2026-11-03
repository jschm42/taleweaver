"""Tests for tw.llm.ask, tw.llm.ask_json and tw.json in the scripting sandbox."""

from types import SimpleNamespace

from backend.api.routes.adventures.script_llm import _model_for
from backend.engine.scripting import GameContext, ScriptRunner
from backend.engine.scripting.llm_proxy import MAX_CALLS_PER_CONTEXT
from backend.engine.scripting.sandbox import SafeAstInterpreter


class FakeAsker:
    def __init__(self, answer="A raven croaks your name.", error=None):
        self.answer = answer
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, prompt, system, tier):
        self.calls.append((prompt, system, tier))
        if self.error:
            raise self.error
        return self.answer


def _run(code: str, asker=None, debug: bool = False) -> GameContext:
    context = GameContext(llm_asker=asker, is_debug_enabled=debug)
    SafeAstInterpreter().execute(code, {"tw": context})
    return context


def test_ask_returns_answer_and_passes_model_tier():
    # Arrange
    asker = FakeAsker()

    # Act
    context = _run(
        "line = tw.llm.ask('Describe a raven.', model='advanced', system='Be eerie.')\n"
        "tw.story.narrate(line)",
        asker,
    )

    # Assert
    assert asker.calls == [("Describe a raven.", "Be eerie.", "advanced")]
    assert context.changeset.narrative_messages == ["A raven croaks your name."]


def test_ask_defaults_to_simple_model():
    # Arrange
    asker = FakeAsker()

    # Act
    _run("tw.llm.ask('Hi')", asker)

    # Assert
    assert asker.calls[0][2] == "simple"


def test_unknown_model_tier_is_a_script_error():
    # Arrange
    asker = FakeAsker()

    context = GameContext(llm_asker=asker)

    # Act
    ScriptRunner().execute_code("tw.llm.ask('Hi', model='huge')", {"tw": context})

    # Assert
    errors = [m for m in context.changeset.system_messages if m.startswith("Script error")]
    assert errors and "model must be 'simple' or 'advanced'" in errors[0]
    assert asker.calls == []


def test_calls_are_capped_per_context():
    # Arrange
    asker = FakeAsker(answer="ok")

    # Act
    _run(
        "for i in range(5):\n    tw.llm.ask('q' + str(i))\n",
        asker,
    )

    # Assert
    assert len(asker.calls) == MAX_CALLS_PER_CONTEXT


def test_missing_asker_and_provider_errors_return_empty_string():
    # Arrange
    failing = FakeAsker(error=RuntimeError("provider down"))

    # Act
    no_llm = _run("tw.vars.set('a', tw.llm.ask('Hi') or 'fallback')")
    broken = _run("tw.vars.set('a', tw.llm.ask('Hi') or 'fallback')", failing)

    # Assert
    assert no_llm.changeset.var_updates["a"] == "fallback"
    assert broken.changeset.var_updates["a"] == "fallback"
    assert len(failing.calls) == 1


def test_guard_expressions_never_call_the_llm():
    # Arrange
    asker = FakeAsker()
    context = GameContext(llm_asker=asker)

    # Act
    result = SafeAstInterpreter().evaluate_expression(
        "tw.llm.ask('Should the door open?') == '' and tw.llm.ask_json('Q') is None and not tw.llm.available",
        {"tw": context},
    )

    # Assert
    assert result is True
    assert asker.calls == []


def test_waiting_for_the_llm_does_not_count_against_the_time_limit(monkeypatch):
    # Arrange: a fake clock that jumps past the 2 s budget while the model "answers".
    clock = [1000.0]
    monkeypatch.setattr("backend.engine.scripting.sandbox.time.monotonic", lambda: clock[0])

    def slow_asker(_prompt, _system, _tier):
        clock[0] += 10
        return "done"

    context = GameContext(llm_asker=slow_asker)
    runner = ScriptRunner()

    # Act
    runner.execute_code(
        "x = tw.llm.ask('slow')\ntotal = 0\nfor i in range(300):\n    total += i\n",
        {"tw": context},
    )

    # Assert
    assert not any("Script error" in m for m in context.changeset.system_messages)


def test_model_for_maps_tiers_to_small_and_complex_settings():
    # Arrange
    user = SimpleNamespace(
        llm_settings={
            "small_model_provider": "anthropic",
            "small_model": "claude-haiku-5-5",
            "complex_model_provider": "openrouter",
            "complex_model": "claude-opus-5-5",
        }
    )

    # Act / Assert
    assert _model_for(user, "simple") == ("anthropic", "claude-haiku-5-5", "small")
    assert _model_for(user, "advanced") == ("openrouter", "claude-opus-5-5", "complex")
    assert _model_for(SimpleNamespace(llm_settings={}), "simple")[1] == "gpt-4o-mini"


def test_ask_json_parses_markdown_fences_and_validates_schema():
    # Arrange
    raw_json = (
        "<think>Generating PCEP question...</think>\n"
        "```json\n"
        "{\n"
        '  "question": "What is the output of:\\n```python\\nfor i in range(2):\\n    print(i)\\n```",\n'
        '  "options": ["0\\n1", "1\\n2", "0 1", "Error"],\n'
        '  "correct_index": 0,\n'
        '  "explanation": "range(2) yields 0 and 1."\n'
        "}\n"
        "```"
    )
    asker = FakeAsker(answer=raw_json)
    code = """
schema = {
    "question": {"type": "str", "min_len": 5},
    "options": {"type": "list", "items": {"type": "str", "min_len": 1}, "min_len": 4, "max_len": 4},
    "correct_index": {"type": "int", "min": 0, "max": 3},
    "explanation": {"type": "str", "optional": True},
}
quiz = tw.llm.ask_json("Generate a PCEP question", schema=schema)
tw.vars.set("quiz", quiz)
"""

    # Act
    context = _run(code, asker)

    # Assert
    quiz = context.changeset.var_updates["quiz"]
    assert isinstance(quiz, dict)
    assert quiz["correct_index"] == 0
    assert len(quiz["options"]) == 4
    assert "    print(i)" in quiz["question"]
    assert "Return ONLY valid JSON matching this schema" in asker.calls[0][1]


def test_ask_json_returns_none_when_schema_fails_or_json_invalid():
    # Arrange
    bad_schema_asker = FakeAsker(
        answer='{"question": "x?", "options": ["a", "b"], "correct_index": 5}'
    )
    broken_json_asker = FakeAsker(answer="Not JSON at all!")
    code = """
schema = {
    "question": "str",
    "options": {"type": "list", "items": "str", "min_len": 4, "max_len": 4},
    "correct_index": {"type": "int", "min": 0, "max": 3},
}
tw.vars.set("res", tw.llm.ask_json("Q", schema=schema))
"""

    # Act
    bad_schema_ctx = _run(code, bad_schema_asker, debug=True)
    broken_json_ctx = _run(code, broken_json_asker, debug=True)

    # Assert
    assert bad_schema_ctx.changeset.var_updates["res"] is None
    assert any("schema validation failed" in m for m in bad_schema_ctx.changeset.system_messages)
    assert broken_json_ctx.changeset.var_updates["res"] is None
    assert any("invalid JSON syntax" in m for m in broken_json_ctx.changeset.system_messages)


def test_tw_json_loads_validate_and_dumps():
    # Arrange
    code = """
schema = {"name": str, "score": {"type": int, "min": 0, "max": 100}}
parsed = tw.json.loads('{"name": "Ada", "score": 95,}', schema=schema)
invalid = tw.json.loads('{"name": "Ada", "score": 200}', schema=schema, default={"fallback": True})
dumped = tw.json.dumps(parsed)
is_ok = tw.json.validate(parsed, schema)
tw.vars.set("parsed", parsed)
tw.vars.set("invalid", invalid)
tw.vars.set("dumped", dumped)
tw.vars.set("is_ok", is_ok)
"""

    # Act
    context = _run(code)

    # Assert
    assert context.changeset.var_updates["parsed"] == {"name": "Ada", "score": 95}
    assert context.changeset.var_updates["invalid"] == {"fallback": True}
    assert '"Ada"' in context.changeset.var_updates["dumped"]
    assert context.changeset.var_updates["is_ok"] is True
