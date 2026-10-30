"""Comprehensions and generator expressions in the script sandbox."""

from types import SimpleNamespace

import pytest

from backend.engine.scripting.sandbox import (
    SafeAstInterpreter,
    ScriptExecutionError,
    ScriptSecurityError,
    ScriptTimeoutError,
)


def _npcs() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(id="GUARD", is_hidden=False),
        SimpleNamespace(id="THIEF", is_hidden=True),
        SimpleNamespace(id="COOK", is_hidden=False),
    ]


def _run(code: str, **context) -> dict:
    SafeAstInterpreter().execute(code, context)
    return context


def test_list_comprehension_filters_objects():
    # Act
    ctx = _run("present = [n.id for n in npcs if not n.is_hidden]", npcs=_npcs())

    # Assert
    assert ctx["present"] == ["GUARD", "COOK"]


def test_generator_expression_works_with_any():
    # Act
    ctx = _run("guard_here = any(n.id == 'GUARD' for n in npcs)", npcs=_npcs())

    # Assert
    assert ctx["guard_here"] is True


def test_dict_set_and_nested_comprehensions():
    # Arrange
    code = (
        "by_id = {n.id: n.is_hidden for n in npcs}\n"
        "letters = {n.id[0] for n in npcs}\n"
        "pairs = [(a, b) for a in range(3) for b in range(a)]"
    )

    # Act
    ctx = _run(code, npcs=_npcs())

    # Assert
    assert ctx["by_id"] == {"GUARD": False, "THIEF": True, "COOK": False}
    assert ctx["letters"] == {"G", "T", "C"}
    assert ctx["pairs"] == [(1, 0), (2, 0), (2, 1)]


def test_loop_variable_does_not_leak_into_the_script():
    # Act
    ctx = _run("n = 'outer'\nids = [n.id for n in npcs]", npcs=_npcs())

    # Assert
    assert ctx["n"] == "outer"
    assert ctx["ids"] == ["GUARD", "THIEF", "COOK"]


def test_comprehension_reads_function_locals():
    # Arrange
    code = (
        "def visible(prefix):\n"
        "    return [prefix + n.id for n in npcs if not n.is_hidden]\n"
        "result = visible('npc:')"
    )

    # Act
    ctx = _run(code, npcs=_npcs())

    # Assert
    assert ctx["result"] == ["npc:GUARD", "npc:COOK"]


def test_guard_expression_accepts_a_generator_expression():
    # Arrange
    interpreter = SafeAstInterpreter()

    # Act
    allowed = interpreter.evaluate_expression(
        "any(item == 'KEY' for item in inventory)", {"inventory": ["MAP", "KEY"]}
    )

    # Assert
    assert allowed is True


def test_check_syntax_accepts_comprehensions():
    # Act
    errors = SafeAstInterpreter.check_syntax(
        "a = [x for x in range(3)]\nb = {x: x for x in a}\nc = sum(x for x in a)"
    )

    # Assert
    assert errors == []


def test_comprehension_counts_against_the_step_limit():
    # Arrange
    interpreter = SafeAstInterpreter(max_steps=500)

    # Act / Assert
    with pytest.raises(ScriptTimeoutError):
        interpreter.execute("big = [x for x in range(10000)]", {})


def test_comprehension_respects_the_size_limit():
    # Arrange
    interpreter = SafeAstInterpreter()
    interpreter.max_sequence_length = 5

    # Act / Assert
    with pytest.raises(ScriptSecurityError, match="size limit"):
        interpreter.execute("big = [x for x in range(10)]", {})


def test_comprehension_rejects_private_loop_variables():
    # Act / Assert
    with pytest.raises(ScriptSecurityError):
        SafeAstInterpreter().execute("x = [_n for _n in range(3)]", {})


def test_comprehension_over_a_non_iterable_fails_cleanly():
    # Act / Assert
    with pytest.raises(ScriptExecutionError, match="not iterable"):
        SafeAstInterpreter().execute("x = [n for n in 5]", {})
