"""Protagonist persona context for the autonomous PlayAgent."""

from typing import Any

_PROFILE_FIELDS = (
    ("description", "Biography"),
    ("character", "Personality & Traits"),
    ("goal", "Personal Goal"),
)


def format_protagonist_profile(avatar: Any) -> str:
    """Renders the protagonist's bio, character traits and goal for role-play.

    Empty fields are skipped; returns a short fallback when no profile exists.
    """
    lines = []
    for attr, label in _PROFILE_FIELDS:
        value = " ".join(str(getattr(avatar, attr, "") or "").split())
        if value:
            lines.append(f"{label}: {value}")
    if not lines:
        return "No biography provided. Infer a fitting persona from your name, role, and the adventure premise."
    return "\n".join(lines)
