"""
TaleWeaver Sandboxed Scripting Engine.

Provides secure AST-level execution of adventure scripts without access
to CPython bytecode, private object internals, or host system sinks.
"""

from __future__ import annotations

import ast
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from backend.engine.scripting.sandbox_comprehensions import ComprehensionMixin
from backend.engine.scripting.sandbox_errors import (
    ScriptExecutionError,
    ScriptSecurityError,
    ScriptTimeoutError,
)

logger = logging.getLogger(__name__)

# The interpreter currently evaluating a script, so host calls can adjust its time budget.
_ACTIVE_INTERPRETER: ContextVar[Any] = ContextVar("tw_active_interpreter", default=None)
# True while a guard expression (not a script) is evaluated; guards must stay deterministic.
_EXPRESSION_MODE: ContextVar[bool] = ContextVar("tw_expression_mode", default=False)


def in_guard_expression() -> bool:
    """True while the sandbox evaluates a guard expression rather than running a script."""
    return _EXPRESSION_MODE.get()


def refund_time_budget(seconds: float) -> None:
    """Gives the running script back wall-clock time spent waiting on a host call (e.g. an LLM)."""
    interpreter = _ACTIVE_INTERPRETER.get()
    if interpreter is not None and seconds > 0:
        interpreter.deadline += seconds


class _ReturnSignalError(Exception):
    """Internal control-flow signal raised by return statements inside functions."""

    def __init__(self, value: Any = None):
        self.value = value


# Whitelist of allowed AST statement and expression nodes
ALLOWED_AST_NODES: set[type[ast.AST]] = {
    # Module & Structure
    ast.Module,
    ast.Expression,
    ast.Expr,
    ast.Pass,
    # Statements
    ast.Assign,
    ast.AugAssign,
    ast.If,
    ast.For,
    ast.Break,
    ast.Continue,
    ast.FunctionDef,
    ast.Return,
    ast.arguments,
    ast.arg,
    # Expressions & Values
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.UnaryOp,
    ast.UAdd,
    ast.USub,
    ast.Not,
    ast.Invert,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.Call,
    ast.keyword,
    ast.Attribute,
    ast.Subscript,
    ast.Slice,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.FormattedValue,
    ast.JoinedStr,
    ast.Lambda,
    ast.IfExp,
    # Comprehensions (evaluated eagerly, see sandbox_comprehensions)
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
}

# Resource limits. Adventure scripts may come from imported (untrusted) adventures, so a
# single script must not be able to exhaust server memory or CPU.
MAX_SEQUENCE_LENGTH = 100_000
MAX_RANGE_LENGTH = 100_000
MAX_INT_BITS = 10_000
MAX_WALL_SECONDS = 2.0
_WALL_CHECK_INTERVAL = 256

# Attribute names that let format strings or introspection reach interpreter internals
# (e.g. ``"{0.__init__.__globals__}".format(obj)`` or generator/frame objects).
_FORBIDDEN_ATTRIBUTES = frozenset({"format", "format_map", "mro"})
_FORBIDDEN_ATTRIBUTE_PREFIXES = ("_", "gi_", "cr_", "ag_", "f_", "tb_", "co_")
_SIZE_SENSITIVE_TYPES = (str, bytes, list, tuple)


def attribute_violation(name: str) -> str | None:
    """Returns why an attribute name is off-limits for scripts, or None if it is allowed."""
    if name.startswith("_"):
        return f"Access to private/dunder attribute '{name}' is forbidden."
    if name in _FORBIDDEN_ATTRIBUTES or name.startswith(_FORBIDDEN_ATTRIBUTE_PREFIXES):
        return f"Access to attribute '{name}' is forbidden in sandbox."
    return None


def _reject_method_overwrite(obj: Any, target: ast.Attribute) -> None:
    """Stops ``npc.add_trait = "angry"``, which would silently replace the method instead of
    calling it. Properties with setters (``npc.character = ...``) stay assignable."""
    if not callable(getattr(type(obj), target.attr, None)):
        return
    owner = target.value.id if isinstance(target.value, ast.Name) else "obj"
    raise ScriptExecutionError(
        f"'{target.attr}' is a method and cannot be assigned. "
        f"Call it instead: {owner}.{target.attr}(...)"
    )


def _check_sequence_size(value: Any) -> Any:
    if isinstance(value, (*_SIZE_SENSITIVE_TYPES, dict)) and len(value) > MAX_SEQUENCE_LENGTH:
        raise ScriptSecurityError(
            f"Value exceeds safe size limit of {MAX_SEQUENCE_LENGTH} elements/characters."
        )
    return value


def _check_int_size(value: Any) -> Any:
    if isinstance(value, int) and value.bit_length() > MAX_INT_BITS:
        raise ScriptSecurityError("Integer result exceeds safe size limit.")
    return value


def _safe_range(*args: Any) -> range:
    result = range(*args)
    if len(result) > MAX_RANGE_LENGTH:
        raise ScriptSecurityError(f"range() is limited to {MAX_RANGE_LENGTH} elements.")
    return result


def _safe_print(*args: Any, sep: str = " ", **_kwargs: Any) -> None:
    """Safe print implementation for sandbox scripts routing to server console logger."""
    msg = sep.join(str(a) for a in args)
    logger.info(f"[Script Print] {msg}")


# Safe built-in functions accessible to scripts
SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": _safe_print,
    "range": _safe_range,
    "round": round,
    "str": str,
    "sum": sum,
    "tuple": tuple,
}


def _inspect_ast_node(node: ast.AST) -> str | None:
    """Returns a security error string if the node violates sandbox rules, else None."""
    if type(node) not in ALLOWED_AST_NODES:
        return f"Forbidden syntax '{type(node).__name__}' is not allowed in sandbox."
    if isinstance(node, ast.Attribute):
        return attribute_violation(node.attr)
    if isinstance(node, ast.Name) and node.id.startswith("__"):
        return f"Use of dunder variable '{node.id}' is forbidden."
    if isinstance(node, ast.FunctionDef):
        if node.name.startswith("_"):
            return f"Cannot define private function '{node.name}'."
        for a in node.args.args:
            if a.arg.startswith("__"):
                return f"Use of dunder parameter name '{a.arg}' is forbidden."
    return None


def _safe_mult(left: Any, right: Any) -> Any:
    for seq, count in ((left, right), (right, left)):
        is_repeat = isinstance(seq, _SIZE_SENSITIVE_TYPES) and isinstance(count, int)
        if is_repeat and count * len(seq) > MAX_SEQUENCE_LENGTH:
            raise ScriptSecurityError("String/Sequence repetition exceeds safe memory limit.")
    both_int = isinstance(left, int) and isinstance(right, int)
    if both_int and left.bit_length() + right.bit_length() > MAX_INT_BITS:
        raise ScriptSecurityError("Integer multiplication exceeds safe size limit.")
    return left * right


def _safe_add(left: Any, right: Any) -> Any:
    sized = isinstance(left, _SIZE_SENSITIVE_TYPES) and isinstance(right, _SIZE_SENSITIVE_TYPES)
    if sized and len(left) + len(right) > MAX_SEQUENCE_LENGTH:
        raise ScriptSecurityError("Concatenation exceeds safe memory limit.")
    return left + right


def _safe_pow(left: Any, right: Any) -> Any:
    if isinstance(right, (int, float)) and right > 1000:
        raise ScriptSecurityError("Exponentiation exceeds safe limits.")
    is_int_pow = isinstance(left, int) and isinstance(right, int) and right > 0
    if is_int_pow and abs(left).bit_length() * right > MAX_INT_BITS:
        raise ScriptSecurityError("Exponentiation exceeds safe limits.")
    return left**right


_BINOPS: dict[type[ast.operator], Any] = {
    ast.Add: _safe_add,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: _safe_mult,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: _safe_pow,
}


def _guard_call_arguments(func: Any, args: list[Any], kwargs: dict[str, Any]) -> None:
    """Rejects calls on builtin sequences that would allocate huge results in one step."""
    owner = getattr(func, "__self__", None)
    if not isinstance(owner, _SIZE_SENSITIVE_TYPES):
        return
    for value in (*args, *kwargs.values()):
        if isinstance(value, int) and abs(value) > MAX_SEQUENCE_LENGTH:
            raise ScriptSecurityError("Argument exceeds safe size limit.")
    is_join = getattr(func, "__name__", "") == "join" and bool(args)
    if is_join and isinstance(args[0], (list, tuple)):
        total = sum(len(part) for part in args[0] if isinstance(part, _SIZE_SENSITIVE_TYPES))
        if total > MAX_SEQUENCE_LENGTH:
            raise ScriptSecurityError("join() result exceeds safe memory limit.")


class SafeAstInterpreter(ComprehensionMixin):
    """
    Pure Python AST interpreter for TaleWeaver scripts.
    Executes valid Python code within a bounded, isolated environment.
    """

    max_sequence_length = MAX_SEQUENCE_LENGTH

    def __init__(self, max_steps: int = 10000):
        self.max_steps = max_steps
        self.step_count = 0
        self.deadline = 0.0
        self.env: dict[str, Any] = {}

    def _start_budget(self) -> None:
        self.step_count = 0
        self.deadline = time.monotonic() + MAX_WALL_SECONDS

    def _tick(self) -> None:
        self.step_count += 1
        if self.step_count > self.max_steps:
            raise ScriptTimeoutError(
                f"Script execution exceeded maximum instruction limit of {self.max_steps} steps."
            )
        if self.step_count % _WALL_CHECK_INTERVAL == 0 and time.monotonic() > self.deadline:
            raise ScriptTimeoutError(
                f"Script execution exceeded the time limit of {MAX_WALL_SECONDS} seconds."
            )

    def validate_ast(self, tree: ast.AST) -> None:
        """
        Statically inspects the AST tree to ensure no forbidden nodes or attributes exist.
        """
        for node in ast.walk(tree):
            err = _inspect_ast_node(node)
            if err:
                raise ScriptSecurityError(err)

    @classmethod
    def check_syntax(cls, code: str) -> list[str]:
        """
        Statically parses and validates Python script code without running it.
        Returns a list of error strings (empty if valid).
        """
        if not code or not code.strip():
            return []

        errors: list[str] = []
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            msg = f"Syntax error at line {exc.lineno or 1}"
            if exc.offset:
                msg += f", col {exc.offset}"
            msg += f": {exc.msg}"
            return [msg]
        except Exception as exc:
            return [f"Parser error: {exc}"]

        for node in ast.walk(tree):
            err = _inspect_ast_node(node)
            if err:
                lineno = getattr(node, "lineno", "?")
                errors.append(f"Line {lineno}: {err}")

        return errors

    @classmethod
    def check_expression_syntax(cls, code: str) -> list[str]:
        """Statically parses and validates Python expression syntax without running it."""
        if not code or not code.strip():
            return []

        errors: list[str] = []
        try:
            tree = ast.parse(code.strip(), mode="eval")
        except SyntaxError as exc:
            msg = f"Syntax error at line {exc.lineno or 1}"
            if exc.offset:
                msg += f", col {exc.offset}"
            msg += f": {exc.msg}"
            return [msg]
        except Exception as exc:
            return [f"Parser error: {exc}"]

        for node in ast.walk(tree):
            err = _inspect_ast_node(node)
            if err:
                lineno = getattr(node, "lineno", "?")
                errors.append(f"Line {lineno}: {err}")

        return errors

    @contextmanager
    def _active(self, expression: bool) -> Iterator[None]:
        """Marks this interpreter as running (and whether it evaluates a guard expression)."""
        interpreter_token = _ACTIVE_INTERPRETER.set(self)
        mode_token = _EXPRESSION_MODE.set(expression)
        try:
            yield
        finally:
            _EXPRESSION_MODE.reset(mode_token)
            _ACTIVE_INTERPRETER.reset(interpreter_token)

    def execute(self, code: str, context: dict[str, Any]) -> None:
        """
        Parses, validates, and executes the script within the provided context.
        """
        with self._active(expression=False):
            self._execute(code, context)

    def evaluate_expression(self, expr_str: str, context: dict[str, Any]) -> Any:
        """
        Parses, validates, and evaluates a Python expression string within the given context.
        """
        with self._active(expression=True):
            return self._evaluate_expression(expr_str, context)

    def _execute(self, code: str, context: dict[str, Any]) -> None:
        self._start_budget()
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise ScriptExecutionError(f"Syntax error in script: {exc}") from exc

        self.validate_ast(tree)

        # Build initial environment
        self.env = {**SAFE_BUILTINS, **context}

        try:
            for stmt in tree.body:
                self._eval_stmt(stmt)
        except _ReturnSignalError:
            raise ScriptExecutionError("SyntaxError: 'return' outside function") from None

        # Sync back created/modified variables to caller context
        for k, v in self.env.items():
            if k not in SAFE_BUILTINS:
                context[k] = v

    def _evaluate_expression(self, expr_str: str, context: dict[str, Any]) -> Any:
        self._start_budget()
        try:
            tree = ast.parse(expr_str.strip(), mode="eval")
        except SyntaxError as exc:
            raise ScriptExecutionError(f"Syntax error in expression: {exc}") from exc

        self.validate_ast(tree)
        self.env = {**SAFE_BUILTINS, **context}
        return self._eval_expr(tree.body)

    # -------------------------------------------------------------------------
    # Statement Handlers
    # -------------------------------------------------------------------------

    def _eval_stmt(self, stmt: ast.stmt) -> Any:
        self._tick()
        method_name = f"_eval_{type(stmt).__name__}"
        handler = getattr(self, method_name, None)
        if handler is None:
            raise ScriptSecurityError(f"Unsupported statement: {type(stmt).__name__}")
        return handler(stmt)

    def _eval_Expr(self, stmt: ast.Expr) -> Any:
        return self._eval_expr(stmt.value)

    def _eval_Pass(self, stmt: ast.Pass) -> None:
        pass

    def _eval_Assign(self, stmt: ast.Assign) -> None:
        val = self._eval_expr(stmt.value)
        for target in stmt.targets:
            self._assign_target(target, val)

    def _eval_AugAssign(self, stmt: ast.AugAssign) -> None:
        current_val = self._eval_expr(stmt.target)
        right_val = self._eval_expr(stmt.value)
        new_val = self._apply_binop(stmt.op, current_val, right_val)
        self._assign_target(stmt.target, new_val)

    def _eval_If(self, stmt: ast.If) -> None:
        test_val = self._eval_expr(stmt.test)
        if bool(test_val):
            for s in stmt.body:
                res = self._eval_stmt(s)
                if res in ("break", "continue"):
                    return res
        else:
            for s in stmt.orelse:
                res = self._eval_stmt(s)
                if res in ("break", "continue"):
                    return res

    def _eval_For(self, stmt: ast.For) -> None:
        iterable = self._eval_expr(stmt.iter)
        try:
            it = iter(iterable)
        except TypeError as exc:
            raise ScriptExecutionError(f"'{type(iterable).__name__}' is not iterable") from exc

        for item in it:
            self._tick()
            self._assign_target(stmt.target, item)
            should_break = False
            for s in stmt.body:
                res = self._eval_stmt(s)
                if res == "break":
                    should_break = True
                    break
                elif res == "continue":
                    break
            if should_break:
                break
        else:
            for s in stmt.orelse:
                self._eval_stmt(s)

    def _eval_Break(self, stmt: ast.Break) -> str:
        return "break"

    def _eval_Continue(self, stmt: ast.Continue) -> str:
        return "continue"

    def _eval_Return(self, stmt: ast.Return) -> None:
        self._tick()
        val = self._eval_expr(stmt.value) if stmt.value is not None else None
        raise _ReturnSignalError(val)

    @staticmethod
    def _bind_call_args(
        param_names: list[str],
        defaults_map: dict[str, Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        func_name: str,
    ) -> dict[str, Any]:
        bound: dict[str, Any] = {}
        for i, pname in enumerate(param_names):
            if i < len(args):
                bound[pname] = args[i]
                continue
            if pname in kwargs:
                bound[pname] = kwargs[pname]
                continue
            if pname in defaults_map:
                bound[pname] = defaults_map[pname]
                continue
            raise ScriptExecutionError(
                f"Missing required argument '{pname}' in function '{func_name}'"
            )
        return bound

    def _eval_FunctionDef(self, stmt: ast.FunctionDef) -> None:
        self._tick()
        func_name = stmt.name
        if func_name.startswith("_"):
            raise ScriptSecurityError(f"Cannot define private function '{func_name}'")

        param_names = [a.arg for a in stmt.args.args]
        for pname in param_names:
            if pname.startswith("__"):
                raise ScriptSecurityError(f"Use of dunder parameter '{pname}' is forbidden")

        default_values = [self._eval_expr(d) for d in stmt.args.defaults]
        defaults_map: dict[str, Any] = {}
        if default_values:
            for pname, def_val in zip(
                param_names[-len(default_values) :], default_values, strict=False
            ):
                defaults_map[pname] = def_val

        closure_env = dict(self.env)
        body = stmt.body

        def sandbox_function(*args: Any, **kwargs: Any) -> Any:
            self._tick()
            call_env = dict(closure_env)
            for k, v in self.env.items():
                if k not in call_env or k in ("tw", "game"):
                    call_env[k] = v

            bound = self._bind_call_args(param_names, defaults_map, args, kwargs, func_name)
            call_env.update(bound)

            old_env = self.env
            self.env = call_env
            try:
                for s in body:
                    self._eval_stmt(s)
                return None
            except _ReturnSignalError as ret:
                return ret.value
            finally:
                for k in ("tw", "game"):
                    if k in self.env:
                        old_env[k] = self.env[k]
                self.env = old_env

        # Lets APIs that store a callback by name (e.g. tw.dialog on_choice) accept the function.
        sandbox_function.__name__ = func_name
        self.env[func_name] = sandbox_function

    # -------------------------------------------------------------------------
    # Target Assignment
    # -------------------------------------------------------------------------

    def _assign_target(self, target: ast.AST, val: Any) -> None:
        if isinstance(target, ast.Name):
            if target.id.startswith("_"):
                raise ScriptSecurityError(f"Cannot assign to private variable '{target.id}'")
            self.env[target.id] = val
        elif isinstance(target, ast.Attribute):
            obj = self._eval_expr(target.value)
            violation = attribute_violation(target.attr)
            if violation:
                raise ScriptSecurityError(violation)
            _reject_method_overwrite(obj, target)
            setattr(obj, target.attr, val)
        elif isinstance(target, ast.Subscript):
            container = self._eval_expr(target.value)
            key = self._eval_expr(target.slice)
            container[key] = val
        elif isinstance(target, (ast.Tuple, ast.List)):
            try:
                items = list(val)
            except TypeError as exc:
                raise ScriptExecutionError(
                    f"Cannot unpack non-iterable '{type(val).__name__}'"
                ) from exc
            if len(items) != len(target.elts):
                raise ScriptExecutionError(
                    f"ValueError: too many/few values to unpack (expected {len(target.elts)}, got {len(items)})"
                )
            for sub_target, sub_val in zip(target.elts, items, strict=True):
                self._assign_target(sub_target, sub_val)
        else:
            raise ScriptSecurityError(f"Unsupported assignment target: {type(target).__name__}")

    # -------------------------------------------------------------------------
    # Expression Handlers
    # -------------------------------------------------------------------------

    def _eval_expr(self, expr: ast.expr) -> Any:
        self._tick()
        if isinstance(expr, ast.JoinedStr):
            return self._eval_joined_str(expr)
        if isinstance(expr, ast.FormattedValue):
            return self._eval_formatted_value(expr)
        method_name = f"_eval_{type(expr).__name__}"
        handler = getattr(self, method_name, None)
        if handler is None:
            raise ScriptSecurityError(f"Unsupported expression: {type(expr).__name__}")
        return handler(expr)

    def _eval_Constant(self, expr: ast.Constant) -> Any:
        return expr.value

    def _eval_Name(self, expr: ast.Name) -> Any:
        name = expr.id
        if name in self.env:
            return self.env[name]
        raise ScriptExecutionError(f"NameError: name '{name}' is not defined")

    def _eval_UnaryOp(self, expr: ast.UnaryOp) -> Any:
        val = self._eval_expr(expr.operand)
        if isinstance(expr.op, ast.UAdd):
            return +val
        if isinstance(expr.op, ast.USub):
            return -val
        if isinstance(expr.op, ast.Not):
            return not val
        if isinstance(expr.op, ast.Invert):
            return ~val
        raise ScriptExecutionError(f"Unsupported unary operator: {type(expr.op).__name__}")

    def _eval_BinOp(self, expr: ast.BinOp) -> Any:
        left = self._eval_expr(expr.left)
        right = self._eval_expr(expr.right)
        return self._apply_binop(expr.op, left, right)

    def _apply_binop(self, op: ast.operator, left: Any, right: Any) -> Any:
        handler = _BINOPS.get(type(op))
        if handler is None:
            raise ScriptExecutionError(f"Unsupported binary operator: {type(op).__name__}")
        return _check_int_size(_check_sequence_size(handler(left, right)))

    def _eval_BoolOp(self, expr: ast.BoolOp) -> Any:
        if isinstance(expr.op, ast.And):
            val: Any = True
            for v in expr.values:
                val = self._eval_expr(v)
                if not val:
                    return val
            return val
        if isinstance(expr.op, ast.Or):
            val = False
            for v in expr.values:
                val = self._eval_expr(v)
                if val:
                    return val
            return val
        raise ScriptExecutionError(f"Unsupported boolean operator: {type(expr.op).__name__}")

    def _eval_Compare(self, expr: ast.Compare) -> bool:
        left = self._eval_expr(expr.left)
        for op, comparator in zip(expr.ops, expr.comparators, strict=True):
            right = self._eval_expr(comparator)
            res = self._apply_compare(op, left, right)
            if not res:
                return False
            left = right
        return True

    def _apply_compare(self, op: ast.cmpop, left: Any, right: Any) -> bool:
        if isinstance(op, ast.Eq):
            return bool(left == right)
        if isinstance(op, ast.NotEq):
            return bool(left != right)
        if isinstance(op, ast.Lt):
            return bool(left < right)
        if isinstance(op, ast.LtE):
            return bool(left <= right)
        if isinstance(op, ast.Gt):
            return bool(left > right)
        if isinstance(op, ast.GtE):
            return bool(left >= right)
        if isinstance(op, ast.Is):
            return bool(left is right)
        if isinstance(op, ast.IsNot):
            return bool(left is not right)
        if isinstance(op, ast.In):
            return bool(left in right)
        if isinstance(op, ast.NotIn):
            return bool(left not in right)
        raise ScriptExecutionError(f"Unsupported comparison: {type(op).__name__}")

    def _eval_Call(self, expr: ast.Call) -> Any:
        func = self._eval_expr(expr.func)
        args = [self._eval_expr(arg) for arg in expr.args]
        kwargs = {kw.arg: self._eval_expr(kw.value) for kw in expr.keywords if kw.arg is not None}
        if not callable(func):
            raise ScriptExecutionError(f"'{type(func).__name__}' object is not callable")
        _guard_call_arguments(func, args, kwargs)
        return _check_int_size(_check_sequence_size(func(*args, **kwargs)))

    def _eval_Attribute(self, expr: ast.Attribute) -> Any:
        violation = attribute_violation(expr.attr)
        if violation:
            raise ScriptSecurityError(violation)
        obj = self._eval_expr(expr.value)
        try:
            return getattr(obj, expr.attr)
        except AttributeError as exc:
            raise ScriptExecutionError(f"AttributeError: {exc}") from exc

    def _eval_Subscript(self, expr: ast.Subscript) -> Any:
        val = self._eval_expr(expr.value)
        idx = self._eval_expr(expr.slice)
        try:
            return val[idx]
        except (IndexError, KeyError, TypeError) as exc:
            raise ScriptExecutionError(f"Subscript error: {exc}") from exc

    def _eval_Slice(self, expr: ast.Slice) -> slice:
        lower = self._eval_expr(expr.lower) if expr.lower is not None else None
        upper = self._eval_expr(expr.upper) if expr.upper is not None else None
        step = self._eval_expr(expr.step) if expr.step is not None else None
        return slice(lower, upper, step)

    def _eval_List(self, expr: ast.List) -> list[Any]:
        return [self._eval_expr(elt) for elt in expr.elts]

    def _eval_Tuple(self, expr: ast.Tuple) -> tuple[Any, ...]:
        return tuple(self._eval_expr(elt) for elt in expr.elts)

    def _eval_Dict(self, expr: ast.Dict) -> dict[Any, Any]:
        return {
            self._eval_expr(k): self._eval_expr(v)
            for k, v in zip(expr.keys, expr.values, strict=False)
            if k is not None
        }

    def _eval_Lambda(self, expr: ast.Lambda) -> Any:
        self._tick()
        param_names = [a.arg for a in expr.args.args]
        default_values = [self._eval_expr(d) for d in expr.args.defaults]
        defaults_map: dict[str, Any] = {}
        if default_values:
            for pname, def_val in zip(
                param_names[-len(default_values) :], default_values, strict=False
            ):
                defaults_map[pname] = def_val

        closure_env = dict(self.env)
        body = expr.body

        def sandbox_lambda(*args: Any, **kwargs: Any) -> Any:
            self._tick()
            call_env = dict(closure_env)
            for k, v in self.env.items():
                if k not in call_env or k in ("tw", "game"):
                    call_env[k] = v

            bound = self._bind_call_args(param_names, defaults_map, args, kwargs, "<lambda>")
            call_env.update(bound)

            old_env = self.env
            self.env = call_env
            try:
                return self._eval_expr(body)
            finally:
                for k in ("tw", "game"):
                    if k in self.env:
                        old_env[k] = self.env[k]
                self.env = old_env

        return sandbox_lambda

    def _eval_IfExp(self, expr: ast.IfExp) -> Any:
        if self._eval_expr(expr.test):
            return self._eval_expr(expr.body)
        return self._eval_expr(expr.orelse)

    def _eval_joined_str(self, expr: ast.JoinedStr) -> str:
        parts = []
        for val in expr.values:
            parts.append(str(self._eval_expr(val)))
        return _check_sequence_size("".join(parts))

    def _eval_formatted_value(self, expr: ast.FormattedValue) -> str:
        val = self._eval_expr(expr.value)
        return str(val)

    # Aliases matching ast class names for dispatch
    _eval_JoinedStr = _eval_joined_str
    _eval_FormattedValue = _eval_formatted_value
