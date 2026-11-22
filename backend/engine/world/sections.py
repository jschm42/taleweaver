"""World sections (regions): spatial groups of scenes on the adventure's world map.

An adventure stores its sections as a JSON list (``AdventureTemplate.world_sections``, like the
audio library) and each scene names its section in ``WorldScene.section_id`` (``None`` = no
section). An adventure without sections behaves exactly as before.

Sections are purely spatial: they gate nothing, gating stays on exits. A section's ``status`` is
``stub`` (planned, no scenes yet, visible to authors only), ``generating`` or ``built``. Sessions
only ever see built sections without the author fields: the session snapshot stores
:func:`player_sections` (spec: ``docs/specs/world_sections.md``).
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Optional

SECTION_STATUSES = ("stub", "generating", "built")
DEFAULT_STATUS = "built"
MAX_SECTIONS = 64
MAX_ID_LENGTH = 50
MAX_LABEL_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 2000
MAX_BRIEF_LENGTH = 4000
MAX_SUMMARY_LENGTH = 4000
MAX_LINKS = 12
MAX_NOTE_LENGTH = 200
MAX_TRAVEL_MINUTES = 60 * 24 * 365
# Fields only the author needs; sessions never receive them.
AUTHOR_ONLY_KEYS = (
    "status",
    "brief",
    "summary",
    "planned_links",
    "generation_error",
    "generation_notes",
    "generation_settings",
)
MAX_NOTES = 12
# Description length in the GM's CURRENT STATE region line.
_PROMPT_DESCRIPTION_LENGTH = 300
_ID_CLEAN = re.compile(r"[^A-Z0-9]+")


def section_id_or_none(raw: Any) -> Optional[str]:
    """``harbor town`` / ``HARBOR_TOWN`` -> ``HARBOR_TOWN``; empty input -> None."""
    if raw is None:
        return None
    cleaned = _ID_CLEAN.sub("_", str(raw).replace("##", "").strip().upper()).strip("_")
    return cleaned[:MAX_ID_LENGTH] or None


def _text(raw: Any, limit: int) -> str:
    return str(raw or "").strip()[:limit]


def _coordinate(raw: Any, fallback: float) -> float:
    """A map coordinate in percent of the world map (0-100)."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return fallback
    return round(min(100.0, max(0.0, value)), 1)


def _default_position(index: int) -> tuple[float, float]:
    """Grid spot for a section the author has not placed yet."""
    return 15.0 + (index % 4) * 23.0, min(90.0, 20.0 + (index // 4) * 25.0)


def _travel_minutes(raw: Any) -> Optional[int]:
    try:
        minutes = int(raw)
    except (TypeError, ValueError):
        return None
    return min(minutes, MAX_TRAVEL_MINUTES) if minutes > 0 else None


def _link(raw: Any, own_id: str) -> Optional[dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    target = section_id_or_none(raw.get("to_section_id") or raw.get("to"))
    if not target or target == own_id:
        return None
    return {
        "to_section_id": target,
        "travel_minutes": _travel_minutes(raw.get("travel_minutes")),
        "note": _text(raw.get("note"), MAX_NOTE_LENGTH),
    }


def _links(raw: Any, own_id: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    links: dict[str, dict[str, Any]] = {}
    for entry in raw:
        link = _link(entry, own_id)
        if link and link["to_section_id"] not in links:
            links[link["to_section_id"]] = link
    return list(links.values())[:MAX_LINKS]


def _notes(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [n for n in (_text(v, MAX_NOTE_LENGTH * 2) for v in raw) if n][:MAX_NOTES]


_MAX_SETTING_KEYS = 32


def _setting_value(value: Any) -> Any:
    """A JSON scalar of a stored generation setting, or None when it is not one."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return int(value)
    return value[:20] if isinstance(value, str) else None


def _setting_map(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    items = [(str(k)[:40], _setting_value(v)) for k, v in list(raw.items())[:_MAX_SETTING_KEYS]]
    return {key: value for key, value in items if key}


def _generation_settings(raw: Any) -> Optional[dict[str, Any]]:
    """The Region Builder's last settings ({mode, context, options}); the generator
    normalizes their values when it uses them (docs/specs/region_builder.md, 8.3)."""
    if not isinstance(raw, dict):
        return None
    mode = raw.get("mode") if raw.get("mode") in ("simple", "advanced") else "simple"
    return {
        "mode": mode,
        "context": _setting_map(raw.get("context")),
        "options": _setting_map(raw.get("options")),
    }


def _status(raw: Any) -> str:
    status = str(raw or "").strip().lower()
    return status if status in SECTION_STATUSES else DEFAULT_STATUS


def normalize_section(raw: Any, index: int = 0) -> Optional[dict[str, Any]]:
    """One section in canonical form, or None when it has no usable id."""
    if not isinstance(raw, dict):
        return None
    section_id = section_id_or_none(raw.get("id"))
    if not section_id:
        return None
    default_x, default_y = _default_position(index)
    return {
        "id": section_id,
        "label": _text(raw.get("label") or raw.get("name"), MAX_LABEL_LENGTH) or section_id,
        "description": _text(raw.get("description"), MAX_DESCRIPTION_LENGTH),
        "map_x": _coordinate(raw.get("map_x"), default_x),
        "map_y": _coordinate(raw.get("map_y"), default_y),
        "order_index": index,
        "status": _status(raw.get("status")),
        "brief": _text(raw.get("brief"), MAX_BRIEF_LENGTH),
        "summary": _text(raw.get("summary"), MAX_SUMMARY_LENGTH),
        "planned_links": _links(raw.get("planned_links"), section_id),
        # Why the last generation of a planned region failed ("" = none).
        "generation_error": _text(raw.get("generation_error"), MAX_NOTE_LENGTH * 3),
        # What the author should check after a generation (fix-ups, new validation findings).
        "generation_notes": _notes(raw.get("generation_notes")),
        # The Region Builder's last settings of this region (None = never built with it).
        "generation_settings": _generation_settings(raw.get("generation_settings")),
    }


def _order_key(entry: tuple[int, Any]) -> tuple[float, int]:
    position, raw = entry
    order = raw.get("order_index") if isinstance(raw, dict) else None
    return (float(order) if isinstance(order, (int, float)) else float(position), position)


def normalize_sections(raw: Any) -> list[dict[str, Any]]:
    """The canonical section list: unique ids, ordered, links only to known sections."""
    if not isinstance(raw, list):
        return []
    sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _position, entry in sorted(enumerate(raw), key=_order_key):
        section = normalize_section(entry, len(sections))
        if section is None or section["id"] in seen:
            continue
        seen.add(section["id"])
        sections.append(section)
        if len(sections) >= MAX_SECTIONS:
            break
    for section in sections:
        section["planned_links"] = [
            link for link in section["planned_links"] if link["to_section_id"] in seen
        ]
    return sections


def is_stub(section: dict[str, Any]) -> bool:
    """True for a section without playable scenes (planned or still generating)."""
    return section.get("status") != "built"


def player_sections(raw: Any) -> list[dict[str, Any]]:
    """Built sections without the author fields: what a session may know."""
    return [
        {key: value for key, value in section.items() if key not in AUTHOR_ONLY_KEYS}
        for section in normalize_sections(raw)
        if not is_stub(section)
    ]


def section_ids(raw: Any) -> set[str]:
    return {section["id"] for section in normalize_sections(raw)}


def find_section(raw: Any, section_id: Any) -> Optional[dict[str, Any]]:
    wanted = section_id_or_none(section_id)
    if not wanted:
        return None
    return next((s for s in normalize_sections(raw) if s["id"] == wanted), None)


def manifest_sections(manifest: Any) -> Any:
    """The raw section list of a manifest: top level ``sections`` or ``adventure.sections``."""
    if not isinstance(manifest, dict):
        return None
    if manifest.get("sections") is not None:
        return manifest["sections"]
    block = manifest.get("adventure") if isinstance(manifest.get("adventure"), dict) else {}
    return (
        block.get("sections") if block.get("sections") is not None else block.get("world_sections")
    )


def session_manifest(manifest: Any) -> dict[str, Any]:
    """A manifest copy for a session snapshot: stubs and author fields removed."""
    copy = deepcopy(manifest) if isinstance(manifest, dict) else {}
    if copy.get("sections") is not None:
        copy["sections"] = player_sections(copy["sections"])
    block = copy.get("adventure")
    if isinstance(block, dict) and block.get("sections") is not None:
        block["sections"] = player_sections(block["sections"])
    return copy


def region_line(sections: Any, section_id: Any) -> str:
    """``Region: <label>: <description>`` for the GM's CURRENT STATE, or "" without a section."""
    section = find_section(sections, section_id)
    if section is None or is_stub(section):
        return ""
    description = section["description"][:_PROMPT_DESCRIPTION_LENGTH].strip()
    return (
        f"Region: {section['label']}: {description}"
        if description
        else (f"Region: {section['label']}")
    )
