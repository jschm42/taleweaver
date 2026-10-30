"""List, set and dict comprehensions and generator expressions for the script sandbox.

Every form is evaluated eagerly inside the interpreter: each element costs a step and the
result obeys the sequence size limit. A generator expression therefore becomes a list, so
no lazy code can run after the script's time budget ended or inside a host function.
Loop variables live in their own scope and do not leak into the script, as in Python 3.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from typing import Any

from backend.engine.scripting.sandbox_errors import ScriptExecutionError, ScriptSecurityError


class ComprehensionMixin:
    """Comprehension handlers for ``SafeAstInterpreter`` (dispatched as ``_eval_<Node>``)."""

    env: dict[str, Any]
    max_sequence_length: int
    _tick: Callable[[], None]
    _eval_expr: Callable[[ast.expr], Any]
    _assign_target: Callable[[ast.AST, Any], None]

    def _eval_ListComp(self, expr: ast.ListComp) -> list[Any]:
        result: list[Any] = []
        self._comprehend(expr.generators, lambda: result.append(self._eval_expr(expr.elt)), result)
        return result

    def _eval_GeneratorExp(self, expr: ast.GeneratorExp) -> list[Any]:
        result: list[Any] = []
        self._comprehend(expr.generators, lambda: result.append(self._eval_expr(expr.elt)), result)
        return result

    def _eval_SetComp(self, expr: ast.SetComp) -> set[Any]:
        result: set[Any] = set()
        self._comprehend(expr.generators, lambda: result.add(self._eval_expr(expr.elt)), result)
        return result

    def _eval_DictComp(self, expr: ast.DictComp) -> dict[Any, Any]:
        result: dict[Any, Any] = {}

        def emit() -> None:
            key = self._eval_expr(expr.key)
            result[key] = self._eval_expr(expr.value)

        self._comprehend(expr.generators, emit, result)
        return result

    def _comprehend(
        self, generators: list[ast.comprehension], emit: Callable[[], None], result: Any
    ) -> None:
        """Runs ``emit`` once per element in a private scope, enforcing the size limit."""

        def emit_checked() -> None:
            if len(result) >= self.max_sequence_length:
                raise ScriptSecurityError(
                    f"Comprehension exceeds safe size limit of {self.max_sequence_length} elements."
                )
            emit()

        outer_env = self.env
        self.env = dict(outer_env)
        try:
            self._for_each_binding(generators, 0, emit_checked)
        finally:
            self.env = outer_env

    def _for_each_binding(
        self, generators: list[ast.comprehension], index: int, emit: Callable[[], None]
    ) -> None:
        if index == len(generators):
            emit()
            return
        generator = generators[index]
        if generator.is_async:
            raise ScriptSecurityError("Async comprehensions are not allowed in sandbox.")
        for item in self._iterate(self._eval_expr(generator.iter)):
            self._tick()
            self._assign_target(generator.target, item)
            if self._passes_filters(generator):
                self._for_each_binding(generators, index + 1, emit)

    def _passes_filters(self, generator: ast.comprehension) -> bool:
        return all(self._eval_expr(condition) for condition in generator.ifs)

    @staticmethod
    def _iterate(iterable: Any) -> Any:
        try:
            return iter(iterable)
        except TypeError as exc:
            raise ScriptExecutionError(f"'{type(iterable).__name__}' is not iterable") from exc
