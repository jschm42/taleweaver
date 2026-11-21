"""Structured LLM output for region generation (docs/specs/world_sections.md, 9.3-9.4).

``SectionManifest`` is one generated region: only new content, merged into the adventure by
``manifest_apply/section_merge.py``. ``CampaignPlan`` is the proposal of "Plan regions": a
campaign outline plus planned regions. Both reuse the world schemas, so every field the
manifest applier reads is accepted (``extra="forbid"``).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from backend.engine.world.schema_base import WorldBaseSchema
from backend.engine.world.world_object_schema import WorldObjectSchema
from backend.engine.world.world_schemas import (
    AwardTemplateSchema,
    QuestSchema,
    SequenceSchema,
    WorldExitSchema,
    WorldNPCSchema,
    WorldSceneSchema,
    WorldScriptSchema,
)
from backend.engine.world.world_section_schema import WorldSectionSchema


class ThreadUpdateSchema(WorldBaseSchema):
    """A story thread of the campaign outline this region opened or resolved."""

    id: str = Field(..., description="Uppercase slug of the thread, e.g. MISSING_SURVEYOR.")
    status: Literal["open", "resolved"] = Field("open", description="Status after this region.")
    opened_in: Optional[str] = Field(None, description="Region id where the thread starts.")
    resolved_in: Optional[str] = Field(None, description="Region id where it is resolved.")
    note: Optional[str] = Field(None, description="One sentence on the thread's state.")

    model_config = {"extra": "forbid"}


class SectionManifest(WorldBaseSchema):
    """One new region of an existing adventure: only content that does not exist yet."""

    summary: str = Field(
        ...,
        description=(
            "3-5 sentences: what the region contains, its key characters, items and open "
            "hooks. Later regions are generated from this summary."
        ),
    )
    scenes: list[WorldSceneSchema] = Field(..., description="The new scenes of this region.")
    exits: list[WorldExitSchema] = Field(
        ...,
        description=(
            "Exits between the new scenes, plus the gateway exits that connect them to the "
            "listed gateway scenes of neighbouring regions."
        ),
    )
    npcs: list[WorldNPCSchema] = Field(default=[], description="New characters of the region.")
    objects: list[WorldObjectSchema] = Field(default=[], description="New items of the region.")
    quests: list[QuestSchema] = Field(default=[], description="New side quests. Use [] if none.")
    awards: list[AwardTemplateSchema] = Field(default=[], description="New awards. Use [] if none.")
    sequences: list[SequenceSchema] = Field(
        default=[], description="New chapters that play in this region. Use [] if none."
    )
    scripts: list[WorldScriptSchema] = Field(
        default=[], description="New event scripts (never on_init). Use [] if none."
    )
    thread_updates: list[ThreadUpdateSchema] = Field(
        default=[], description="Campaign threads this region opens or resolves."
    )

    model_config = {"extra": "forbid"}


class OutlineSectionSchema(WorldBaseSchema):
    id: str = Field(..., description="Region id, the same as in `sections`.")
    purpose: str = Field(..., description="What the region does for the story, one sentence.")
    gating: Optional[str] = Field(None, description="What the player needs to get in, if anything.")
    plants: list[str] = Field(default=[], description="Hooks this region plants for later ones.")
    resolves: list[str] = Field(default=[], description="Threads this region resolves.")

    model_config = {"extra": "forbid"}


class CampaignPlan(WorldBaseSchema):
    """The proposal of "Plan regions": outline plus planned (stub) regions."""

    premise: str = Field(..., description="The campaign premise in 2-3 sentences.")
    arc: list[str] = Field(..., description="3-5 acts of the campaign, one sentence each.")
    sections: list[WorldSectionSchema] = Field(
        ..., description="The planned regions (status 'stub') with map position and links."
    )
    outline_sections: list[OutlineSectionSchema] = Field(
        ..., description="One entry per region: purpose, gating, plants, resolves."
    )
    threads: list[ThreadUpdateSchema] = Field(
        default=[], description="Story threads that run across regions."
    )

    model_config = {"extra": "forbid"}
