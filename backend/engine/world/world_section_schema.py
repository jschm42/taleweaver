"""World generation schema for world sections (regions) and their planned links.

The manifest applier reads these fields (``engine/world/sections.py``); the schemas use
``extra="forbid"`` like every world schema, so every field the applier reads must exist here.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from backend.engine.world.schema_base import WorldBaseSchema


class SectionLinkSchema(WorldBaseSchema):
    """A planned route from a stub section to a neighbour (its exits do not exist yet)."""

    to_section_id: str = Field(..., description="ID of the neighbouring section.")
    travel_minutes: Optional[int] = Field(
        None, description="Planned in-game travel time in minutes, e.g. 480 for a day's march."
    )
    note: Optional[str] = Field(None, description="Optional short note, e.g. 'mountain pass'.")

    model_config = {"extra": "forbid"}


class WorldSectionSchema(WorldBaseSchema):
    """A region of the world map that groups scenes (a town, a mine, a mountain range)."""

    id: str = Field(..., description="Uppercase slug, e.g. HARBOR_TOWN.")
    label: str = Field(..., description="Region name shown to the player, e.g. 'Harbor Town'.")
    description: str = Field(
        default="", description="One paragraph: what the region is like and why it matters."
    )
    map_x: Optional[float] = Field(
        None, description="Horizontal position on the world map in percent (0 = west, 100 = east)."
    )
    map_y: Optional[float] = Field(
        None, description="Vertical position on the world map in percent (0 = north, 100 = south)."
    )
    status: Literal["built", "stub"] = Field(
        default="built",
        description=(
            "'built' when scenes of this adventure belong to the region; 'stub' for a region "
            "that is only planned (no scenes yet)."
        ),
    )
    brief: Optional[str] = Field(
        default="", description="Stubs only: directions for building the region later."
    )
    planned_links: list[SectionLinkSchema] = Field(
        default=[], description="Stubs only: planned routes to neighbouring regions."
    )

    model_config = {"extra": "forbid"}
