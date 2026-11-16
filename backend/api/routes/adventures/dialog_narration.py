"""Narration while a script's choice dialog waits for the player.

A trigger in this turn (``on_interact``, ``on_receive_item``, ``on_enter_scene`` ...) may open a
choice dialog with ``tw.dialog.choose`` / ``tw.dialog.tree``. The player's answer then decides
what happens (its handler may teleport, start a sequence, ...). Pass 2 must not decide it
first, so the narration gets a reminder: stop where the choice begins.

A dialog can only be open at narration time if this turn opened it: while one is open,
``POST /chat`` refuses new player messages.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.scripting.dialog import pending_dialog

_MAX_OPTIONS_IN_REMINDER = 6


def open_choice_reminder(entity_states: Any) -> Optional[str]:
    """Pass 2 reminder for an open choice dialog, or None without one."""
    dialog = pending_dialog(entity_states if isinstance(entity_states, dict) else None)
    if not dialog:
        return None
    labels = [str(o.get("label") or "") for o in dialog.get("options") or []]
    options = "; ".join(f'"{label}"' for label in labels[:_MAX_OPTIONS_IN_REMINDER] if label)
    speaker = str(dialog.get("speaker") or "").strip()
    asker = f" ({speaker} asks)" if speaker else ""
    return (
        f"OPEN CHOICE{asker}: the game now shows the player a choice: "
        f'"{dialog.get("prompt") or ""}" Options: {options}. '
        "End the narration where this choice begins: do not choose for the player, do not "
        "narrate the outcome of any option, and do not repeat the question word for word."
    )
