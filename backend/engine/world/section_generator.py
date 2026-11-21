"""Generates one planned region of an adventure, and plans new regions.

``generate_section``: outline + ledger + brief -> ``SectionManifest`` -> fix-ups -> validation;
on errors one retry with the errors in the prompt, then ``SectionGenerationError``. A valid
region is merged into the template (``manifest_apply/section_merge.py``).

``plan_sections``: returns a reviewable proposal (outline and planned regions); nothing is
stored until the author applies it in the editor.
Spec: docs/specs/world_sections.md (9.3-9.5).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.llm_router import GameMasterLLM
from backend.engine.manifest_apply.section_merge import merge_section
from backend.engine.world.section_ledger import build_ledger
from backend.engine.world.section_outline import normalize_outline
from backend.engine.world.section_prompt import (
    PLAN_SYSTEM_PROMPT,
    SECTION_SYSTEM_PROMPT,
    build_plan_prompt,
    build_section_prompt,
)
from backend.engine.world.section_schemas import CampaignPlan, SectionManifest
from backend.engine.world.section_validation import prepare_section, validate_section
from backend.engine.world.sections import is_stub, normalize_sections
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene

MAX_ATTEMPTS = 2


class SectionGenerationError(Exception):
    """The generated region stayed invalid; nothing was applied."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[:5]) or "The region could not be generated.")
        self.errors = errors


def _llm(user: User) -> tuple[GameMasterLLM, str]:
    # Lazy import: world_generator imports the manifest applier, which imports this package.
    from backend.engine.world.world_generator import _resolve_generator_provider_and_model

    provider, model = _resolve_generator_provider_and_model(user, None, None)
    return GameMasterLLM(user, provider=provider, model_category="generator"), model


def _built_neighbours(
    section: dict[str, Any], sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    built = {s["id"] for s in sections if not is_stub(s)}
    return [link for link in section["planned_links"] if link["to_section_id"] in built]


async def _template_scenes(db: AsyncSession, template_id: str) -> dict[str, WorldScene]:
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id, WorldScene.session_id.is_(None)
        )
    )
    return {scene.id: scene for scene in res.scalars().all()}


async def generate_section(
    db: AsyncSession, template_id: str, section_id: str, user: User
) -> list[str]:
    """Generates, validates and merges one planned region; returns fix-up notes."""
    adventure = await db.get(AdventureTemplate, template_id)
    sections = normalize_sections(adventure.world_sections if adventure else None)
    section = next((s for s in sections if s["id"] == section_id), None)
    if adventure is None or section is None:
        raise SectionGenerationError([f"Region '{section_id}' not found."])
    ledger = await build_ledger(db, adventure)
    neighbours = _built_neighbours(section, sections)
    scenes = await _template_scenes(db, template_id)
    llm, model = _llm(user)
    errors: list[str] = []
    for _attempt in range(MAX_ATTEMPTS):
        result: SectionManifest = await llm.aexecute_complex_task(
            system_prompt=SECTION_SYSTEM_PROMPT,
            user_prompt=build_section_prompt(
                adventure, section, ledger, neighbours, scenes, errors
            ),
            response_model=SectionManifest,
            model=model,
            adventure_id=template_id,
            operation="generate_section",
            phase="analysis",
        )
        region = result.model_dump()
        notes = prepare_section(region, section_id, ledger)
        errors = validate_section(region, ledger, [n["to_section_id"] for n in neighbours])
        if not errors:
            await merge_section(db, template_id, section_id, region, user)
            return notes
    raise SectionGenerationError(errors)


def _proposal(plan: CampaignPlan, existing: list[dict[str, Any]]) -> dict[str, Any]:
    taken = {s["id"] for s in existing}
    new = [
        {**s, "status": "stub", "order_index": len(existing) + index}
        for index, s in enumerate(normalize_sections([s.model_dump() for s in plan.sections]))
        if s["id"] not in taken
    ]
    outline = normalize_outline(
        {
            "premise": plan.premise,
            "arc": plan.arc,
            "sections": [s.model_dump() for s in plan.outline_sections],
            "threads": [t.model_dump() for t in plan.threads],
        }
    )
    return {"outline": outline, "sections": normalize_sections([*existing, *new])}


async def plan_sections(
    db: AsyncSession, template_id: str, user: User, count: int, direction: str
) -> dict[str, Any]:
    """A proposal {outline, sections}: the existing regions plus ``count`` planned ones."""
    adventure = await db.get(AdventureTemplate, template_id)
    if adventure is None:
        raise ValueError(f"Adventure '{template_id}' not found.")
    existing = normalize_sections(adventure.world_sections)
    llm, model = _llm(user)
    plan: CampaignPlan = await llm.aexecute_complex_task(
        system_prompt=PLAN_SYSTEM_PROMPT,
        user_prompt=build_plan_prompt(adventure, existing, count, direction),
        response_model=CampaignPlan,
        model=model,
        adventure_id=template_id,
        operation="plan_sections",
        phase="analysis",
    )
    return _proposal(plan, existing)
