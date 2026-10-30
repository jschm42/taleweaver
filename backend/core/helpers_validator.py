"""Static checks for scene helper blocks (``helpers_script``).

Like the global ``init_script`` definitions, a helper block is re-read on every script run and
only its ``def`` statements and constant assignments are loaded. Anything else in it never
runs, and two blocks defining the same name shadow each other, so both are flagged.
"""

from __future__ import annotations

import ast
from typing import Any, Optional

from backend.schemas.validation import ValidationFinding

_CONSTANT_NODES = (ast.Constant, ast.List, ast.Tuple, ast.Dict)


def _parse(code: Any) -> Optional[ast.Module]:
    if not isinstance(code, str) or not code.strip():
        return None
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _is_definition(stmt: ast.stmt) -> bool:
    """Mirrors ``ScriptRunner.load_init_definitions``: functions and constant assignments."""
    if isinstance(stmt, ast.FunctionDef):
        return True
    return isinstance(stmt, ast.Assign) and isinstance(stmt.value, _CONSTANT_NODES)


def _names(stmt: ast.stmt) -> list[str]:
    if isinstance(stmt, ast.FunctionDef):
        return [stmt.name]
    if isinstance(stmt, ast.Assign):
        return [t.id for t in stmt.targets if isinstance(t, ast.Name)]
    return []


def definition_names(code: Any) -> set[str]:
    """Function and constant names a definition block puts into every script run."""
    tree = _parse(code)
    if tree is None:
        return set()
    return {name for stmt in tree.body if _is_definition(stmt) for name in _names(stmt)}


def scene_helper_blocks(scenes: list[Any]) -> list[tuple[str, str]]:
    """``(scene_id, code)`` of every scene with a non-empty helper block."""
    blocks: list[tuple[str, str]] = []
    for scene in scenes or []:
        if not isinstance(scene, dict):
            continue
        code = scene.get("helpers_script")
        if isinstance(code, str) and code.strip():
            blocks.append((str(scene.get("id") or "?"), code))
    return blocks


def _ignored_statement_findings(scene_id: str, code: str) -> list[ValidationFinding]:
    tree = _parse(code)
    if tree is None:
        return []
    return [
        ValidationFinding(
            severity="warn",
            code="helpers_statement_ignored",
            message=(
                f"Scene '{scene_id}' helpers, line {stmt.lineno}: only 'def' statements and "
                "constant assignments are loaded; this statement never runs. Move it into a "
                "trigger script (e.g. on_enter_scene)."
            ),
            location=f"scene:{scene_id}",
            context={"scene_id": scene_id, "field": "helpers_script", "line": stmt.lineno},
        )
        for stmt in tree.body
        if not _is_definition(stmt)
    ]


def _conflict_findings(blocks: list[tuple[str, str]], init_script: Any) -> list[ValidationFinding]:
    owners: dict[str, str] = {name: "init_script" for name in definition_names(init_script)}
    findings: list[ValidationFinding] = []
    for scene_id, code in blocks:
        source = f"scene '{scene_id}' helpers"
        for name in sorted(definition_names(code)):
            previous = owners.get(name)
            owners[name] = source
            if previous is None:
                continue
            findings.append(
                ValidationFinding(
                    severity="warn",
                    code="helper_name_conflict",
                    message=(
                        f"'{name}' is defined in {previous} and again in {source}; "
                        f"every script uses the one from {source}. Rename one of them."
                    ),
                    location=f"scene:{scene_id}",
                    context={"scene_id": scene_id, "name": name, "shadowed": previous},
                )
            )
    return findings


def check_scene_helpers(scenes: list[Any], init_script: Any) -> list[ValidationFinding]:
    """Warns about helper statements that never run and names defined twice."""
    blocks = scene_helper_blocks(scenes)
    findings: list[ValidationFinding] = []
    for scene_id, code in blocks:
        findings.extend(_ignored_statement_findings(scene_id, code))
    findings.extend(_conflict_findings(blocks, init_script))
    return findings
