"""Regression tests for sandbox escapes and resource exhaustion vectors."""

import pytest

from backend.engine.scripting.context import PlayerProxy, ScriptChangeset
from backend.engine.scripting.sandbox import (
    SafeAstInterpreter,
    ScriptSecurityError,
    ScriptTimeoutError,
)


def _run(code: str, context: dict | None = None) -> dict:
    ctx = dict(context or {})
    SafeAstInterpreter().execute(code, ctx)
    return ctx


@pytest.mark.parametrize(
    "code",
    [
        'out = "{0.heal.__func__.__globals__}".format(p)',
        'out = str.format("{0.__class__}", p)',
        'out = "{x}".format_map({"x": p})',
        "out = str.mro()",
        "out = p.heal.f_globals",
    ],
)
def test_introspection_escapes_are_blocked(code):
    # Arrange
    player = PlayerProxy({"hp": 10}, ScriptChangeset())

    # Act / Assert
    with pytest.raises(ScriptSecurityError):
        _run(code, {"p": player})


@pytest.mark.parametrize(
    "code",
    [
        'out = 10000000 * "ab"',
        's = "x" * 100000\nfor i in range(12):\n    s = s + s',
        "out = list(range(30000000))",
        "x = 10 ** 1000\nx = x ** 1000",
        'out = "x".ljust(500000000)',
        'parts = ["y" * 90000, "y" * 90000]\nout = "".join(parts)',
    ],
)
def test_resource_exhaustion_is_blocked(code):
    # Act / Assert
    with pytest.raises(ScriptSecurityError):
        _run(code)


def test_infinite_work_hits_step_budget():
    # Act / Assert
    with pytest.raises(ScriptTimeoutError):
        _run("total = 0\nfor i in range(100000):\n    for j in range(100000):\n        total += 1")


def test_regular_scripts_still_work():
    # Arrange
    code = (
        "names = ['a', 'b']\n"
        "label = 'many' if len(names) > 1 else 'one'\n"
        "msg = f'{label}: ' + ', '.join(names)\n"
        "total = sum(range(10)) * 2"
    )

    # Act
    ctx = _run(code)

    # Assert
    assert ctx["msg"] == "many: a, b"
    assert ctx["total"] == 90
