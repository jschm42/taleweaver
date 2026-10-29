"""Player-facing strategy guide assembled from the per-sequence mini-walkthroughs."""

from __future__ import annotations

from typing import Any, Optional


def _ordered_sequences(sequences: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    valid = [seq for seq in (sequences or []) if isinstance(seq, dict)]
    return sorted(valid, key=lambda seq: seq.get("order") or 0)


def _step_title(seq: dict[str, Any], index: int, is_active: bool) -> str:
    title = str(seq.get("title") or "").strip() or f"Sequence {index + 1}"
    return f"{title} (current)" if is_active else title


def sequence_walkthrough_steps(
    sequences: Optional[list[dict[str, Any]]], active_sequence_id: Optional[str] = None
) -> list[dict[str, str]]:
    """One step per sequence that has a walkthrough, in story order."""
    ordered = _ordered_sequences(sequences)
    current_id = active_sequence_id or (ordered[0].get("id") if ordered else None)
    steps: list[dict[str, str]] = []
    for index, seq in enumerate(ordered):
        content = str(seq.get("walkthrough") or "").strip()
        if not content:
            continue
        is_active = bool(current_id) and seq.get("id") == current_id
        steps.append({"title": _step_title(seq, index, is_active), "content": content})
    return steps


def legacy_main_sequence(
    walkthrough: str, plot: Optional[str] = None, completed_condition: Optional[str] = None
) -> dict[str, Any]:
    """Sequence 1 built from an old adventure-wide walkthrough (pre-sequence format)."""
    return {
        "id": "SEQ_1_MAIN",
        "order": 1,
        "title": "Main Journey",
        "description": plot or "Follow the adventure storyline.",
        "walkthrough": walkthrough or "Follow the main storyline.",
        "end_condition": completed_condition or "Achieve the victory condition.",
        "exp_reward": 500,
    }


def apply_legacy_walkthrough(template: Any, walkthrough: Optional[str]) -> None:
    """Converts a legacy global walkthrough into a sequence when the template has none."""
    if getattr(template, "sequences", None) or not walkthrough:
        return
    template.sequences = [
        legacy_main_sequence(walkthrough, template.plot, template.completed_condition)
    ]


def format_walkthrough_steps(steps: list[dict[str, str]]) -> str:
    """Plain-text rendering of the steps (used by the debug command and raw view)."""
    return "\n\n".join(f"## {step['title']}\n{step['content']}" for step in steps)
