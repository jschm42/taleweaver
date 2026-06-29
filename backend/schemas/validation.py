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