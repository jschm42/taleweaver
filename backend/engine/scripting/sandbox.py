"""
TaleWeaver Sandboxed Scripting Engine.

Provides secure AST-level execution of adventure scripts without access
to CPython bytecode, private object internals, or host system sinks.
"""
from __future__ import annotations

import ast
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ScriptSecurityError(Exception):
    """Raised when a script attempts an unauthorized or unsafe operation."""
    pass


class ScriptExecutionError(Exception):
    """Raised when a runtime error occurs during script evaluation."""
    pass


class ScriptTimeoutError(ScriptExecutionError):
    """Raised when a script exceeds its maximum execution instruction budget."""
    pass


# Whitelist of allowed AST statement and expression nodes
ALLOWED_AST_NODES: set[type[ast.AST]] = {
    # Module & Structure
    ast.Module,
    ast.Expr,
    ast.Pass,
    # Statements
    ast.Assign,
    ast.AugAssign,
    ast.If,
    ast.For,
    ast.Break,
    ast.Continue,
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
}

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
    "range": range,
    "round": round,
    "str": str,
    "sum": sum,
    "tuple": tuple,
}


class SafeAstInterpreter:
    """
    Pure Python AST interpreter for TaleWeaver scripts.
    Executes valid Python code within a bounded, isolated environment.
    """

    def __init__(self, max_steps: int = 10000):
        self.max_steps = max_steps
        self.step_count = 0
        self.env: dict[str, Any] = {}

    def _tick(self) -> None:
        self.step_count += 1
        if self.step_count > self.max_steps:
            raise ScriptTimeoutError(
                f"Script execution exceeded maximum instruction limit of {self.max_steps} steps."
            )

    def validate_ast(self, tree: ast.AST) -> None:
        """
        Statically inspects the AST tree to ensure no forbidden nodes or attributes exist.
        """
        for node in ast.walk(tree):
            if type(node) not in ALLOWED_AST_NODES:
                raise ScriptSecurityError(
                    f"Forbidden syntax in script: '{type(node).__name__}' is not allowed."
                )

            # Prevent private/dunder attribute access (e.g. __class__, __subclasses__)
            if isinstance(node, ast.Attribute):
                if node.attr.startswith("_"):
                    raise ScriptSecurityError(
                        f"Access to private/internal attribute '{node.attr}' is forbidden."
                    )

            # Prevent private variable binding
            if isinstance(node, ast.Name):
                if node.id.startswith("__"):
                    raise ScriptSecurityError(
                        f"Use of dunder variable name '{node.id}' is forbidden."
                    )

    def execute(self, code: str, context: dict[str, Any]) -> None:
        """
        Parses, validates, and executes the script within the provided context.
        """
        self.step_count = 0
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise ScriptExecutionError(f"Syntax error in script: {exc}") from exc

        self.validate_ast(tree)

        # Build initial environment
        self.env = {**SAFE_BUILTINS, **context}

        for stmt in tree.body:
            self._eval_stmt(stmt)

        # Sync back created/modified variables to caller context
        for k, v in self.env.items():
            if k not in SAFE_BUILTINS:
                context[k] = v

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
            if target.attr.startswith("_"):
                raise ScriptSecurityError(f"Cannot set private attribute '{target.attr}'")
            setattr(obj, target.attr, val)
        elif isinstance(target, ast.Subscript):
            container = self._eval_expr(target.value)
            key = self._eval_expr(target.slice)
            container[key] = val
        elif isinstance(target, (ast.Tuple, ast.List)):
            try:
                items = list(val)
            except TypeError as exc:
                raise ScriptExecutionError(f"Cannot unpack non-iterable '{type(val).__name__}'") from exc
            if len(items) != len(target.elts):
                raise ScriptExecutionError(
                    f"ValueError: too many/few values to unpack (expected {len(target.elts)}, got {len(items)})"
                )
            for sub_target, sub_val in zip(target.elts, items):
                self._assign_target(sub_target, sub_val)
        else:
            raise ScriptSecurityError(f"Unsupported assignment target: {type(target).__name__}")

    # -------------------------------------------------------------------------
    # Expression Handlers
    # -------------------------------------------------------------------------

    def _eval_expr(self, expr: ast.expr) -> Any:
        self._tick()
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
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            # Guard against huge string/list memory multiplication
            if isinstance(left, (str, list, tuple)) and isinstance(right, int):
                if right * len(left) > 100000:
                    raise ScriptSecurityError("String/Sequence repetition exceeds safe memory limit.")
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Mod):
            return left % right
        if isinstance(op, ast.Pow):
            if isinstance(right, (int, float)) and right > 1000:
                raise ScriptSecurityError("Exponentiation exceeds safe limits.")
            return left ** right
        raise ScriptExecutionError(f"Unsupported binary operator: {type(op).__name__}")

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
        for op, comparator in zip(expr.ops, expr.comparators):
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
        return func(*args, **kwargs)

    def _eval_Attribute(self, expr: ast.Attribute) -> Any:
        if expr.attr.startswith("_"):
            raise ScriptSecurityError(f"Access to private attribute '{expr.attr}' is forbidden.")
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
            for k, v in zip(expr.keys, expr.values)
            if k is not None
        }

    def _eval_JoinedStr(self, expr: ast.JoinedStr) -> str:
        parts = []
        for val in expr.values:
            parts.append(str(self._eval_expr(val)))
        return "".join(parts)

    def _eval_FormattedValue(self, expr: ast.FormattedValue) -> str:
        val = self._eval_expr(expr.value)
        return str(val)
