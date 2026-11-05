"""Resolves the title of a session's current sequence (chapter) for the session list."""

from __future__ import annotations

from typing import Any, Optional

from backend.api.routes.adventures.logic import AdventureLogic
from backend.models.session_state import SessionState


def _session_sequences(template: Any, state: Optional[SessionState]) -> list[dict[str, Any]]:
    """Template sequences first; sessions whose template is gone fall back to their manifest snapshot."""
    raw = getattr(template, "sequences", None) if template else None
    if not raw:
        snapshot = AdventureLogic.extract_manifest_snapshot(state)
        sources = (snapshot.get("adventure"), snapshot.get("original_manifest"))
        raw = next(
            (s.get("sequences") for s in sources if isinstance(s, dict) and s.get("sequences")),
            None,
        )
    if not isinstance(raw, list):
        return []
    return sorted((s for s in raw if isinstance(s, dict)), key=lambda s: s.get("order", 1))


def active_sequence_title(template: Any, state: Optional[SessionState]) -> Optional[str]:
    """Title of the active sequence, or None when the session has no state or no sequences."""
    if not state:
        return None
    sequences = _session_sequences(template, state)
    if not sequences:
        return None
    active_id = state.active_sequence_id
    mode = getattr(template, "sequence_progression_mode", "linear")
    if not active_id and mode == "dynamic":
        return None
    active = next((s for s in sequences if s.get("id") == active_id), None)
    if not active:
        if mode == "dynamic":
            return None
        active = sequences[0]
    return active.get("title") or active.get("id")
