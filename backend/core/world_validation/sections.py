"""World section (region) checks (see backend/engine/world/sections.py)."""

from __future__ import annotations

from backend.core.world_validation.context import ValidationContext, finding, scene_id
from backend.engine.world.sections import is_stub, normalize_sections, section_id_or_none
from backend.schemas.validation import ValidationFinding

# Unassigned scenes named in one finding; the rest is summarized.
_LISTED_SCENES = 8


def _scene_sections(ctx: ValidationContext) -> dict[str, str | None]:
    return {
        sid: section_id_or_none(scene.get("section_id"))
        for scene in ctx.scenes
        if (sid := scene_id(scene))
    }


def check_scene_sections(ctx: ValidationContext) -> list[ValidationFinding]:
    """A scene's section must exist and must not be a planned (stub) section."""
    sections = {s["id"]: s for s in normalize_sections(ctx.adventure.get("world_sections"))}
    findings: list[ValidationFinding] = []
    for sid, section_id in _scene_sections(ctx).items():
        if section_id is None:
            continue
        section = sections.get(section_id)
        if section is None:
            findings.append(
                finding(
                    "error",
                    "scene_section_missing",
                    f"Scene '{sid}' belongs to section '{section_id}', which does not exist.",
                    location=f"scene:{sid}",
                    scene_id=sid,
                    section_id=section_id,
                )
            )
        elif is_stub(section):
            findings.append(
                finding(
                    "error",
                    "scene_in_planned_section",
                    f"Scene '{sid}' belongs to '{section['label']}', which is only planned. "
                    "Mark the section as built, or move the scene.",
                    location=f"scene:{sid}",
                    scene_id=sid,
                    section_id=section_id,
                )
            )
    return findings


def check_section_coverage(ctx: ValidationContext) -> list[ValidationFinding]:
    """With sections, every built section has scenes and every scene has a section."""
    sections = normalize_sections(ctx.adventure.get("world_sections"))
    if not sections:
        return []
    scene_sections = _scene_sections(ctx)
    used = set(scene_sections.values())
    findings = [
        finding(
            "warn",
            "section_without_scenes",
            f"Section '{section['label']}' is marked as built but has no scenes. "
            "Add scenes or mark it as planned.",
            section_id=section["id"],
        )
        for section in sections
        if not is_stub(section) and section["id"] not in used
    ]
    unassigned = sorted(sid for sid, section_id in scene_sections.items() if section_id is None)
    if unassigned:
        listed = ", ".join(unassigned[:_LISTED_SCENES])
        more = len(unassigned) - _LISTED_SCENES
        suffix = f" and {more} more" if more > 0 else ""
        findings.append(
            finding(
                "warn",
                "scene_without_section",
                f"{len(unassigned)} scene(s) belong to no section: {listed}{suffix}. "
                "They do not appear on the world map.",
                scene_ids=unassigned,
            )
        )
    return findings
