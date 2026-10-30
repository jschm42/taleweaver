"""Static checks for sequence and scene helper blocks (``helpers_script``).

Like the global ``init_script`` definitions, a helper block is re-read on every script run and
only its ``def`` statements and constant assignments are loaded. Anything else in it never
runs, and two blocks defining the same name shadow each other, so both are flagged.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
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


@dataclass(frozen=True)
class HelperBlock:
    """A ``helpers_script`` of a sequence or a scene."""

    kind: str  # "sequence" or "scene"
    owner_id: str
    code: str

    @property
    def label(self) -> str:
        return f"{self.kind} '{self.owner_id}' helpers"

    @property
    def location(self) -> str:
        return f"{self.kind}:{self.owner_id}"


def _owner_blocks(kind: str, owners: Any) -> list[HelperBlock]:
    blocks: list[HelperBlock] = []
    for owner in owners or []:
        if not isinstance(owner, dict):
            continue
        code = owner.get("helpers_script")
        if isinstance(code, str) and code.strip():
            blocks.append(HelperBlock(kind, str(owner.get("id") or "?"), code))
    return blocks


def _order(sequence: Any) -> int:
    order = sequence.get("order") if isinstance(sequence, dict) else None
    return order if isinstance(order, int) else 0


def helper_blocks(scenes: Any, sequences: Any = None) -> list[HelperBlock]:
    """Every non-empty helper block, in the runtime's load order: sequences, then scenes."""
    chapters = sorted(sequences, key=_order) if isinstance(sequences, list) else []
    return [*_owner_blocks("sequence", chapters), *_owner_blocks("scene", scenes)]


def _ignored_statement_findings(block: HelperBlock) -> list[ValidationFinding]:
    tree = _parse(block.code)
    if tree is None:
        return []
    hint = "on_enter_scene" if block.kind == "scene" else "on_start_sequence"
    return [
        ValidationFinding(
            severity="warn",
            code="helpers_statement_ignored",
            message=(
                f"{block.label[0].upper()}{block.label[1:]}, line {stmt.lineno}: only 'def' "
                "statements and constant assignments are loaded; this statement never runs. "
                f"Move it into a trigger script (e.g. {hint})."
            ),
            location=block.location,
            context={
                f"{block.kind}_id": block.owner_id,
                "field": "helpers_script",
                "line": stmt.lineno,
            },
        )
        for stmt in tree.body
        if not _is_definition(stmt)
    ]


def _conflict_findings(blocks: list[HelperBlock], init_script: Any) -> list[ValidationFinding]:
    owners: dict[str, str] = {name: "init_script" for name in definition_names(init_script)}
    findings: list[ValidationFinding] = []
    for block in blocks:
        for name in sorted(definition_names(block.code)):
            previous = owners.get(name)
            owners[name] = block.label
            if previous is None:
                continue
            findings.append(
                ValidationFinding(
                    severity="warn",
                    code="helper_name_conflict",
                    message=(
                        f"'{name}' is defined in {previous} and again in {block.label}; "
                        f"every script uses the one from {block.label}. Rename one of them."
                    ),
                    location=block.location,
                    context={
                        f"{block.kind}_id": block.owner_id,
                        "name": name,
                        "shadowed": previous,
                    },
                )
            )
    return findings


def check_helper_blocks(scenes: Any, sequences: Any, init_script: Any) -> list[ValidationFinding]:
    """Warns about helper statements that never run and names defined twice."""
    blocks = helper_blocks(scenes, sequences)
    findings: list[ValidationFinding] = []
    for block in blocks:
        findings.extend(_ignored_statement_findings(block))
    findings.extend(_conflict_findings(blocks, init_script))
    return findings
