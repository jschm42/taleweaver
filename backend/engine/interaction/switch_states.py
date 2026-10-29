"""SWITCH states: script-facing IDs and the optional labels shown in-game.

A state ID (e.g. ``OFF``, ``HALF-OPEN``, ``LEVEL_2``) is the key that scripts, transitions
and gates use: upper-case ``A-Z``, ``0-9``, ``_`` and ``-``, at most 15 characters. A label
(at most 20 characters) is the text the player sees; without one the ID is shown. Labels
live in the switch config as ``state_labels`` (``{ID: label}``); the manifest calls them
``switch_state_labels`` and also accepts ``[{"state": ID, "label": text}]``.
"""

from __future__ import annotations

import re
from typing import Any

STATE_ID_MAX = 15
STATE_LABEL_MAX = 20
STATE_ID_PATTERN = re.compile(r"^[A-Z0-9_-]{1,15}$")
_INVALID_CHARS = re.compile(r"[^A-Z0-9_-]")


def normalize_state_id(raw: Any) -> str:
    """Upper-cased ID with invalid characters removed, cut to the maximum length."""
    token = str(raw or "").strip().upper().replace(" ", "_")
    return _INVALID_CHARS.sub("", token)[:STATE_ID_MAX]


def is_valid_state_id(state: Any) -> bool:
    return isinstance(state, str) and bool(STATE_ID_PATTERN.fullmatch(state))


def _label_pairs(raw: Any) -> list[tuple[Any, Any]]:
    if isinstance(raw, dict):
        return list(raw.items())
    if not isinstance(raw, list):
        return []
    return [(e.get("state"), e.get("label")) for e in raw if isinstance(e, dict)]


def normalize_state_labels(states: list[str], raw: Any) -> dict[str, str]:
    """``{ID: label}`` for the given states; empty labels are dropped, long ones cut."""
    labels: dict[str, str] = {}
    for state, label in _label_pairs(raw):
        key = normalize_state_id(state)
        text = str(label or "").strip()[:STATE_LABEL_MAX].rstrip()
        if key in states and text:
            labels[key] = text
    return labels


def state_label(switch_config: dict[str, Any] | None, state: Any) -> str:
    """The in-game text of ``state``: its label, or the ID when no label is set."""
    state_id = str(state or "").strip().upper()
    labels = (switch_config or {}).get("state_labels")
    if isinstance(labels, dict) and str(labels.get(state_id) or "").strip():
        return str(labels[state_id]).strip()
    return state_id


def invalid_state_ids(states: list[str]) -> list[str]:
    return [s for s in states if not is_valid_state_id(s)]


def long_state_labels(raw: Any) -> list[str]:
    """States whose label exceeds the maximum length (for validation messages)."""
    return [
        str(state)
        for state, label in _label_pairs(raw)
        if len(str(label or "").strip()) > STATE_LABEL_MAX
    ]
