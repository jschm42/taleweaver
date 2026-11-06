"""World-generation schemas for switch mechanics (states, transitions, gates, outcomes)."""

from typing import Any, Optional

from pydantic import Field, model_serializer

from backend.engine.world.schema_base import WorldBaseSchema


class SwitchGatesSchema(WorldBaseSchema):
    item: Optional[str] = Field(
        default="", description="The item ID needed to pass this transition."
    )
    code: Optional[str] = Field(
        default="", description="The code/password needed to pass this transition."
    )
    rule: Optional[str] = Field(
        default="", description="A soft narrative rule needed to pass this transition."
    )
    expression: Optional[str] = Field(
        default="",
        description="A boolean Python expression evaluated against tw (e.g. tw.vars.get('flag') == True).",
    )
    condition: Optional[str] = Field(
        default="",
        description="Alias for expression.",
    )

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        expr = self.expression or self.condition or ""
        return {
            "item": self.item or "",
            "code": self.code or "",
            "rule": self.rule or "",
            "expression": expr,
            "condition": expr,
        }

    model_config = {"populate_by_name": True, "extra": "forbid"}


class SwitchStateLabelSchema(WorldBaseSchema):
    state: str = Field(..., description="State ID from switch_states, e.g. 'HALF-OPEN'.")
    label: str = Field(
        ..., description="Short in-game text for this state (max 20 characters), e.g. 'Half open'."
    )


class SwitchTransitionSchema(WorldBaseSchema):
    from_state: Optional[str] = Field(
        default="",
        alias="from",
        description="The starting state of this transition. Omit or leave empty to apply to any current state.",
    )
    to_state: str = Field(..., alias="to", description="The target state of this transition.")
    gates: Optional[SwitchGatesSchema] = Field(
        default=None, description="Optional lock gates required to allow the transition."
    )
    fail_message: Optional[str] = Field(
        default="", description="The failure message narrated if gates are not met."
    )
    success_message: Optional[str] = Field(
        default="", description="Optional success message narrated when transition passes."
    )
    on_success_script: Optional[str] = Field(
        default="", description="Optional script executed when this transition succeeds."
    )
    on_failure_script: Optional[str] = Field(
        default="", description="Optional script executed when this transition fails."
    )

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "to": self.to_state,
            "gates": self.gates.model_dump() if self.gates else None,
            "fail_message": self.fail_message or "",
        }
        if self.from_state:
            payload["from"] = self.from_state
        if self.success_message:
            payload["success_message"] = self.success_message
        if self.on_success_script:
            payload["on_success_script"] = self.on_success_script
        if self.on_failure_script:
            payload["on_failure_script"] = self.on_failure_script
        return payload

    model_config = {"populate_by_name": True, "extra": "forbid"}


class SwitchEffectSchema(WorldBaseSchema):
    type: str = Field(
        ...,
        description="The effect type: unlock_exit, unlock_container, unlock_item (release a take-locked item), lock_item, or story_flag.",
    )
    target_id: Optional[str] = Field(
        default="",
        description="The ID of the target exit, container or item. Keep empty if not applicable.",
    )
    key: Optional[str] = Field(
        default="", description="The story flag key. Keep empty if not applicable."
    )
    model_config = {"extra": "forbid"}


class SwitchOutcomeSchema(WorldBaseSchema):
    on_state: str = Field(..., description="The state trigger for these effects.")
    effects: list[SwitchEffectSchema] = Field(
        ..., description="List of effects triggered when the state is entered."
    )
    model_config = {"extra": "forbid"}
