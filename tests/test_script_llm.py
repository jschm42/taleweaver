"""Tests for tw.llm.ask in the scripting sandbox."""

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


def _run(code: str, asker=None) -> GameContext:
    context = GameContext(llm_asker=asker)
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
        "tw.llm.ask('Should the door open?') == '' and not tw.llm.available", {"tw": context}
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
