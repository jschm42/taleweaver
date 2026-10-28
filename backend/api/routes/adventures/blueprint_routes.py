"""Pre-flight check of a Story Idea blueprint before generation starts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.core.auth import get_current_user
from backend.engine.blueprint import analyze_blueprint, has_blueprint_tags
from backend.models.user import User

router = APIRouter(tags=["Adventure Creation"])

MAX_STORY_IDEA_CHARS = 100_000


class BlueprintValidationRequest(BaseModel):
    text: str = Field(default="", max_length=MAX_STORY_IDEA_CHARS)


class BlueprintValidationResponse(BaseModel):
    has_tags: bool
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    counts: dict[str, int]


@router.post("/blueprint/validate", response_model=BlueprintValidationResponse)
async def validate_story_blueprint(
    payload: BlueprintValidationRequest,
    current_user: User = Depends(get_current_user),
) -> BlueprintValidationResponse:
    """Parse the Story Idea and report syntax, script and reference problems."""
    if not has_blueprint_tags(payload.text):
        return BlueprintValidationResponse(has_tags=False, errors=[], warnings=[], counts={})
    blueprint, _missing = analyze_blueprint(payload.text)
    counts: dict[str, int] = {}
    for block in blueprint.blocks:
        counts[block.kind] = counts.get(block.kind, 0) + 1
    return BlueprintValidationResponse(
        has_tags=True,
        errors=[issue.as_dict() for issue in blueprint.errors],
        warnings=[issue.as_dict() for issue in blueprint.warnings],
        counts=counts,
    )
