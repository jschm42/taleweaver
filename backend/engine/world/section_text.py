"""AI text for one region's description or brief on the Regions page.

The prompt is built from what the adventure already knows: title, language, tone, teaser,
plot and chapters, the region's own fields, its planned routes, the other regions and the
scenes it already holds. The region data comes from the page draft, so unsaved regions work
too. The caller runs it on the small model; the text goes into the draft for review.
"""

from __future__ import annotations

from typing import Any

from backend.engine.world.section_context import clip
from backend.engine.world.sections import MAX_DESCRIPTION_LENGTH, is_stub

MAX_BRIEF_TEXT = 1500
FIELD_LIMITS = {"description": MAX_DESCRIPTION_LENGTH, "brief": MAX_BRIEF_TEXT}
_MAX_SCENES = 25
_MAX_CHAPTERS = 20

SECTION_TEXT_SYSTEM_PROMPT = (
    "You are the World-Builder of TaleWeaver, a text adventure engine. You write one text field "
    "of a region (an area of the adventure's world map) that fits the adventure's plot and the "
    "other regions.\n"
    "Write in {language}. The tone of the adventure is {tone}.\n"
    "Respond with ONLY the text of the field: no quotes, no heading or label, no markdown, no "
    "introduction or explanation."
)

FIELD_INSTRUCTIONS = {
    "description": (
        "Write the region's DESCRIPTION: one paragraph of 3-5 sentences that the Game Master "
        "reads while the player is in this region. Describe what the region looks like, its "
        "mood, who or what lives there and why it matters to the story. No game mechanics, no "
        "ids, no directions to the author."
    ),
    "brief": (
        "Write the region's BRIEF: directions for the World-Builder that will build this region "
        "later. Say which part of the adventure's plot plays here, the key locations, "
        "characters, items and puzzles, what the player needs to get in, and what the region "
        "leads to. Name neighbouring regions by their names. 3-6 sentences, concrete and dense."
    ),
}


def _region_lines(section: dict[str, Any], label_of: dict[str, str]) -> list[str]:
    state = "planned" if is_stub(section) else "built"
    lines = [f"Name: {section['label']} ({state})"]
    if section["description"]:
        lines.append(f"Current description: {clip(section['description'], 1500)}")
    if is_stub(section) and section["brief"]:
        lines.append(f"Current brief: {clip(section['brief'], 1500)}")
    for link in section["planned_links"]:
        hours = (
            f", {round(link['travel_minutes'] / 60, 1)} h travel"
            if link.get("travel_minutes")
            else ""
        )
        lines.append(
            f"Route to: {label_of.get(link['to_section_id'], link['to_section_id'])}{hours}"
        )
    return lines


def _other_line(section: dict[str, Any]) -> str:
    text = section["description"] if is_stub(section) else section["summary"]
    line = f"- {section['label']} [{'planned' if is_stub(section) else 'built'}]: "
    line += clip(text or section["description"], 300)
    if is_stub(section) and section["brief"]:
        line += f" Brief: {clip(section['brief'], 300)}"
    return line


def _order(chapter: dict[str, Any]) -> int:
    try:
        return int(chapter.get("order") or 0)
    except (TypeError, ValueError):
        return 0


def _chapters(adventure: Any) -> list[str]:
    chapters = sorted((s for s in adventure.sequences or [] if isinstance(s, dict)), key=_order)
    return [
        f"{s.get('order')}. {s.get('title', '')}: {clip(s.get('description'), 160)}"
        for s in chapters[:_MAX_CHAPTERS]
    ]


def _block(heading: str, lines: list[str]) -> str:
    return "\n".join([heading, *lines]) if lines else ""


def build_section_text_prompt(
    adventure: Any,
    section: dict[str, Any],
    sections: list[dict[str, Any]],
    scenes: list[tuple[str, str]],
    field: str,
) -> str:
    """The user prompt for ``field`` of ``section``; ``scenes`` are (label, description) pairs."""
    label_of = {s["id"]: s["label"] for s in sections}
    others = [_other_line(s) for s in sections if s["id"] != section["id"]]
    scene_lines = [f"- {label}: {clip(text, 160)}" for label, text in scenes[:_MAX_SCENES]]
    adventure_lines = [
        f"Title: {adventure.title}",
        f"Teaser: {clip(adventure.teaser, 600)}" if (adventure.teaser or "").strip() else "",
        f"Plot: {clip(adventure.plot, 4000)}" if (adventure.plot or "").strip() else "",
    ]
    parts = [
        _block("ADVENTURE:", [line for line in adventure_lines if line]),
        _block("CHAPTERS:", _chapters(adventure)),
        _block("THIS REGION:", _region_lines(section, label_of)),
        _block("SCENES ALREADY IN THIS REGION:", scene_lines),
        _block("OTHER REGIONS:", others),
        FIELD_INSTRUCTIONS[field]
        + " If a current text is given, write an improved version that keeps its intent."
        + f" At most {FIELD_LIMITS[field]} characters.",
    ]
    return "\n\n".join(part for part in parts if part)


def clean_section_text(text: str, field: str) -> str:
    """Strips an echoed field label and code fences, then enforces the field's limit."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    prefix = f"{field}:"
    if cleaned.lower().startswith(prefix):
        cleaned = cleaned[len(prefix) :].strip()
    return cleaned.strip('"').strip()[: FIELD_LIMITS[field]]
