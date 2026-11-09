"""Markdown syntax helpers for the World-Builder blueprint parser."""

from __future__ import annotations

import re
import textwrap

_MD_HEADING_RE = re.compile(r"^(\s*)(#{1,6})\s+(.*)$")
_SINGLE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]+$")
_HR_RE = re.compile(r"^(?:---+|\*\*\*+)$")
_FENCE_OPEN_RE = re.compile(r"^\s*```[A-Za-z0-9_\-]*\s*$")
_FENCE_CLOSE_RE = re.compile(r"^\s*```\s*$")
_EXIT_ROUTE_RE = re.compile(r"^([^<>\r\n]+?(?:<->|->)\s*[A-Za-z0-9_]+)(.*)$")
_SEP_START_RE = re.compile(r"^(?:—|–|-|:)\s*(.*)$")


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
    indent_str, hashes, raw_body = heading_match.groups()
    body = raw_body.strip()
    if not body:
        return None

    if ":" in body:
        raw_word, raw_tail = body.split(":", 1)
        tail = raw_tail.strip()
    else:
        raw_word, tail = body, None

    word = normalize_md_word(raw_word)
    if not word or word not in kind_aliases:
        return None
    kind, preset_type = kind_aliases[word]
    if tail is None and kind not in singleton_kinds:
        return None
    raw_ref, rest = _split_md_tag_tail(kind, (tail or "").strip(), singleton_kinds)
    indent = len(indent_str.expandtabs(4))
    return kind, preset_type, raw_ref, rest, indent, len(hashes)


def _split_exit_tail(tail: str) -> tuple[str, str]:
    exit_match = _EXIT_ROUTE_RE.match(tail)
    if not exit_match:
        return tail, ""
    route = exit_match.group(1).strip()
    rem = exit_match.group(2).strip()
    if not rem:
        return route, ""
    sep_match = _SEP_START_RE.match(rem)
    return route, sep_match.group(1).strip() if sep_match else rem


def _split_md_tag_tail(kind: str, tail: str, singleton_kinds: set[str]) -> tuple[str, str]:
    if not tail or kind in singleton_kinds:
        return "", tail
    if kind == "exit":
        return _split_exit_tail(tail)

    parts = tail.split(None, 1)
    first = parts[0]
    if not _SINGLE_TOKEN_RE.match(first):
        return "", tail
    if len(parts) == 1:
        return first, ""
    sep_match = _SEP_START_RE.match(parts[1].strip())
    if sep_match:
        return first, sep_match.group(1).strip()
    return "", tail


def match_markdown_section_heading(line: str) -> tuple[int, str] | None:
    """Match a general Markdown heading ``# ...`` returning ``(level, text)``."""
    match = _MD_HEADING_RE.match(line)
    if not match:
        return None
    return len(match.group(2)), match.group(3).strip()


def is_markdown_noise(line: str) -> bool:
    """True for horizontal rules (``---``, ``***``) and single-line HTML comments."""
    stripped = line.strip()
    if stripped.startswith("<!--") and stripped.endswith("-->"):
        return True
    return bool(_HR_RE.match(stripped))


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
