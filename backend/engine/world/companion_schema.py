"""World-generation schema of the NPC ``companion`` block (see ``engine/party``)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from backend.engine.world.schema_base import WorldBaseSchema


class CompanionSchema(WorldBaseSchema):
    recruitable: bool = Field(
        True,
        description="The NPC can join the protagonist's party as a companion.",
    )
    starts_in_party: bool = Field(
        False,
        description="The NPC travels with the protagonist from the start (at most one such NPC).",
    )
    tactics: Literal["BALANCED", "OFFENSIVE", "DEFENSIVE", "SUPPORT"] = Field(
        "BALANCED", description="How the companion fights alongside the protagonist."
    )
    banter: Literal["NORMAL", "QUIET", "CHATTY"] = Field(
        "NORMAL", description="How often the companion comments on what happens."
    )
    downed_recovery: float = Field(
        0.25,
        description="Share of max HP (0.01-1) the companion gets back after being downed in a fight.",
    )
    recruit_mode: Literal["SCRIPT", "INSTANT", "ITEM"] = Field(
        "SCRIPT",
        description=(
            "How the player recruits it: SCRIPT = only a script (tw.party.recruit) after story "
            "events; INSTANT = the NPC's Recruit action makes it join at once; ITEM = the Recruit "
            "dialog asks for recruit_item_id, which the NPC keeps (wrong item = failure)."
        ),
    )
    recruit_item_id: str = Field(
        "",
        description="ITEM mode only: ID of an existing item the NPC wants before joining. Empty otherwise.",
    )
    recruit_hint: str = Field(
        "",
        description="Optional line shown in the Recruit dialog, e.g. 'Bring me something strong to drink.'",
    )

    model_config = {"extra": "forbid"}
