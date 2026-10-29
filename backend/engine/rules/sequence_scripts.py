"""Sequence-scoped event scripts: a sequence's ``scripts`` only run while it is the active one.

They use the same shape as top-level scripts (``trigger``, ``target_id``, ``code``) and are
appended to the top-level scripts when the script runner is built, so every trigger dispatch
picks them up. ``on_init`` is not allowed: no sequence is active before the session exists;
use the sequence's ``on_start_sequence_script`` for chapter set-up instead.
"""

from __future__ import annotations

from typing import Any, Optional

SEQUENCE_SCRIPT_TRIGGERS = frozenset(
    {
        "on_enter_scene",
        "on_interact",
        "on_turn_start",
        "on_turn_end",
        "on_logic_pass_done",
        "on_narration_done",
    }
)


def sequence_scripts(sequence: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """The valid scripts of ``sequence``, tagged with its id."""
    if not isinstance(sequence, dict):
        return []
    rows = sequence.get("scripts") or []
    return [
        {**row, "sequence_id": sequence.get("id")}
        for row in rows
        if isinstance(row, dict) and row.get("trigger") in SEQUENCE_SCRIPT_TRIGGERS
    ]
