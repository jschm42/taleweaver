"""Author-defined dialog skin of an adventure (``ui_theme``).

Adventures may pick one of the built-in dialog skins and an accent color. Only these two
whitelisted values are stored; adventures never ship free-form CSS (imports are untrusted).
The skin ids mirror ``frontend/src/skins/skinRegistry.ts``.
"""

from __future__ import annotations

import re
from typing import Any, Optional

UI_SKINS = frozenset(
    {"classic", "chronicle", "noir", "terminal", "grimoire", "eldritch", "toon", "ancient"}
)
# Player choice that defers to the adventure's skin; stored as NULL on the session.
UI_SKIN_AUTO = "auto"

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_ui_theme(value: Any) -> Optional[dict[str, str]]:
    """Returns ``{"skin", "accent"}`` with only valid entries, or ``None`` when nothing is valid.

    Accepts a dict or a bare skin id string (manifest shorthand ``ui_theme: noir``).
    """
    if isinstance(value, str):
        value = {"skin": value}
    if not isinstance(value, dict):
        return None

    theme: dict[str, str] = {}
    skin = str(value.get("skin") or "").strip().lower()
    if skin in UI_SKINS:
        theme["skin"] = skin
    accent = str(value.get("accent") or "").strip()
    if _HEX_COLOR.match(accent):
        theme["accent"] = accent.lower()
    return theme or None
