"""Generation schema for the adventure's ``game_over_rules`` (what happens at 0 HP)."""

from typing import Literal

from pydantic import Field

from backend.engine.world.schema_base import WorldBaseSchema


class GameOverRulesSchema(WorldBaseSchema):
    on_zero_hp: Literal["game_over", "respawn"] = Field(
        "game_over",
        description=(
            "What happens when the protagonist falls to 0 HP: 'game_over' ends the adventure; "
            "'respawn' knocks them out and they wake up at the last scene with "
            "`is_respawn_point` they reached (else the start scene). Scripted defeats stay final."
        ),
    )
    respawn_hp_percent: int = Field(
        25, ge=1, le=100, description="Respawn mode: share of max HP after waking up (percent)."
    )
