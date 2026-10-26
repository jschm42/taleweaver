"""Pydantic schemas for free-text World-Builder instructions in the editor."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.schemas.validation import FixProposal

WORLD_BUILDER_INSTRUCTION_MAX = 2000


class WorldBuilderInstructionRequest(BaseModel):
    instruction: str = Field(
        ...,
        min_length=3,
        max_length=WORLD_BUILDER_INSTRUCTION_MAX,
        description="Free-text change request from the author, e.g. 'Make the innkeeper grumpier'.",
    )


class WorldBuilderSuggestionsResponse(BaseModel):
    instruction: str = Field(..., description="The instruction the proposals answer.")
    proposals: list[FixProposal] = Field(
        default_factory=list,
        description="Up to 3 distinct change proposals. Empty when the AI declined.",
    )
    note: Optional[str] = Field(
        None, description="Optional AI explanation, e.g. why the instruction cannot be applied."
    )
    generated_at: str = Field(..., description="ISO-8601 timestamp of the generation.")
    error: Optional[str] = Field(
        None,
        description="User-safe failure description; HTTP status stays 200 so the modal can retry.",
    )


class WorldBuilderApplyRequest(BaseModel):
    proposal: FixProposal = Field(..., description="The proposal the author wants to apply.")


class WorldBuilderApplyResponse(BaseModel):
    status: Literal["applied", "no_op", "partial"]
    applied_targets: list[str] = Field(
        default_factory=list,
        description="List of '<target_type>:<target_id>' identifiers that were modified.",
    )
    message: Optional[str] = None
