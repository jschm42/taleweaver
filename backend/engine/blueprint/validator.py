"""Static checks for a parsed blueprint: script syntax, references and duplicates."""

from __future__ import annotations

import re
from collections.abc import Iterator
from functools import cache
from typing import Any

from backend.engine.blueprint.field_specs import KEY_TABLES, FieldRole
from backend.engine.blueprint.models import Blueprint, BlueprintBlock
from backend.engine.scripting.sandbox import SafeAstInterpreter

MAX_READABLE_CHARS = 500
_MENTION_RE = re.compile(r"@([A-Z][A-Z0-9_]+)")
_SCENE_REF_FIELDS = ("from_scene_id", "to_scene_id")


@cache
def _roles(kind: str) -> dict[str, FieldRole]:
    return {spec.target: spec.role for spec in KEY_TABLES.get(kind, {}).values()}


def iter_blocks(blueprint: Blueprint) -> Iterator[BlueprintBlock]:
    for block in blueprint.blocks:
        yield block
        yield from block.children


def validate_blueprint(blueprint: Blueprint) -> list[str]:
    """Add issues to ``blueprint`` and return the referenced-but-undeclared IDs."""
    _check_duplicates(blueprint)
    declared = blueprint.declared_ids()
    referenced: dict[str, int] = {}
    for block in iter_blocks(blueprint):
        _check_block_fields(blueprint, block, referenced)
        _check_required_parts(blueprint, block)
        for mention in _MENTION_RE.findall(block.description):
            referenced.setdefault(mention, block.line)
    missing = sorted(ref for ref in referenced if ref not in declared)
    for ref in missing:
        blueprint.add_issue(
            referenced[ref],
            f"'{ref}' is referenced but not declared; the World-Builder will be told to create it.",
            "warning",
        )
    return missing


def _check_duplicates(blueprint: Blueprint) -> None:
    seen: dict[tuple[str, str], int] = {}
    for block in iter_blocks(blueprint):
        if not block.ref or block.kind in {"world", "protagonist", "ignored"}:
            continue
        key = ("entity" if block.kind in {"scene", "npc", "item"} else block.kind, block.ref)
        if key in seen:
            blueprint.add_issue(
                block.line, f"Duplicate ID '{block.ref}' (first declared on line {seen[key]})."
            )
            continue
        seen[key] = block.line


def _check_block_fields(
    blueprint: Blueprint, block: BlueprintBlock, referenced: dict[str, int]
) -> None:
    roles = _roles(block.kind)
    for target, value in block.fields.items():
        role = "ref" if target in _SCENE_REF_FIELDS else roles.get(target, "text")
        for message in _check_value(role, value.value, referenced, value.line or block.line):
            blueprint.add_issue(value.line or block.line, f"{_label(block)} {target}: {message}")
    readable = block.fields.get("text_log_content")
    if readable and len(str(readable.value)) > MAX_READABLE_CHARS:
        blueprint.add_issue(
            readable.line,
            f"{_label(block)} text is longer than {MAX_READABLE_CHARS} characters "
            "and will be shortened.",
            "warning",
        )


def _check_value(role: FieldRole, value: Any, referenced: dict[str, int], line: int) -> list[str]:
    if role == "script":
        return SafeAstInterpreter.check_syntax(str(value))
    if role == "expr":
        return SafeAstInterpreter.check_expression_syntax(str(value))
    if role == "ref" and value:
        referenced.setdefault(str(value), line)
    if role == "refs":
        for ref in value:
            referenced.setdefault(ref, line)
    if role == "transition":
        return _check_transitions(value, referenced, line)
    return []


def _check_transitions(
    transitions: list[dict[str, Any]], referenced: dict[str, int], line: int
) -> list[str]:
    errors: list[str] = []
    for transition in transitions:
        gates = transition.get("gates") or {}
        if gates.get("item"):
            referenced.setdefault(gates["item"], line)
        errors.extend(SafeAstInterpreter.check_expression_syntax(gates.get("expression") or ""))
    return errors


def _check_required_parts(blueprint: Blueprint, block: BlueprintBlock) -> None:
    if block.kind == "script" and "code" not in block.fields:
        blueprint.add_issue(block.line, f"{_label(block)} has no 'code:'; it will be ignored.")
    if block.kind == "script" and "trigger" not in block.fields:
        blueprint.add_issue(block.line, f"{_label(block)} needs a 'trigger:'.")
    if block.kind == "rule" and not (block.name or "condition" in block.fields):
        blueprint.add_issue(block.line, f"{_label(block)} needs a condition ('when:').")


def _label(block: BlueprintBlock) -> str:
    return f"[{block.kind.title()}: {block.ref or block.name}]"
