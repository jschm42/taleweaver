"""Prompts for region generation and for planning regions (docs/specs/world_sections.md, 9.3-9.4).

The region prompt holds only what the region needs: the adventure frame, the campaign
outline, the world ledger, the region's brief and the gateway scenes of its built neighbours.
"""

from __future__ import annotations

from typing import Any

from backend.engine.world.section_ledger import Ledger
from backend.engine.world.section_outline import outline_prompt_block
from backend.engine.world.world_scripting_prompt import TW_API_REFERENCE

# Gateway scenes shown per neighbouring region.
_GATEWAY_SCENES = 8

SECTION_SYSTEM_PROMPT = (
    "You are the World-Builder of TaleWeaver, a text adventure engine. You extend an EXISTING "
    "adventure with exactly ONE new region of its world map. Write only new content; never "
    "repeat or change anything listed in the WORLD LEDGER.\n\n"
    "RULES:\n"
    "- 6-10 new scenes with vivid descriptions, all inside this region.\n"
    "- Ids are UPPERCASE slugs and must not appear in the WORLD LEDGER (scenes, characters and "
    "items share one id space).\n"
    "- Connect the region to the listed gateway scenes of its neighbours with exits "
    "(`exit_type: bidirectional` unless one-way makes sense). Give these long ways the listed "
    "`travel_minutes`. Every new scene must be reachable through exits.\n"
    "- Mark one or two central scenes `is_fast_travel_point: true`, one of them where the "
    "player arrives.\n"
    "- Characters start in new scenes (`start_scene_id`); items start in a new scene, or in a "
    "character's or container's inventory. Locks use items that exist in the ledger or in this "
    "region, and the key must be obtainable.\n"
    "- Plant and resolve what the CAMPAIGN OUTLINE asks of this region; report it in "
    "`thread_updates`.\n"
    "- Quests, awards and chapters are optional; add a chapter only when the region carries "
    "its own story step.\n"
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
    return (
        f"ADVENTURE: {adventure.title}\n"
        f"Language of all player-facing text: {adventure.language or 'English'}\n"
        f"Plot: {adventure.plot or ''}\n"
        f"Rules: {adventure.rules or ''}"
    )


def _gateway_block(ledger: Ledger, neighbours: list[dict[str, Any]], scenes: dict[str, Any]) -> str:
    if not neighbours:
        return "GATEWAY SCENES: none listed; connect the region to any fitting existing scene."
    lines = ["GATEWAY SCENES (connect the new region to some of these):"]
    for link in neighbours:
        minutes = link.get("travel_minutes")
        travel = f", travel_minutes {minutes}" if minutes else ""
        lines.append(f"Region {link['to_section_id']}{travel}:")
        for scene_id in ledger.scenes_of(link["to_section_id"])[:_GATEWAY_SCENES]:
            scene = scenes.get(scene_id)
            text = (getattr(scene, "description", "") or "")[:240]
            lines.append(f"- {scene_id} ({getattr(scene, 'label', scene_id)}): {text}")
    return "\n".join(lines)


def build_section_prompt(
    adventure: Any,
    section: dict[str, Any],
    ledger: Ledger,
    neighbours: list[dict[str, Any]],
    scenes: dict[str, Any],
    errors: list[str],
) -> str:
    """The user prompt for one region; ``errors`` of a failed attempt are listed to fix."""
    parts = [
        _frame(adventure),
        outline_prompt_block(adventure.world_outline, section["id"]),
        ledger.text,
        f"THE NEW REGION: {section['id']} - {section['label']}\n"
        f"Description: {section['description']}\nBrief: {section['brief'] or 'none'}",
        _gateway_block(ledger, neighbours, scenes),
    ]
    if errors:
        parts.append(
            "YOUR LAST ATTEMPT WAS REJECTED. Fix every one of these problems:\n"
            + "\n".join(f"- {e}" for e in errors[:30])
        )
    return "\n\n".join(parts)


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
