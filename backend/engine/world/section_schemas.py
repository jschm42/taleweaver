"""Structured LLM output for region generation (docs/specs/world_sections.md, 9.3-9.4).

``SectionManifest`` is one generated region: only new content, merged into the adventure by
``manifest_apply/section_merge.py``. ``CampaignPlan`` is the proposal of "Plan regions":
planned regions derived from the adventure's plot. Both reuse the world schemas, so every field the
manifest applier reads is accepted (``extra="forbid"``).
"""

from __future__ import annotations

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

    model_config = {"extra": "forbid"}


class CampaignPlan(WorldBaseSchema):
    """The proposal of "Plan regions": planned (stub) regions."""

    sections: list[WorldSectionSchema] = Field(
        ..., description="The planned regions (status 'stub') with map position and links."
    )

    model_config = {"extra": "forbid"}
