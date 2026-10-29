"""Best-effort repair of malformed or truncated JSON returned by LLMs."""

from __future__ import annotations

import json
import re

_SAFE_DELIMITERS = (",", "{", "[")
_CLOSERS = {"{": "}", "[": "]"}
_FIELD_LINE_RE = re.compile(r'^(\s*"(?:[^"\\]|\\.)+"\s*:\s*")(.*)("[\s,]*)$')


def is_truncated_json(content: str) -> bool:
    """Heuristic: True when the JSON document does not end with a closing brace/bracket
    (e.g. a token-limit cutoff mid-string)."""
    stripped = (content or "").rstrip()
    return bool(stripped) and stripped[-1] not in ("]", "}")


def _scan_structure(content: str) -> tuple[int, list[str]]:
    """Walks the JSON text tracking string/escape state and open structures.

    Returns (index where an unterminated string starts or -1, stack of pending closers).
    """
    string_open_at = -1
    escape_next = False
    stack: list[str] = []
    for i, ch in enumerate(content):
        if escape_next or ch == "\\":
            escape_next = not escape_next
            continue
        if ch == '"':
            string_open_at = -1 if string_open_at >= 0 else i
            continue
        if string_open_at >= 0:
            continue
        if ch in _CLOSERS:
            stack.append(_CLOSERS[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
    return string_open_at, stack


def _cut_before_unterminated_string(content: str, string_open_at: int) -> str:
    """Truncates back to the last safe delimiter (`,`, `{`, `[`) before the string.

    A colon is unsafe because it would leave a key without a value; a trailing comma is
    stripped so the result stays valid JSON.
    """
    last_safe = next(
        (i for i in range(string_open_at - 1, -1, -1) if content[i] in _SAFE_DELIMITERS), -1
    )
    if last_safe < 0:
        # Nothing safe before the unterminated string at all: drop the whole document.
        return ""
    if content[last_safe] == ",":
        return content[:last_safe].rstrip()
    return content[: last_safe + 1]


def attempt_repair_truncated_json(content: str) -> str:
    """Closes an obviously truncated JSON document so json.loads can parse it.

    Best-effort heuristic: may not produce semantically valid output, but captures more
    complete error context.
    """
    if not content:
        return content
    string_open_at, stack = _scan_structure(content)
    repaired = content
    if string_open_at >= 0:
        repaired = _cut_before_unterminated_string(content, string_open_at)
    # Strip a trailing comma so the appended closing braces/brackets produce valid JSON.
    repaired = re.sub(r",\s*$", "", repaired)
    return repaired + "".join(reversed(stack))


def _parses(content: str) -> bool:
    try:
        json.loads(content)
    except json.JSONDecodeError:
        return False
    return True


def _single_quoted_value_to_double(match: re.Match[str]) -> str:
    # Escape double quotes (now wrapped in double quotes) and unescape single quotes.
    val = match.group(1).replace('"', r"\"").replace(r"\'", "'")
    return f': "{val}"'


def _escape_quotes_in_field_line(line: str) -> str:
    """Escapes unescaped double quotes inside a `"key": "value"` line."""
    match = _FIELD_LINE_RE.match(line)
    if not match or '"' not in match.group(2):
        return line
    prefix, val, suffix = match.group(1), match.group(2), match.group(3)
    escaped_val = re.sub(r'(?<!\\)"', r"\"", val)
    return f"{prefix}{escaped_val}{suffix}"


def repair_json(content: str) -> str:
    """Repairs common minor JSON syntax errors (trailing commas, single quotes,
    unescaped double quotes inside values)."""
    if not content:
        return ""
    content = re.sub(r",\s*([\}\]])", r"\1", content)
    if _parses(content):
        return content

    content = re.sub(r"'\s*([a-zA-Z0-9_-]+)\s*'\s*:", r'"\1":', content)
    content = re.sub(r":\s*'([^'\\]*(?:\\.[^'\\]*)*)'", _single_quoted_value_to_double, content)
    if _parses(content):
        return content

    return "".join(_escape_quotes_in_field_line(line) for line in content.splitlines(keepends=True))
