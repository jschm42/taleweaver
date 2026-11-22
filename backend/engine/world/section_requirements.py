"""Size, feature and strictness options of a region and their REGION REQUIREMENTS block.

The same options as on the Generate adventure page, worded for one region with region-sized
defaults (a new adventure's "3 to 10 scenes" would be too few or too many here). ``None``
as min and max means the AI decides. Spec: docs/specs/region_builder.md (4.2, 7.2).
"""

from __future__ import annotations

from typing import Any, Optional

COUNT_KEYS = ("scenes", "items", "quests", "sequences", "containers", "text_logs", "awards")
FEATURE_KEYS = (
    "quest_generation_enabled",
    "container_generation_enabled",
    "scripts_generation_enabled",
    "text_log_generation_enabled",
    "award_generation_enabled",
)
MAX_COUNT = 60
STRICTNESS = ("creative", "strict")

_LABELS = {
    "scenes": "New scenes",
    "items": "New items in `objects` (containers and readables included)",
    "quests": "New side quests",
    "sequences": "New chapters (`sequences`)",
    "containers": "CONTAINER items",
    "text_logs": "READABLE items",
    "awards": "New awards",
}
_TYPICAL = {
    "scenes": "6 to 10",
    "items": "4 to 12",
    "quests": "0 to 2",
    "sequences": "0 or 1, only when the region carries its own story step",
    "containers": "1 to 3",
    "text_logs": "0 to 3",
    "awards": "0 to 2",
}
_FEATURE_OF = {
    "quests": "quest_generation_enabled",
    "containers": "container_generation_enabled",
    "text_logs": "text_log_generation_enabled",
    "awards": "award_generation_enabled",
}
_STRICTNESS_LINES = {
    "creative": "- Strictness: creative. Expand the region brief freely within these counts.",
    "strict": (
        "- Strictness: strict. Build exactly the scenes, characters, items and puzzles the "
        "region brief names; add only what the counts above demand."
    ),
}
_READABLE_RULE = (
    "- READABLE items need a non-empty `text_log_content` (at most 500 characters) and never "
    "state a lock code directly (use a riddle or a fragment)."
)


def _count(raw: Any) -> Optional[int]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return max(0, min(MAX_COUNT, int(raw)))
    except (TypeError, ValueError):
        return None


def normalize_options(raw: Any) -> dict[str, Any]:
    """Counts clamped to 0-60 (min never above max), switches default on, strictness."""
    data = raw if isinstance(raw, dict) else {}
    options: dict[str, Any] = {key: data.get(key) is not False for key in FEATURE_KEYS}
    for key in COUNT_KEYS:
        low, high = _count(data.get(f"min_{key}")), _count(data.get(f"max_{key}"))
        if low is not None and high is not None and low > high:
            high = low
        options[f"min_{key}"], options[f"max_{key}"] = low, high
    strictness = data.get("generation_strictness")
    options["generation_strictness"] = strictness if strictness in STRICTNESS else "creative"
    return options


def _count_line(key: str, low: Optional[int], high: Optional[int]) -> str:
    label = _LABELS[key]
    if low is None and high is None:
        return f"- {label}: a fitting number, typically {_TYPICAL[key]}."
    if high is None:
        return f"- {label}: at least {low}."
    if low is None:
        return f"- {label}: at most {high}."
    if low == high:
        return f"- {label}: exactly {low}."
    return f"- {label}: between {low} and {high}."


def requirements_text(options: dict[str, Any]) -> str:
    """The REGION REQUIREMENTS block of the prompt."""
    lines = ["REGION REQUIREMENTS:"]
    for key in COUNT_KEYS:
        flag = _FEATURE_OF.get(key)
        if flag and not options[flag]:
            lines.append(f"- {_LABELS[key]}: none.")
        else:
            lines.append(_count_line(key, options[f"min_{key}"], options[f"max_{key}"]))
    if options["text_log_generation_enabled"]:
        lines.append(_READABLE_RULE)
    if not options["scripts_generation_enabled"]:
        lines.append("- Scripts: none. Leave `scripts` empty and write no scene scripts.")
    lines.append(_STRICTNESS_LINES[options["generation_strictness"]])
    return "\n".join(lines)
