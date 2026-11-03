"""Markdown syntax helpers for the World-Builder blueprint parser."""

from __future__ import annotations

import re
import textwrap

_MD_HEADING_RE = re.compile(r"^(\s*)(#{1,6})\s+(.+?)\s*$")
_MD_TAG_BODY_RE = re.compile(r"^([A-Za-z][A-Za-z_ ]*?)(?:\s*:\s*(.*))?$")
_MD_SPLIT_REF_RE = re.compile(r"^([A-Za-z0-9_]+)\s*(?:—|–|-|:)\s+(.*)$")
_MD_EXIT_SPLIT_RE = re.compile(r"^([^<>\-]+?(?:<->|->)\s*[A-Za-z0-9_]+)(?:\s*(?:—|–|-|:)\s*(.*))?$")
_SINGLE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]+$")
_HR_OR_COMMENT_RE = re.compile(r"^\s*(?:---+|\*\*\*+|<!--.*-->)\s*$")
_FENCE_OPEN_RE = re.compile(r"^\s*```[A-Za-z0-9_\-]*\s*$")
_FENCE_CLOSE_RE = re.compile(r"^\s*```\s*$")


def normalize_md_word(raw: str) -> str:
    return re.sub(r"[\s\-]+", "_", raw.strip().lower())


def match_markdown_heading_tag(
    line: str,
    kind_aliases: dict[str, tuple[str, str]],
    singleton_kinds: set[str],
) -> tuple[str, str, str, str, int, int] | None:
    """Match an unbracketed Markdown heading tag like ``## Scene: CELL — Brig Cell``."""
    heading_match = _MD_HEADING_RE.match(line)
    if not heading_match:
        return None
    indent_str, hashes, body = heading_match.groups()
    body_match = _MD_TAG_BODY_RE.match(body)
    if not body_match:
        return None
    word = normalize_md_word(body_match.group(1))
    if word not in kind_aliases:
        return None
    kind, preset_type = kind_aliases[word]
    tail = body_match.group(2)
    if tail is None and kind not in singleton_kinds:
        return None
    raw_ref, rest = _split_md_tag_tail(kind, (tail or "").strip(), singleton_kinds)
    indent = len(indent_str.expandtabs(4))
    return kind, preset_type, raw_ref, rest, indent, len(hashes)


def _split_md_tag_tail(kind: str, tail: str, singleton_kinds: set[str]) -> tuple[str, str]:
    if not tail or kind in singleton_kinds:
        return "", tail
    if kind == "exit":
        exit_match = _MD_EXIT_SPLIT_RE.match(tail)
        if exit_match:
            return exit_match.group(1).strip(), (exit_match.group(2) or "").strip()
        return tail, ""
    split_match = _MD_SPLIT_REF_RE.match(tail)
    if split_match:
        return split_match.group(1).strip(), split_match.group(2).strip()
    if _SINGLE_TOKEN_RE.match(tail):
        return tail, ""
    return "", tail


def match_markdown_section_heading(line: str) -> tuple[int, str] | None:
    """Match a general Markdown heading ``# ...`` returning ``(level, text)``."""
    match = _MD_HEADING_RE.match(line)
    if not match:
        return None
    return len(match.group(2)), match.group(3).strip()


def is_markdown_noise(line: str) -> bool:
    """True for horizontal rules (``---``, ``***``) and single-line HTML comments."""
    return bool(_HR_OR_COMMENT_RE.match(line))


def strip_inline_code(raw: str) -> str:
    """Strip surrounding single backticks from a single-line value or name."""
    cleaned = raw.strip()
    if (
        len(cleaned) >= 2
        and cleaned.startswith("`")
        and cleaned.endswith("`")
        and not cleaned.startswith("``")
    ):
        return cleaned[1:-1].strip()
    return cleaned


def is_fence_open(line: str) -> bool:
    """True when ``line`` opens a Markdown fenced code block (`` ```python `` or `` ``` ``)."""
    return bool(_FENCE_OPEN_RE.match(line))


def read_fenced_block(lines: list[str], start: int) -> tuple[str, int]:
    """Read lines after an opening `` ``` `` fence up to the closing `` ``` `` fence."""
    collected: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if _FENCE_CLOSE_RE.match(line):
            index += 1
            break
        collected.append(line.expandtabs(4))
        index += 1
    return textwrap.dedent("\n".join(collected)).strip("\n"), index
