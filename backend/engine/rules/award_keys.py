"""Award keys: new keys are stored in upper case; granting matches keys case-insensitively.

Existing adventures may still hold lower-case keys (earned awards reference them as stored),
so stored keys are never rewritten. Instead, a requested key is mapped to the stored key.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

_NON_KEY_CHARS = re.compile(r"[^A-Z0-9_]+")


def normalize_award_key(key: Any) -> str:
    """``"award brass-lever"`` -> ``"AWARD_BRASS_LEVER"`` (empty for an empty key)."""
    return _NON_KEY_CHARS.sub("_", str(key or "").strip().upper()).strip("_")


def normalize_new_award_keys(awards: Any) -> None:
    """Upper-cases the keys of freshly generated awards in place (never for stored adventures)."""
    for award in awards if isinstance(awards, list) else []:
        if isinstance(award, dict) and normalize_award_key(award.get("key")):
            award["key"] = normalize_award_key(award["key"])


def canonical_award_keys(requested: Iterable[Any], awards: Iterable[Any]) -> list[str]:
    """Maps each requested key to the adventure's stored key, ignoring case.

    Unknown keys are kept as given, so callers still report them as non-existent.
    """
    stored: dict[str, str] = {}
    for award in awards or []:
        key = str(award.get("key") or "") if isinstance(award, dict) else ""
        if key:
            stored.setdefault(key.upper(), key)
    return [stored.get(str(key).upper(), str(key)) for key in requested if key]
