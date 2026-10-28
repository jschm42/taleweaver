"""Deterministic parser for the World-Builder blueprint syntax.

The Story Idea text is split into tags (``[Scene: CELL] Brig Cell``). Each tag body
holds ``key: value`` lines (mapped onto manifest fields), ``key: |`` script blocks
and free prose. Anything that is not a recognized key stays prose for the LLM.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field

from backend.engine.blueprint.converters import normalize_id
from backend.engine.blueprint.field_specs import KEY_TABLES, FieldSpec, normalize_key
from backend.engine.blueprint.models import Blueprint, BlueprintBlock, BlueprintValue

MAX_SEQUENCES = 15

_TAG_RE = re.compile(r"^(\s*)\[\s*([A-Za-z][A-Za-z_ ]*?)\s*(?::\s*([^\]]*))?\]\s*(.*)$")
_KEY_RE = re.compile(r"^(\s*)([A-Za-z][A-Za-z0-9_ \-]{0,40}?)\s*:\s*(.*)$")
_TRAILING_ID_RE = re.compile(r"^(.*?)\s*\(([A-Za-z][A-Za-z0-9_]*)\)\s*$")
_EXIT_REF_RE = re.compile(r"^\s*([^<>\-]+?)\s*(<->|->)\s*([^<>\-]+?)\s*$")

# tag word -> (block kind, preset item_type)
_KIND_ALIASES: dict[str, tuple[str, str]] = {
    "world": ("world", ""),
    "protagonist": ("protagonist", ""),
    "player": ("protagonist", ""),
    "scene": ("scene", ""),
    "location": ("scene", ""),
    "exit": ("exit", ""),
    "path": ("exit", ""),
    "npc": ("npc", ""),
    "character": ("npc", ""),
    "item": ("item", ""),
    "object": ("item", ""),
    "readable": ("item", "READABLE"),
    "container": ("item", "CONTAINER"),
    "switch": ("item", "SWITCH"),
    "mechanism": ("item", "SWITCH"),
    "weapon": ("item", "WEAPON"),
    "sequence": ("sequence", ""),
    "chapter": ("sequence", ""),
    "rule": ("rule", ""),
    "soft_rule": ("rule", ""),
    "script": ("script", ""),
    "sidequest": ("sidequest", ""),
    "quest": ("sidequest", ""),
    "award": ("award", ""),
    "ability": ("ability", ""),
}
_NAME_FIELDS = {
    "protagonist": "name",
    "scene": "name",
    "npc": "name",
    "item": "name",
    "sequence": "title",
    "sidequest": "title",
    "award": "title",
    "script": "name",
    "ability": "name",
    "rule": "condition",
    "exit": "label",
}
_SINGLETON_KINDS = {"world", "protagonist"}
_INTRODUCED_KINDS = {"scene", "npc", "item", "exit"}


@dataclass
class _ParseState:
    blueprint: Blueprint
    current: BlueprintBlock | None = None
    child: BlueprintBlock | None = None
    premise: list[str] = field(default_factory=list)
    sequence_count: int = 0

    @property
    def target(self) -> BlueprintBlock | None:
        return self.child or self.current


def has_blueprint_tags(text: str) -> bool:
    """True if the text contains at least one recognized blueprint tag."""
    return any(_match_tag(line) for line in (text or "").splitlines())


def parse_blueprint(text: str) -> Blueprint:
    state = _ParseState(blueprint=Blueprint())
    lines = (text or "").splitlines()
    index = 0
    while index < len(lines):
        index = _consume_line(state, lines, index)
    state.blueprint.premise = "\n".join(state.premise).strip()
    for block in state.blueprint.blocks:
        _derive_implied_fields(block)
    return state.blueprint


def _match_tag(line: str) -> tuple[str, str, str, str, int] | None:
    match = _TAG_RE.match(line)
    if not match:
        return None
    word = normalize_key(match.group(2))
    if word not in _KIND_ALIASES:
        return None
    kind, preset_type = _KIND_ALIASES[word]
    indent = len(match.group(1).expandtabs(4))
    return kind, preset_type, (match.group(3) or "").strip(), match.group(4).strip(), indent


def _consume_line(state: _ParseState, lines: list[str], index: int) -> int:
    line = lines[index]
    tag = _match_tag(line)
    if tag:
        _open_block(state, index + 1, *tag)
        return index + 1
    target = state.target
    if target is None:
        state.premise.append(line)
        return index + 1
    key_match = _KEY_RE.match(line)
    spec = _lookup_spec(target.kind, key_match.group(2)) if key_match else None
    if not key_match or spec is None or not key_match.group(3).strip():
        if line.strip():
            target.prose.append(line.strip())
        return index + 1
    key_indent = len(key_match.group(1).expandtabs(4))
    raw_value = key_match.group(3).strip()
    if raw_value == "|":
        block_text, next_index = _read_block_scalar(lines, index + 1, key_indent)
        _store_value(state.blueprint, target, key_match.group(2), spec, block_text, index + 1)
        return next_index
    _store_value(state.blueprint, target, key_match.group(2), spec, raw_value, index + 1)
    return index + 1


def _lookup_spec(kind: str, raw_key: str) -> FieldSpec | None:
    return KEY_TABLES.get(kind, {}).get(normalize_key(raw_key))


def _read_block_scalar(lines: list[str], start: int, key_indent: int) -> tuple[str, int]:
    collected: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        indent = len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip())
        if line.strip() and indent <= key_indent:
            break
        collected.append(line.expandtabs(4))
        index += 1
    return textwrap.dedent("\n".join(collected)).strip("\n"), index


def _store_value(
    blueprint: Blueprint,
    block: BlueprintBlock,
    raw_key: str,
    spec: FieldSpec,
    raw_value: str,
    line_no: int,
) -> None:
    if raw_value.strip() == "?":
        block.open_fields.append(spec.target)
        return
    mode = "fixed"
    if raw_value.startswith("~"):
        mode, raw_value = "hint", raw_value[1:].strip()
    try:
        value = spec.convert(raw_value)
    except ValueError as exc:
        blueprint.add_issue(line_no, f"{block.kind} '{block.ref or block.name}': {raw_key}: {exc}")
        return
    if spec.target == "*":
        for target, sub_value in value.items():
            block.fields[target] = BlueprintValue(sub_value, mode, line_no)
        return
    if spec.repeat:
        existing = block.fields.get(spec.target)
        entries = list(existing.value) if existing else []
        block.fields[spec.target] = BlueprintValue([*entries, value], mode, line_no)
        return
    block.fields[spec.target] = BlueprintValue(value, mode, line_no)


def _open_block(
    state: _ParseState,
    line_no: int,
    kind: str,
    preset_type: str,
    raw_ref: str,
    rest: str,
    indent: int,
) -> None:
    blueprint = state.blueprint
    if kind in {"rule", "ability"} or (kind == "script" and indent > 0):
        _open_child(state, line_no, kind, raw_ref, rest)
        return
    state.child = None
    if kind in _SINGLETON_KINDS and blueprint.first(kind):
        blueprint.add_issue(line_no, f"[{kind.title()}] may only appear once.")
    if kind == "sequence":
        state.sequence_count += 1
        if state.sequence_count > MAX_SEQUENCES:
            blueprint.add_issue(
                line_no, f"More than {MAX_SEQUENCES} sequences; extra ones are ignored.", "warning"
            )
            state.current = BlueprintBlock(kind="ignored", ref="", name=rest, line=line_no)
            return
    block = _new_block(blueprint, line_no, kind, raw_ref, rest, state.sequence_count)
    if preset_type:
        block.fields["item_type"] = BlueprintValue(preset_type, "fixed", line_no)
    _note_introduction(state, block)
    blueprint.blocks.append(block)
    state.current = block


def _open_child(state: _ParseState, line_no: int, kind: str, raw_ref: str, rest: str) -> None:
    parent_kinds = {"rule": {"sequence"}, "script": {"sequence"}, "ability": {"npc", "protagonist"}}
    parent = state.current
    if kind != "ability":
        # Rules and chapter scripts belong to the latest chapter, even after entity tags.
        sequences = state.blueprint.of_kind("sequence")
        parent = sequences[-1] if sequences else None
    if parent is None or parent.kind not in parent_kinds[kind]:
        expected = " or ".join(sorted(parent_kinds[kind]))
        state.blueprint.add_issue(line_no, f"[{kind.title()}] must be placed inside a {expected}.")
        state.child = BlueprintBlock(kind="ignored", ref="", name=rest, line=line_no)
        return
    child = _new_block(state.blueprint, line_no, kind, raw_ref, rest, 0)
    if not child.ref:
        child.ref = f"{parent.ref}_{kind.upper()}_{len(parent.child_blocks(kind)) + 1}"
    parent.children.append(child)
    state.child = child


def _new_block(
    blueprint: Blueprint, line_no: int, kind: str, raw_ref: str, rest: str, sequence_no: int
) -> BlueprintBlock:
    name, explicit_id = rest, ""
    trailing = _TRAILING_ID_RE.match(rest)
    if trailing:
        name, explicit_id = trailing.group(1).strip(), trailing.group(2)
    block = BlueprintBlock(kind=kind, ref="", name=name, line=line_no)
    _store_header_name(block, name)
    if kind == "exit":
        _apply_exit_ref(blueprint, block, raw_ref)
        return block
    if kind == "sequence":
        block.ref = str(sequence_no)
        return block
    if kind in _SINGLETON_KINDS:
        return block
    ref = explicit_id or raw_ref
    if not ref or ref.isdigit():
        ref = name if name and name != "?" else ""
    block.ref = normalize_id(ref)
    if not block.ref and kind not in {"rule", "script", "ability"}:
        blueprint.add_issue(line_no, f"[{kind.title()}] needs an ID or a name.")
    return block


def _store_header_name(block: BlueprintBlock, name: str) -> None:
    """The text after a tag is the entity's name (``~Name`` = suggestion, ``?`` = open)."""
    target = _NAME_FIELDS.get(block.kind)
    if not target or not name:
        return
    if name == "?":
        block.name = ""
        block.open_fields.append(target)
        return
    mode = "hint" if name.startswith("~") else "fixed"
    block.name = name.lstrip("~").strip()
    block.fields[target] = BlueprintValue(block.name, mode, block.line)


def _apply_exit_ref(blueprint: Blueprint, block: BlueprintBlock, raw_ref: str) -> None:
    match = _EXIT_REF_RE.match(raw_ref)
    if not match:
        blueprint.add_issue(block.line, f"[Exit: {raw_ref}] must look like [Exit: FROM -> TO].")
        return
    from_id, to_id = normalize_id(match.group(1)), normalize_id(match.group(3))
    block.ref = f"{from_id}->{to_id}"
    block.fields["from_scene_id"] = BlueprintValue(from_id, "fixed", block.line)
    block.fields["to_scene_id"] = BlueprintValue(to_id, "fixed", block.line)
    if match.group(2) == "<->":
        block.fields["is_bidirectional"] = BlueprintValue(True, "fixed", block.line)


def _note_introduction(state: _ParseState, block: BlueprintBlock) -> None:
    """Keep the old behavior of mentioning chapter entities in the chapter walkthrough."""
    current = state.current
    if current is None or current.kind != "sequence" or block.kind not in _INTRODUCED_KINDS:
        return
    label = f" ({block.name})" if block.name else ""
    current.prose.append(f"Introduces {block.kind} {block.ref}{label}.")


_IMPLIED_ITEM_TYPES = (
    ("switch_states", "SWITCH"),
    ("text_log_content", "READABLE"),
    ("combination_ingredients", "CONSTRUCTABLE"),
)


def _derive_implied_fields(block: BlueprintBlock) -> None:
    if block.kind == "exit":
        lock_fields = ("code_to_unlock", "item_to_unlock", "rule_to_unlock", "unlock_expression")
        if "is_locked" not in block.fields and any(f in block.fields for f in lock_fields):
            block.fields["is_locked"] = BlueprintValue(True, "fixed", block.line)
        return
    if block.kind != "item" or "item_type" in block.fields:
        return
    for source, item_type in _IMPLIED_ITEM_TYPES:
        if source in block.fields:
            block.fields["item_type"] = BlueprintValue(item_type, "fixed", block.line)
            return
