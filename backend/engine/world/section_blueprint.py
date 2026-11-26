"""The blueprint of a region idea: parsed in region mode against the adventure's ledger, sent
to the LLM as a prompt block and written back over the generated region.
Spec: docs/specs/region_builder.md (section 6).
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.blueprint import apply_blueprint
from backend.engine.blueprint.region_mode import (
    RegionBlueprint,
    RegionWorld,
    analyze_region_blueprint,
)
from backend.engine.world.section_ledger import Ledger


def region_blueprint(section: dict[str, Any], ledger: Ledger) -> Optional[RegionBlueprint]:
    """The region blueprint of ``section``'s brief, or None for a plain-text brief."""
    world = RegionWorld(
        section_id=section["id"],
        taken_ids={i.upper() for i in ledger.taken_ids | ledger.award_keys},
        scene_ids=set(ledger.scene_ids),
        scene_sections=dict(ledger.scene_sections),
        linked_section_ids={link["to_section_id"] for link in section["planned_links"]},
    )
    return analyze_region_blueprint(section.get("brief") or "", world)


def apply_region_blueprint(
    region: dict[str, Any], blueprint: RegionBlueprint, ledger: Ledger
) -> list[str]:
    """Writes the blueprint's fixed values over the generated region; returns notes."""
    violations = apply_blueprint(region, blueprint.blueprint, known_scene_ids=ledger.scene_ids)
    # apply_blueprint creates every collection it knows; a region carries none of these.
    for key in ("audio_tracks", "sections"):
        if not region.get(key):
            region.pop(key, None)
    return [f"Blueprint: {v}" for v in violations]


def blueprint_summary(blueprint: Optional[RegionBlueprint]) -> Optional[dict[str, Any]]:
    """The preview's blueprint report: issues and how many blocks of each kind it has."""
    if blueprint is None:
        return None
    return {
        "issues": [issue.as_dict() for issue in blueprint.blueprint.issues],
        "kinds": blueprint.kinds(),
    }
