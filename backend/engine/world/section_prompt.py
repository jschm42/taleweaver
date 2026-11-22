"""Prompts for region generation and for planning regions (docs/specs/world_sections.md, 9.3-9.4).

The region prompt is assembled from blocks in a fixed order (docs/specs/region_builder.md,
7.2): adventure frame, the world context options the author chose (``section_context``), the
gateway scenes, the new region, the requirements, and the errors of a rejected attempt. The
system prompt is static, so providers can cache it.
"""

from __future__ import annotations

from typing import Any

from backend.engine.world.section_context import (
    ContextBlock,
    ContextSource,
    clip,
    estimate_tokens,
    option_blocks,
)
from backend.engine.world.section_gateways import gateway_block
from backend.engine.world.section_requirements import requirements_text
from backend.engine.world.world_scripting_prompt import TW_API_REFERENCE

SECTION_SYSTEM_PROMPT = (
    "You are the World-Builder of TaleWeaver, a text adventure engine. You extend an EXISTING "
    "adventure with exactly ONE new region of its world map. Write only new content; never "
    "repeat or change anything the prompt lists as existing.\n\n"
    "RULES:\n"
    "- Follow the REGION REQUIREMENTS for how much to build. Scenes get vivid descriptions and "
    "all lie inside this region.\n"
    "- Ids are UPPERCASE slugs. Start every new id with the region's id prefix; never reuse an "
    "existing id (scenes, characters, items, quests and scripts share one id space).\n"
    "- Connect the region to the listed gateway scenes with exits (`exit_type: bidirectional` "
    "unless one-way makes sense). Give these long ways the listed `travel_minutes`. Every new "
    "scene must be reachable through exits.\n"
    "- Mark one or two central scenes `is_fast_travel_point: true`, one of them where the "
    "player arrives.\n"
    "- Characters start in new scenes (`start_scene_id`); items start in a new scene, or in a "
    "character's or container's inventory. Locks use items that already exist or are new in "
    "this region, and the key must be obtainable.\n"
    "- If a CAMPAIGN OUTLINE is given, plant and resolve what it asks of this region and report "
    "it in `thread_updates`.\n"
    "- Scripts: never use the trigger `on_init` and do not write an init script; the adventure "
    "already runs. Put setup into `on_enter_scene` scripts or a scene's `helpers_script`.\n"
    "- `summary`: 3-5 sentences on the region, its key characters, items and open hooks.\n\n"
    f"SCRIPTING API:\n{TW_API_REFERENCE}"
)

PLAN_SYSTEM_PROMPT = (
    "You are the World-Builder of TaleWeaver. You plan a campaign that spreads an adventure "
    "over several regions of a world map. Plan only: no scenes yet. Each planned region gets an "
    "uppercase id, a name, a one-paragraph description, a map position (map_x, map_y in "
    "percent, regions spread over the map), status 'stub', a brief for building it later, and "
    "planned_links to neighbouring regions with a travel time in minutes. Existing regions keep "
    "their ids; link new regions to them. The outline names each region's purpose, what gates "
    "it, what it plants for later regions and what it resolves, plus the threads that run "
    "across regions. The final goal must lie in the last region."
)


def _frame(adventure: Any) -> str:
    """Frame of the planning prompt (plot and rules included)."""
    return (
        f"ADVENTURE: {adventure.title}\n"
        f"Language of all player-facing text: {adventure.language or 'English'}\n"
        f"Plot: {adventure.plot or ''}\n"
        f"Rules: {adventure.rules or ''}"
    )


def _tone_label(adventure: Any) -> str:
    tone = getattr(adventure, "selected_tone", None) or {}
    if not isinstance(tone, dict):
        return ""
    return str(tone.get("name") or tone.get("label") or "")


def region_frame(adventure: Any) -> str:
    """Frame of the region prompt; plot and rules are context options of their own."""
    lines = [
        f"ADVENTURE: {adventure.title}",
        f"Language of all player-facing text: {adventure.language or 'English'}",
        f"Rule mode: {adventure.rule_enforcement_mode or 'story'}",
    ]
    tone = _tone_label(adventure)
    if tone:
        lines.append(f"Tone: {tone}")
    return "\n".join(lines)


def id_prefix(section_id: str) -> str:
    """``GLOOM_PEAKS`` -> ``GP_``, ``PEAKS`` -> ``PEA_``: the prefix of a region's new ids."""
    parts = [p for p in section_id.split("_") if p]
    if len(parts) > 1:
        return "".join(p[0] for p in parts)[:4] + "_"
    return section_id[:3] + "_"


def target_text(section: dict[str, Any]) -> str:
    return (
        f"THE NEW REGION: {section['id']} - {section['label']}\n"
        f"Id prefix of its new ids: {id_prefix(section['id'])}\n"
        f"Description: {clip(section['description'], 2000) or 'none'}\n"
        f"Brief: {section['brief'] or 'none'}"
    )


def region_blocks(
    src: ContextSource,
    context: dict[str, Any],
    options: dict[str, Any],
    neighbours: list[dict[str, Any]],
) -> list[ContextBlock]:
    """Every block of the region prompt in order; switched-off options are not ``included``."""
    return [
        ContextBlock("system", SECTION_SYSTEM_PROMPT, always=True),
        ContextBlock("frame", region_frame(src.adventure), always=True),
        *option_blocks(src, context),
        gateway_block(src, neighbours),
        ContextBlock("region", target_text(src.section), always=True),
        ContextBlock("requirements", requirements_text(options), always=True),
    ]


def build_section_prompt(blocks: list[ContextBlock], errors: list[str]) -> str:
    """The user prompt for one region; ``errors`` of a failed attempt are listed to fix."""
    parts = [b.text for b in blocks if b.included and b.text and b.id != "system"]
    if errors:
        parts.append(
            "YOUR LAST ATTEMPT WAS REJECTED. Fix every one of these problems:\n"
            + "\n".join(f"- {e}" for e in errors[:30])
        )
    return "\n\n".join(parts)


def total_tokens(blocks: list[ContextBlock]) -> int:
    """Estimated prompt tokens of the included blocks (system prompt included)."""
    return sum(estimate_tokens(b.text) for b in blocks if b.included)


def build_plan_prompt(
    adventure: Any, existing: list[dict[str, Any]], count: int, direction: str
) -> str:
    regions = "\n".join(
        f"- {s['id']} {s['label']} [{s['status']}] at {s['map_x']}, {s['map_y']}: {s['description']}"
        for s in existing
    )
    return "\n\n".join(
        [
            _frame(adventure),
            f"EXISTING REGIONS:\n{regions or '- none'}",
            f"Plan {count} new regions.",
            f"AUTHOR'S DIRECTIONS: {direction or 'none'}",
        ]
    )
