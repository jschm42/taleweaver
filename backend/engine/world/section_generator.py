"""Generates one planned region of an adventure, and plans new regions.

``generate_section``: chosen world context + gateways + brief + requirements -> LLM
``SectionManifest`` -> fix-ups -> validation; on errors one retry with the errors in the
prompt, then ``SectionGenerationError``. A valid region is merged into the template
(``manifest_apply/section_merge.py``). ``preview_section_prompt`` builds the same prompt
without an LLM call and reports its blocks with token estimates.

``plan_sections``: returns a reviewable proposal of planned regions; nothing is
stored until the author applies it in the editor.
Spec: docs/specs/world_sections.md (9.3-9.5), docs/specs/region_builder.md (5, 7, 8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.llm_router import GameMasterLLM
from backend.engine.blueprint.region_mode import RegionBlueprint
from backend.engine.manifest_apply.section_media import RegionMedia
from backend.engine.manifest_apply.section_merge import merge_section
from backend.engine.sessions.start_scene import resolve_initial_scene_id
from backend.engine.world.section_blueprint import (
    apply_region_blueprint,
    blueprint_summary,
    region_blueprint,
)
from backend.engine.world.section_context import ContextBlock, ContextSource, normalize_context
from backend.engine.world.section_gateways import built_neighbours
from backend.engine.world.section_ledger import Ledger, ledger_from_rows, load_world_rows
from backend.engine.world.section_prompt import (
    PLAN_SYSTEM_PROMPT,
    SECTION_SYSTEM_PROMPT,
    build_plan_prompt,
    build_section_prompt,
    region_blocks,
    total_tokens,
)
from backend.engine.world.section_requirements import normalize_options
from backend.engine.world.section_schemas import CampaignPlan, SectionManifest
from backend.engine.world.section_validation import prepare_section, validate_section
from backend.engine.world.sections import normalize_sections
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

MAX_ATTEMPTS = 2


class SectionGenerationError(Exception):
    """The generated region stayed invalid; nothing was applied."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[:5]) or "The region could not be generated.")
        self.errors = errors


@dataclass
class RegionPrompt:
    """The assembled prompt of one region plus what validation needs."""

    blocks: list[ContextBlock]
    ledger: Ledger
    neighbour_ids: list[str]
    blueprint: Optional[RegionBlueprint] = None

    def user_prompt(self, errors: list[str]) -> str:
        return build_section_prompt(self.blocks, errors)


def normalize_settings(raw: Any) -> dict[str, Any]:
    """``{context, options}`` of a generation request with all defaults filled in."""
    data = raw if isinstance(raw, dict) else {}
    return {
        "context": normalize_context(data.get("context")),
        "options": normalize_options(data.get("options")),
    }


def _llm(user: User) -> tuple[GameMasterLLM, str]:
    # Lazy import: world_generator imports the manifest applier, which imports this package.
    from backend.engine.world.world_generator import _resolve_generator_provider_and_model

    provider, model = _resolve_generator_provider_and_model(user, None, None)
    return GameMasterLLM(user, provider=provider, model_category="generator"), model


async def _region(
    db: AsyncSession, template_id: str, section_id: str
) -> tuple[AdventureTemplate, dict[str, Any], list[dict[str, Any]]]:
    adventure = await db.get(AdventureTemplate, template_id)
    sections = normalize_sections(adventure.world_sections if adventure else None)
    section = next((s for s in sections if s["id"] == section_id), None)
    if adventure is None or section is None:
        raise SectionGenerationError([f"Region '{section_id}' not found."])
    return adventure, section, sections


async def build_region_prompt(
    db: AsyncSession,
    adventure: AdventureTemplate,
    section: dict[str, Any],
    sections: list[dict[str, Any]],
    settings: Optional[dict[str, Any]] = None,
) -> RegionPrompt:
    """The region prompt for the given settings (``None`` = all defaults)."""
    chosen = normalize_settings(settings)
    rows = await load_world_rows(db, adventure.id)
    neighbours = built_neighbours(section, sections)
    ledger = ledger_from_rows(adventure, rows)
    blueprint = region_blueprint(section, ledger)
    strictness = chosen["options"]["generation_strictness"]
    source = ContextSource(
        adventure=adventure,
        # With a blueprint the brief is its premise; the blocks follow as their own part.
        section={**section, "brief": blueprint.premise} if blueprint else section,
        sections=sections,
        rows=rows,
        walkthroughs=chosen["context"]["walkthroughs"],
        start_scene_id=await resolve_initial_scene_id(db, adventure.id) if rows.scenes else None,
    )
    blueprint_text = blueprint.prompt_section(strictness) if blueprint else ""
    return RegionPrompt(
        blocks=region_blocks(
            source, chosen["context"], chosen["options"], neighbours, blueprint_text
        ),
        ledger=ledger,
        neighbour_ids=[n["to_section_id"] for n in neighbours],
        blueprint=blueprint,
    )


def _with_gateways(
    section: dict[str, Any], sections: list[dict[str, Any]], gateways: dict[str, list[str]]
) -> dict[str, Any]:
    links = [
        {**link, "gateway_scene_ids": gateways.get(link["to_section_id"], [])}
        for link in section["planned_links"]
    ]
    # Normalized like a saved region, so the picks are cleaned the same way.
    others = [s for s in sections if s["id"] != section["id"]]
    normalized = normalize_sections([*others, {**section, "planned_links": links}])
    return next(s for s in normalized if s["id"] == section["id"])


async def preview_section_prompt(
    db: AsyncSession,
    template_id: str,
    section_id: str,
    settings: Optional[dict[str, Any]],
    brief: Optional[str] = None,
    include_prompt: bool = False,
    gateways: Optional[dict[str, list[str]]] = None,
) -> dict[str, Any]:
    """The prompt's blocks with token estimates, without an LLM call. ``brief`` and
    ``gateways`` (picked gateway scenes per linked region) override the saved values."""
    adventure, section, sections = await _region(db, template_id, section_id)
    if brief is not None:
        section = {**section, "brief": brief.strip()}
    if gateways is not None:
        section = _with_gateways(section, sections, gateways)
    prompt = await build_region_prompt(db, adventure, section, sections, settings)
    result: dict[str, Any] = {
        "blocks": [
            {
                "id": b.id,
                "tokens": b.tokens,
                "items": b.count,
                "empty": not b.text,
                "always": b.always,
                "included": b.included,
                "detail": b.detail,
            }
            for b in prompt.blocks
        ],
        "total_tokens": total_tokens(prompt.blocks),
        "blueprint": blueprint_summary(prompt.blueprint),
    }
    if include_prompt:
        result["prompt"] = prompt.user_prompt([])
    return result


async def generate_section(
    db: AsyncSession,
    template_id: str,
    section_id: str,
    user: User,
    settings: Optional[dict[str, Any]] = None,
) -> list[str]:
    """Generates, validates and merges one planned region; returns fix-up notes."""
    adventure, section, sections = await _region(db, template_id, section_id)
    prompt = await build_region_prompt(db, adventure, section, sections, settings)
    if prompt.blueprint and prompt.blueprint.errors:
        raise SectionGenerationError(prompt.blueprint.errors)
    llm, model = _llm(user)
    errors: list[str] = []
    for _attempt in range(MAX_ATTEMPTS):
        result: SectionManifest = await llm.aexecute_complex_task(
            system_prompt=SECTION_SYSTEM_PROMPT,
            user_prompt=prompt.user_prompt(errors),
            response_model=SectionManifest,
            model=model,
            adventure_id=template_id,
            operation="generate_section",
            phase="analysis",
        )
        region = result.model_dump()
        notes = (
            apply_region_blueprint(region, prompt.blueprint, prompt.ledger)
            if prompt.blueprint
            else []
        )
        notes += prepare_section(region, section_id, prompt.ledger)
        errors = validate_section(region, prompt.ledger, prompt.neighbour_ids)
        if not errors:
            media = RegionMedia.from_options(normalize_settings(settings)["options"])
            notes += await merge_section(db, template_id, section_id, region, user, media)
            return notes
    raise SectionGenerationError(errors)


def _proposal(plan: CampaignPlan, existing: list[dict[str, Any]]) -> dict[str, Any]:
    taken = {s["id"] for s in existing}
    new = [
        {**s, "status": "stub", "order_index": len(existing) + index}
        for index, s in enumerate(normalize_sections([s.model_dump() for s in plan.sections]))
        if s["id"] not in taken
    ]
    return {"sections": normalize_sections([*existing, *new])}


async def plan_sections(
    db: AsyncSession, template_id: str, user: User, count: int, direction: str
) -> dict[str, Any]:
    """A proposal {sections}: the existing regions plus ``count`` planned ones."""
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
