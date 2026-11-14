"""Deterministic parser for the World-Builder blueprint syntax.

The Story Idea text is split into tags (``[Scene: CELL] Brig Cell`` or Markdown headings
such as ``## Scene: CELL — Brig Cell``). Each tag body holds ``key: value`` lines
(mapped onto manifest fields), ``key: |`` or fenced code blocks, and free prose.
Anything that is not a recognized key stays prose for the LLM.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field

from backend.engine.blueprint.converters import normalize_id
from backend.engine.blueprint.field_specs import (
    DEPRECATED_KEYS,
    KEY_TABLES,
    FieldSpec,
    normalize_key,
)
from backend.engine.blueprint.markdown import (
    is_fence_open,
    is_markdown_noise,
    match_markdown_heading_tag,
    match_markdown_section_heading,
    read_fenced_block,
    strip_inline_code,
)
from backend.engine.blueprint.models import Blueprint, BlueprintBlock, BlueprintValue
from backend.engine.world.dynamic_scene_schemas import build_dynamic_placeholder_scene_id

MAX_SEQUENCES = 15

# Tag and key patterns end in an unanchored ``(.*)`` (no ``$``) so a failing tail cannot
# trigger polynomial backtracking (ReDoS); the captured value is stripped by the caller.
_TAG_RE = re.compile(r"^(\s*)(?:(#{1,6})\s+|[-*]\s+)?\[([^:\]]+)(?::([^\]]*))?\](.*)")
_KEY_RE = re.compile(
    r"^(\s*)(?:[-*]\s+)?(?:\*\*|__|`)?([A-Za-z][A-Za-z0-9_\-]{0,40}(?:\s+[A-Za-z0-9_\-]+)*?)(?:\*\*|__|`)?\s*:(.*)"
)
_TRAILING_ID_RE = re.compile(r"^(.*?)\s*\(([A-Za-z][A-Za-z0-9_]*)\)\s*$")
_EXIT_REF_RE = re.compile(r"^\s*([^<>\-]+?)\s*(<->|->)\s*([^<>\-]+?)\s*$")

# tag word -> (block kind, preset item_type)
_KIND_ALIASES: dict[str, tuple[str, str]] = {
    "world": ("world", ""),
    "protagonist": ("protagonist", ""),
    "player": ("protagonist", ""),
    "scene": ("scene", ""),
    "dynamic_scene": ("scene", "DYNAMIC"),
    "dynamicscene": ("scene", "DYNAMIC"),
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
    "containerswitch": ("item", "CONTAINER_SWITCH"),
    "container_switch": ("item", "CONTAINER_SWITCH"),
    "mechanism": ("item", "SWITCH"),
    "weapon": ("item", "WEAPON"),
    "recipe": ("item", "CONSTRUCTABLE"),
    "sequence": ("sequence", ""),
    "chapter": ("sequence", ""),
    "rule": ("rule", ""),
    "soft_rule": ("rule", ""),
    "script": ("script", ""),
    "sidequest": ("sidequest", ""),
    "quest": ("sidequest", ""),
    "award": ("award", ""),
    "audio": ("audio", ""),
    "track": ("audio", ""),
    "music": ("audio", ""),
    "ability": ("ability", ""),
    "talent": ("talent", ""),
}
_NAME_FIELDS = {
    "protagonist": "name",
    "scene": "name",
    "npc": "name",
    "item": "name",
    "sequence": "title",
    "sidequest": "title",
    "award": "title",
    "audio": "name",
    "script": "name",
    "ability": "name",
    "talent": "name",
    "rule": "condition",
    "exit": "label",
}
_SINGLETON_KINDS = {"world", "protagonist"}
# Child tags of an entity (abilities, talents) or of the latest sequence (rules).
_ENTITY_CHILD_KINDS = {"ability", "talent"}
_CHILD_KINDS = {"rule", *_ENTITY_CHILD_KINDS}
_INTRODUCED_KINDS = {"scene", "npc", "item", "exit"}
_IMPLICIT_FENCE_KEYS = {"script": "code", "rule": "script"}


@dataclass
class _ParseState:
    blueprint: Blueprint
    current: BlueprintBlock | None = None
    child: BlueprintBlock | None = None
    premise: list[str] = field(default_factory=list)
    sequence_count: int = 0
    parent_heading_level: int = 0

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
    state.blueprint.premise = "\n".join(state.premise).strip() or state.blueprint.title
    for block in state.blueprint.blocks:
        _derive_implied_fields(block)
    return state.blueprint


def _match_tag(
    line: str, *, allow_md_heading: bool = True
) -> tuple[str, str, str, str, int, int] | None:
    match = _TAG_RE.match(line)
    if match:
        word = normalize_key(match.group(3).strip())
        if word not in _KIND_ALIASES:
            return None
        kind, preset_type = _KIND_ALIASES[word]
        indent = len(match.group(1).expandtabs(4))
        heading_level = len(match.group(2)) if match.group(2) else 0
        return (
            kind,
            preset_type,
            (match.group(4) or "").strip(),
            match.group(5).strip(),
            indent,
            heading_level,
        )
    if not allow_md_heading:
        return None
    return match_markdown_heading_tag(line, _KIND_ALIASES, _SINGLETON_KINDS)


def _consume_line(state: _ParseState, lines: list[str], index: int) -> int:
    line = lines[index]
    tag = _match_tag(line)
    if tag:
        _open_block(state, index + 1, *tag)
        return index + 1
    target = state.target
    if target is None:
        _consume_premise_line(state, line)
        return index + 1
    key_next = _try_consume_key(state, target, lines, index)
    if key_next is not None:
        return key_next
    return _consume_body_line(state, target, lines, index)


def _consume_premise_line(state: _ParseState, line: str) -> None:
    if is_markdown_noise(line):
        return
    heading = match_markdown_section_heading(line)
    if heading is not None:
        level, title_text = heading
        if level == 1 and not state.blueprint.title and not any(s.strip() for s in state.premise):
            state.blueprint.title = title_text
        return
    state.premise.append(line)


def _strip_value_markup(raw: str) -> str:
    """Value after ``key:`` without a leading ``**`` / ``__`` (the bold key's closing marker)."""
    value = raw.strip()
    if value.startswith(("**", "__")):
        value = value[2:].strip()
    return value


def _try_consume_key(
    state: _ParseState, target: BlueprintBlock, lines: list[str], index: int
) -> int | None:
    line = lines[index]
    key_match = _KEY_RE.match(line)
    spec = _lookup_spec(target.kind, key_match.group(2)) if key_match else None
    if not key_match or spec is None:
        return None
    raw_key = key_match.group(2)
    raw_value = strip_inline_code(_strip_value_markup(key_match.group(3)))
    next_has_fence = index + 1 < len(lines) and is_fence_open(lines[index + 1])
    if raw_value in ("|", "") and next_has_fence:
        block_text, next_index = read_fenced_block(lines, index + 2)
        _store_value(state.blueprint, target, raw_key, spec, block_text, index + 1)
        return next_index
    if raw_value == "|":
        key_indent = len(key_match.group(1).expandtabs(4))
        block_text, next_index = _read_block_scalar(lines, index + 1, key_indent)
        _store_value(state.blueprint, target, raw_key, spec, block_text, index + 1)
        return next_index
    if not raw_value:
        return None
    _store_value(state.blueprint, target, raw_key, spec, raw_value, index + 1)
    return index + 1


def _consume_body_line(
    state: _ParseState, target: BlueprintBlock, lines: list[str], index: int
) -> int:
    line = lines[index]
    implicit_key = _IMPLICIT_FENCE_KEYS.get(target.kind)
    if implicit_key and is_fence_open(line) and implicit_key not in target.fields:
        spec = _lookup_spec(target.kind, implicit_key)
        block_text, next_index = read_fenced_block(lines, index + 1)
        if spec is not None:
            _store_value(state.blueprint, target, implicit_key, spec, block_text, index + 1)
        return next_index
    if is_markdown_noise(line):
        return index + 1
    if match_markdown_section_heading(line) is not None:
        state.child = None
        return index + 1
    if line.strip():
        target.prose.append(line.strip())
    return index + 1


def _lookup_spec(kind: str, raw_key: str) -> FieldSpec | None:
    return KEY_TABLES.get(kind, {}).get(normalize_key(raw_key))


def _read_block_scalar(lines: list[str], start: int, key_indent: int) -> tuple[str, int]:
    """Reads a ``key: |`` block: the lines indented deeper than the key.

    A bracketed blueprint tag line also ends the block, so an indented ``[Rule: ...]`` right
    after a sequence's multi-line ``helpers``/``on_start`` value becomes a child, not script code.
    """
    collected: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        indent = len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip())
        if line.strip() and (indent <= key_indent or _match_tag(line, allow_md_heading=False)):
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
        mode, raw_value = "hint", strip_inline_code(raw_value[1:].strip())
    try:
        value = spec.convert(raw_value)
    except ValueError as exc:
        blueprint.add_issue(line_no, f"{block.kind} '{block.ref or block.name}': {raw_key}: {exc}")
        return
    deprecation = DEPRECATED_KEYS.get((block.kind, normalize_key(raw_key)))
    if deprecation:
        blueprint.add_issue(
            line_no,
            f"{block.kind} '{block.ref or block.name}': '{raw_key}' is deprecated; {deprecation}.",
            "warning",
        )
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


def _is_child_script(state: _ParseState, indent: int, heading_level: int) -> bool:
    if indent > 0:
        return True
    if state.current is None or state.current.kind != "sequence":
        return False
    return heading_level > state.parent_heading_level > 0


def _open_block(
    state: _ParseState,
    line_no: int,
    kind: str,
    preset_type: str,
    raw_ref: str,
    rest: str,
    indent: int,
    heading_level: int = 0,
) -> None:
    blueprint = state.blueprint
    if kind in _CHILD_KINDS or (
        kind == "script" and _is_child_script(state, indent, heading_level)
    ):
        _open_child(state, line_no, kind, raw_ref, rest)
        return
    state.child = None
    state.parent_heading_level = heading_level
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
    if preset_type == "DYNAMIC" and kind == "scene":
        block.fields["dynamic_zone.enabled"] = BlueprintValue(True, "fixed", line_no)
    elif preset_type:
        block.fields["item_type"] = BlueprintValue(preset_type, "fixed", line_no)
    _note_introduction(state, block)
    blueprint.blocks.append(block)
    state.current = block


def _open_child(state: _ParseState, line_no: int, kind: str, raw_ref: str, rest: str) -> None:
    parent_kinds = {
        "rule": {"sequence"},
        "script": {"sequence"},
        "ability": {"npc", "protagonist"},
        "talent": {"protagonist"},
    }
    parent = state.current
    if kind not in _ENTITY_CHILD_KINDS:
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
    cleaned_rest = strip_inline_code(rest)
    name, explicit_id = cleaned_rest, ""
    trailing = _TRAILING_ID_RE.match(cleaned_rest)
    if trailing:
        name, explicit_id = strip_inline_code(trailing.group(1)), trailing.group(2)
    block = BlueprintBlock(kind=kind, ref="", name=name, line=line_no)
    _store_header_name(block, name)
    if kind == "exit":
        _apply_exit_ref(blueprint, block, strip_inline_code(raw_ref))
        return block
    if kind == "sequence":
        block.ref = str(sequence_no)
        return block
    if kind in _SINGLETON_KINDS:
        return block
    ref = explicit_id or strip_inline_code(raw_ref)
    if not ref or ref.isdigit():
        ref = block.name if block.name and block.name != "?" else ""
    block.ref = normalize_id(ref)
    if not block.ref and kind not in {"script", *_CHILD_KINDS}:
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
    block.name = strip_inline_code(name.lstrip("~").strip())
    block.fields[target] = BlueprintValue(block.name, mode, block.line)


def _apply_exit_ref(blueprint: Blueprint, block: BlueprintBlock, raw_ref: str) -> None:
    match = _EXIT_REF_RE.match(raw_ref)
    if not match:
        blueprint.add_issue(block.line, f"[Exit: {raw_ref}] must look like [Exit: FROM -> TO].")
        return
    from_id = normalize_id(match.group(1))
    raw_to = match.group(3).strip()
    to_id = "?" if raw_to in {"?", "*"} else normalize_id(raw_to)
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
    ("result_item_ids", "CONSTRUCTABLE"),
)


def _derive_dynamic_exit_fields(block: BlueprintBlock) -> None:
    from_id = str(block.fields.get("from_scene_id", BlueprintValue("")).value or "")
    raw_to = str(block.fields.get("to_scene_id", BlueprintValue("")).value or "")
    if "dynamic_zone.zone_id" not in block.fields:
        fallback_name = normalize_id(block.name or "zone").lower() or "zone"
        zone_id = raw_to.lower() if (raw_to and raw_to != "?") else fallback_name
        block.fields["dynamic_zone.zone_id"] = BlueprintValue(zone_id, "fixed", block.line)
    else:
        zone_id = str(block.fields["dynamic_zone.zone_id"].value)
    if "dynamic_zone.theme" not in block.fields and block.description:
        block.fields["dynamic_zone.theme"] = BlueprintValue(block.description, "fixed", block.line)
    placeholder_id = build_dynamic_placeholder_scene_id(
        zone_id, 1, 1, f"{from_id}{block.name or ''}"
    )
    block.fields["to_scene_id"] = BlueprintValue(placeholder_id, "fixed", block.line)


def _derive_dynamic_scene_fields(block: BlueprintBlock) -> None:
    enabled_field = block.fields.get("dynamic_zone.enabled")
    if enabled_field and enabled_field.value is False:
        return
    if "dynamic_zone.zone_id" not in block.fields:
        fallback_zone = normalize_id(block.ref or block.name or "zone").lower() or "zone"
        block.fields["dynamic_zone.zone_id"] = BlueprintValue(fallback_zone, "fixed", block.line)
    if "dynamic_zone.theme" not in block.fields:
        theme = block.description or block.name or "Uncharted area"
        block.fields["dynamic_zone.theme"] = BlueprintValue(theme, "fixed", block.line)


def _derive_implied_fields(block: BlueprintBlock) -> None:
    if block.kind == "scene":
        if any(k.startswith("dynamic_zone.") for k in block.fields):
            _derive_dynamic_scene_fields(block)
        return
    if block.kind == "exit":
        if any(k.startswith("dynamic_zone.") for k in block.fields):
            _derive_dynamic_exit_fields(block)
        lock_fields = ("code_to_unlock", "item_to_unlock", "rule_to_unlock", "unlock_expression")
        if "is_locked" not in block.fields and any(f in block.fields for f in lock_fields):
            block.fields["is_locked"] = BlueprintValue(True, "fixed", block.line)
        return
    if block.kind != "item" or "item_type" in block.fields:
        return
    has_container_fields = any(
        f in block.fields for f in ("inventory", "on_items_added_script", "on_items_added_text")
    )
    if "switch_states" in block.fields and has_container_fields:
        block.fields["item_type"] = BlueprintValue("CONTAINER_SWITCH", "fixed", block.line)
        return
    for source, item_type in _IMPLIED_ITEM_TYPES:
        if source in block.fields:
            block.fields["item_type"] = BlueprintValue(item_type, "fixed", block.line)
            return
