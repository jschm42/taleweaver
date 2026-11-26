"""Travel time and fast travel checks (see backend/engine/rules/travel_time.py, fast_travel.py)."""

from __future__ import annotations

import json
import re

from backend.core.world_validation.context import ValidationContext, finding, scene_id
from backend.engine.rules.fast_travel import normalize_unlock_mode
from backend.engine.rules.travel_time import normalize_travel_minutes
from backend.engine.world.sections import is_stub, normalize_sections, section_id_or_none
from backend.schemas.validation import ValidationFinding


def _fast_travel_on(ctx: ValidationContext) -> bool:
    return ctx.adventure.get("fast_travel_enabled") is not False


def _points(ctx: ValidationContext) -> list[dict]:
    return [scene for scene in ctx.scenes if scene.get("is_fast_travel_point") is True]


def check_script_unlocked_points(ctx: ValidationContext) -> list[ValidationFinding]:
    """A point that only a script unlocks needs a script that calls unlock_fast_travel for it."""
    script_points = [
        p for p in _points(ctx) if normalize_unlock_mode(p.get("fast_travel_unlock")) == "script"
    ]
    if not script_points or not _fast_travel_on(ctx):
        return []
    # Scripts live in many places (adventure, sequences, scenes, entities); search all text.
    text = json.dumps(ctx.raw, default=str)
    findings: list[ValidationFinding] = []
    for point in script_points:
        sid = scene_id(point) or ""
        pattern = rf"unlock_fast_travel\(\s*\\?['\"]{re.escape(sid)}\\?['\"]"
        if re.search(pattern, text, flags=re.IGNORECASE):
            continue
        findings.append(
            finding(
                "warn",
                "fast_travel_point_never_unlocked",
                f"Fast travel point '{sid}' is unlocked by scripts only, but no script calls "
                f"tw.game.unlock_fast_travel('{sid}').",
                location=f"scene:{sid}",
                scene_id=sid,
            )
        )
    return findings


def check_region_travel(ctx: ValidationContext) -> list[ValidationFinding]:
    """With regions: each built region has a fast travel point, long ways have a travel time."""
    sections = [
        s for s in normalize_sections(ctx.adventure.get("world_sections")) if not is_stub(s)
    ]
    if not sections:
        return []
    by_scene = {
        sid: section_id_or_none(scene.get("section_id"))
        for scene in ctx.scenes
        if (sid := scene_id(scene))
    }
    findings: list[ValidationFinding] = []
    if _fast_travel_on(ctx):
        with_points = {by_scene.get(scene_id(p) or "") for p in _points(ctx)}
        findings.extend(
            finding(
                "warn",
                "section_without_fast_travel_point",
                f"Region '{s['label']}' has no fast travel point, so players can never fast "
                "travel there.",
                section_id=s["id"],
            )
            for s in sections
            if s["id"] not in with_points
        )
    for ex in ctx.exits:
        a, b = by_scene.get(ex.get("from_scene_id")), by_scene.get(ex.get("to_scene_id"))
        if not a or not b or a == b or normalize_travel_minutes(ex.get("travel_minutes")):
            continue
        findings.append(
            finding(
                "warn",
                "region_exit_without_travel_time",
                f"Exit {ex.get('from_scene_id')} -> {ex.get('to_scene_id')} connects two regions "
                "but takes no travel time.",
                location=f"exit:{ex.get('id', '?')}",
                exit_id=ex.get("id"),
            )
        )
    return findings
