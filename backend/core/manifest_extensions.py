"""Fork- and tool-specific data in an adventure manifest (top-level ``extensions``).

Forks and external tools may store their own data under a namespace of their choice,
e.g. ``"extensions": {"my_fork": {"visual_novel": {...}}}``. TaleWeaver never interprets it:
the block is kept on import, survives editing (it lives in ``original_manifest``) and is
written back on export. Imports are untrusted, so only well-formed namespaces are kept and
the block is size-capped.
"""

from __future__ import annotations

import json
import re
from typing import Any

EXTENSIONS_KEY = "extensions"
# Lower-case namespace ids such as "my_fork", "acme.vn" or "comfyui-scenes".
_NAMESPACE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
MAX_NAMESPACES = 32
MAX_EXTENSIONS_BYTES = 256 * 1024


def _encoded_size(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        return MAX_EXTENSIONS_BYTES + 1


def normalize_extensions(value: Any) -> dict[str, dict[str, Any]]:
    """Returns the valid namespaces of an ``extensions`` block, ``{}`` when none are valid.

    A namespace is kept when its id matches ``_NAMESPACE``, its value is a JSON object and
    it still fits into the total size budget. Namespaces past ``MAX_NAMESPACES`` are dropped.
    """
    if not isinstance(value, dict):
        return {}

    result: dict[str, dict[str, Any]] = {}
    budget = MAX_EXTENSIONS_BYTES
    for namespace, data in value.items():
        if len(result) >= MAX_NAMESPACES:
            break
        if not isinstance(namespace, str) or not _NAMESPACE.match(namespace):
            continue
        if not isinstance(data, dict):
            continue
        size = _encoded_size(data)
        if size > budget:
            continue
        budget -= size
        result[namespace] = data
    return result


def manifest_extensions(manifest: Any) -> dict[str, dict[str, Any]]:
    """Reads the normalized top-level ``extensions`` block of a manifest dict."""
    if not isinstance(manifest, dict):
        return {}
    return normalize_extensions(manifest.get(EXTENSIONS_KEY))
