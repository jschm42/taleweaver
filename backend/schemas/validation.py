"""Pydantic schemas for the editor validation panel."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Severity = Literal["error", "warn"]


class ValidationFinding(BaseModel):
    """A single issue discovered by structural or AI validation."""

    severity: Severity
    code: str = Field(..., description="Stable identifier, e.g. 'unreachable_scene'.")
    message: str = Field(..., description="Human-readable description of the issue.")
    location: Optional[str] = Field(
        None,
        description="Optional scope hint (e.g. 'scene:START', 'object:safe_01').",
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional machine-readable extras for the UI or future tooling.",
    )


class ValidationRunRequest(BaseModel):
    include_ai: bool = Field(
        False,
        description="When False (default), only structural checks run. "
        "Used by the auto-validation on save. When True, also runs the "
        "AI logic validation pass; reserved for the manual button.",
    )


class ValidationRunResponse(BaseModel):
    structural_findings: List[ValidationFinding] = Field(default_factory=list)
    ai_findings: List[ValidationFinding] = Field(default_factory=list)
    ai_skipped_reason: Optional[str] = Field(
        None,
        description="When include_ai was True but AI was skipped, this explains why. "
        "Possible values: 'scene_limit_exceeded', 'ai_error'.",
    )
    run_at: str = Field(..., description="ISO-8601 timestamp of the run.")


FixTargetType = Literal[
    "scene",
    "object",
    "npc",
    "exit",
    "protagonist",
    "adventure",
]


class FixProposalEntityPatch(BaseModel):
    """One concrete patch proposal emitted by the AI for a single entity."""

    target_type: FixTargetType = Field(
        ..., description="Which entity kind the patch targets."
    )
    target_id: Optional[str] = Field(
        None,
        description="ID of the targeted scene/object/npc/exit. None for 'adventure' or 'protagonist'.",
    )
    description: str = Field(..., description="Human-readable explanation of this patch.")
    field_updates: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Field name -> new value. Keys must match the editor's patch "
            "payload (e.g. 'description', 'goal', 'character', 'walkthrough', 'plot')."
        ),
    )


class FixProposal(BaseModel):
    """One possible fix for an AI finding. Up to 3 are returned."""

    title: str = Field(..., description="Short human-readable title for the option.")
    summary: str = Field(
        ..., description="Two- to four-sentence description of how this fixes the finding."
    )
    rationale: Optional[str] = Field(
        None, description="Optional reasoning for why the AI picked this approach."
    )
    patches: List[FixProposalEntityPatch] = Field(
        default_factory=list,
        description="Concrete patches the engine should apply when this option is accepted.",
    )


class AIFixSuggestionsRequest(BaseModel):
    finding_code: str = Field(..., description="ValidationFinding.code to fix.")
    finding_message: str = Field(..., description="The original finding message.")
    finding_location: Optional[str] = Field(
        None, description="Optional location hint, e.g. 'scene:START'."
    )
    finding_context: Optional[Dict[str, Any]] = Field(
        None, description="Optional structured context from the original finding."
    )
    finding_severity: Severity = Field(
        "warn", description="Severity from the original finding."
    )


class AIFixSuggestionsResponse(BaseModel):
    finding_signature: str = Field(
        ...,
        description="Stable signature of the finding the suggestions were generated for.",
    )
    proposals: List[FixProposal] = Field(
        default_factory=list,
        description="Up to 3 distinct fix proposals. Empty list means the AI declined to suggest fixes.",
    )
    generated_at: str = Field(..., description="ISO-8601 timestamp of the generation.")
    error: Optional[str] = Field(
        None,
        description=(
            "When the AI call failed (timeout, network, parsing), this field "
            "carries a user-safe description and ``proposals`` stays empty. "
            "The HTTP status is still 200 so the client can render an inline "
            "retry affordance in the modal."
        ),
    )


class AIFixApplyRequest(BaseModel):
    finding_signature: str = Field(
        ...,
        description="Signature returned by /suggest-fix. Echoed back for traceability only.",
    )
    proposal: FixProposal = Field(..., description="The proposal the user wants to apply.")


class AIFixApplyResponse(BaseModel):
    status: Literal["applied", "no_op", "partial"] = Field(
        ..., description="Result of the apply attempt."
    )
    applied_targets: List[str] = Field(
        default_factory=list,
        description="List of '<target_type>:<target_id>' identifiers that were modified.",
    )
    message: Optional[str] = Field(
        None, description="Optional human-readable summary of what was changed."
    )