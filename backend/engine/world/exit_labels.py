"""How an exit is named, including legacy exits without a label.

Every exit needs a label that names the passage itself ("a heavy oak door"), the same from
both sides of a two-way exit. Older data may still lack one; such an exit is named after the
scene it leads to, which is correct from either side. Two forms:

- ``exit_display_name``: the label or the target scene's name, as shown on the exit tile and
  usable as ``/go <name>``.
- ``exit_phrase``: the label or "the way to <target>", for sentences such as
  "<phrase> is locked."
"""

from __future__ import annotations

from typing import Any, Optional


def scene_title_from_id(scene_id: Any) -> str:
    """``"COMBAT_LAB"`` -> ``"Combat Lab"``; used when no scene name is at hand."""
    words = str(scene_id or "").replace("-", " ").replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)


def _target(target_name: Optional[str], target_scene_id: Any) -> str:
    return str(target_name or "").strip() or scene_title_from_id(target_scene_id)


def exit_display_name(
    label: Optional[str], target_name: Optional[str] = None, target_scene_id: Any = None
) -> str:
    """The label, else the target scene's name, else ``"Exit"``."""
    text = str(label or "").strip()
    return text or _target(target_name, target_scene_id) or "Exit"


def exit_phrase(
    label: Optional[str], target_name: Optional[str] = None, target_scene_id: Any = None
) -> str:
    """The label, else ``"the way to <target>"``, else ``"the exit"`` (lower-case start)."""
    text = str(label or "").strip()
    if text:
        return text
    target = _target(target_name, target_scene_id)
    return f"the way to {target}" if target else "the exit"


def capitalized(text: str) -> str:
    """First letter upper-case, the rest unchanged (``"the way to X"`` -> ``"The way to X"``)."""
    return text[:1].upper() + text[1:]


def exit_target_scene_id(world_exit: Any, current_scene_id: Any) -> Any:
    """The scene an exit leads to when taken from ``current_scene_id`` (two-way aware)."""
    from_id = getattr(world_exit, "from_scene_id", None)
    to_id = getattr(world_exit, "to_scene_id", None)
    if current_scene_id and str(to_id) == str(current_scene_id) and from_id:
        return from_id
    return to_id


def exit_sentence_name(world_exit: Any, current_scene_id: Any) -> str:
    """Sentence-start name of a stored exit taken from ``current_scene_id``."""
    target = exit_target_scene_id(world_exit, current_scene_id)
    return capitalized(exit_phrase(getattr(world_exit, "label", None), target_scene_id=target))
