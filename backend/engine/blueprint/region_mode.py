"""Blueprint region mode: a blueprint in the Region Builder's region idea.

A region only adds content to an existing adventure (docs/specs/region_builder.md, 6):

* ``World``, ``Protagonist`` and ``Audio`` blocks are global; they are dropped with a warning.
* ``Section`` blocks are dropped too (the region is edited in the builder's Region card).
* A block may not declare an id that already exists in the adventure (error).
* Ids of the adventure may be referenced (exit ends, keys, requirements); they are not
  reported as missing. An exit must touch at least one new scene, and an exit to an existing
  scene outside the linked regions gets a warning (only when the region has links).
* Scenes belong to the region being built; ``section`` naming another region is an error.
* Chapters are numbered from 1 within the region and appended after the existing chapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.engine.blueprint.models import Blueprint, BlueprintBlock
from backend.engine.blueprint.parser import has_blueprint_tags, parse_blueprint
from backend.engine.blueprint.prompt import render_blueprint_prompt
from backend.engine.blueprint.validator import validate_blueprint

GLOBAL_KINDS = {"world", "protagonist", "audio"}
_ID_KINDS = {"scene", "npc", "item", "sidequest", "award", "script"}
_REFERENCED_PREFIX = "is referenced but not declared"
_REGION_RULES = (
    "REGION BLUEPRINT NOTES:\n"
    "- The blueprint describes only the NEW region. Ids that already exist in the adventure "
    "may appear as references (exit ends, keys, requirements); never create them again.\n"
    "- Exits from or to an existing scene are the region's gateway exits.\n"
    "- Chapters (`sequences`) are numbered from 1 within this region. Keep exactly these "
    "`order` values in your output; they are moved after the existing chapters afterwards.\n"
)


@dataclass
class RegionWorld:
    """What region mode checks a blueprint against."""

    section_id: str
    taken_ids: set[str] = field(default_factory=set)
    scene_ids: set[str] = field(default_factory=set)
    scene_sections: dict[str, Optional[str]] = field(default_factory=dict)
    linked_section_ids: set[str] = field(default_factory=set)


@dataclass
class RegionBlueprint:
    blueprint: Blueprint
    premise: str
    missing_ids: list[str]

    @property
    def errors(self) -> list[str]:
        return [f"line {i.line}: {i.message}" for i in self.blueprint.errors]

    def prompt_section(self, generation_strictness: str) -> str:
        rendered = render_blueprint_prompt(self.blueprint, self.missing_ids, generation_strictness)
        return f"{_REGION_RULES}{rendered}" if rendered else ""

    def kinds(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for block in self.blueprint.blocks:
            counts[block.kind] = counts.get(block.kind, 0) + 1
        return counts


def _label(block: BlueprintBlock) -> str:
    return f"[{block.kind.title()}: {block.ref or block.name}]"


def _drop_global_blocks(blueprint: Blueprint) -> None:
    kept = []
    for block in blueprint.blocks:
        if block.kind in GLOBAL_KINDS or block.kind == "section":
            reason = (
                "is edited in the Region card"
                if block.kind == "section"
                else "is global to the adventure"
            )
            blueprint.add_issue(block.line, f"{_label(block)} {reason}; ignored here.", "warning")
            continue
        kept.append(block)
    blueprint.blocks = kept


def _check_redefinitions(blueprint: Blueprint, world: RegionWorld) -> None:
    for block in blueprint.blocks:
        if block.kind in _ID_KINDS and block.ref and block.ref.upper() in world.taken_ids:
            blueprint.add_issue(
                block.line,
                f"{_label(block)} exists already; the Region Builder only adds content.",
            )


def _check_scene_regions(blueprint: Blueprint, world: RegionWorld) -> None:
    for block in blueprint.of_kind("scene"):
        value = block.fields.get("section_id")
        target = str(value.value or "").upper() if value else ""
        if target and target != world.section_id:
            blueprint.add_issue(
                block.line, f"{_label(block)} belongs to {target}, not to the region being built."
            )


def _check_exits(blueprint: Blueprint, world: RegionWorld) -> None:
    new_scenes = {b.ref.upper() for b in blueprint.of_kind("scene") if b.ref}
    for block in blueprint.of_kind("exit"):
        fixed = block.fixed()
        ends = [str(fixed.get(k) or "").upper() for k in ("from_scene_id", "to_scene_id")]
        existing = [end for end in ends if end in world.scene_ids and end not in new_scenes]
        if len(existing) == len(ends):
            blueprint.add_issue(block.line, f"{_label(block)} only joins existing scenes.")
            continue
        # Without planned links any existing scene is a fitting gateway.
        if not world.linked_section_ids:
            continue
        for end in existing:
            region = world.scene_sections.get(end)
            if region not in world.linked_section_ids:
                blueprint.add_issue(
                    block.line,
                    f"{_label(block)} leads to {end}, which is not in a linked region.",
                    "warning",
                )


def _forget_existing_references(
    blueprint: Blueprint, missing: list[str], world: RegionWorld
) -> list[str]:
    known = world.taken_ids | world.scene_ids
    existing = {ref for ref in missing if ref.upper() in known}
    blueprint.issues = [
        issue
        for issue in blueprint.issues
        if not (
            _REFERENCED_PREFIX in issue.message
            and any(issue.message.startswith(f"'{ref}'") for ref in existing)
        )
    ]
    return [ref for ref in missing if ref not in existing]


def analyze_region_blueprint(text: str, world: RegionWorld) -> Optional[RegionBlueprint]:
    """The region blueprint of a region idea, or None when the text uses no tags."""
    if not has_blueprint_tags(text):
        return None
    blueprint = parse_blueprint(text)
    _drop_global_blocks(blueprint)
    missing = validate_blueprint(blueprint)
    missing = _forget_existing_references(blueprint, missing, world)
    _check_redefinitions(blueprint, world)
    _check_scene_regions(blueprint, world)
    _check_exits(blueprint, world)
    return RegionBlueprint(blueprint=blueprint, premise=blueprint.premise, missing_ids=missing)
