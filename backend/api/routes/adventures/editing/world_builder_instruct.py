"""Endpoints that turn a free-text author instruction into World-Builder change proposals.

Reuses the AI fix pipeline: the same provider chain, proposal sanitizer
(allowlists + length limits) and patch applier, but driven by an instruction
instead of a validation finding.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.ai_fix_apply import _apply_patches, _apply_result
from backend.api.routes.adventures.editing.ai_fix_context import (
    _format_world_context_block,
    _summarize_world_for_fix,
)
from backend.api.routes.adventures.editing.ai_fix_limits import format_length_limits
from backend.api.routes.adventures.editing.ai_fix_llm import (
    _AllProvidersFailedError,
    _generate_llm_proposals,
    _summarize_outcomes,
)
from backend.api.routes.adventures.editing.ai_fix_sanitize import sanitize_proposals
from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.api.routes.adventures.schemas import AISuggestFixProposal
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.world_builder_prompts import WORLD_BUILDER_INSTRUCTION_SYSTEM_PROMPT
from backend.models.user import User
from backend.schemas.world_builder import (
    WorldBuilderApplyRequest,
    WorldBuilderApplyResponse,
    WorldBuilderInstructionRequest,
    WorldBuilderSuggestionsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])

_MAX_PROPOSALS = 3
_NOTE_MAX = 400
_TIMEOUT_MESSAGE = "The AI service did not respond in time. Please retry in a moment."
_UNAVAILABLE_MESSAGE = "The AI service is currently unavailable. Please retry in a moment."
_STALE_MESSAGE = (
    "The proposal references entities that no longer exist. Please send the instruction again."
)
_SYSTEM_PROMPT = WORLD_BUILDER_INSTRUCTION_SYSTEM_PROMPT + format_length_limits()


class _WorldBuilderLLMResponse(BaseModel):
    """Raw LLM wrapper; ``note`` explains why fewer (or no) proposals were returned."""

    proposals: list[AISuggestFixProposal] = Field(default_factory=list)
    note: Optional[str] = None


def _instruction_prompt(instruction: str, summary: dict[str, Any]) -> str:
    return (
        f"{_format_world_context_block(summary)}\n"
        f"=== AUTHOR INSTRUCTION ===\n"
        f'"""\n{instruction}\n"""\n\n'
        f"Produce up to 3 distinct, immediately applicable proposals that carry out the "
        f"instruction above.\n"
        f"Return ONLY the JSON object with a top-level 'proposals' key."
    )


def _failure_message(exc: Exception, template_id: str) -> str:
    """User-facing, provider-neutral message for a failed World-Builder call (logged here)."""
    if isinstance(exc, _AllProvidersFailedError):
        logger.warning("World-Builder instruction unavailable for %s: %s", template_id, exc)
        return _summarize_outcomes(exc.outcomes)
    if isinstance(exc, TimeoutError):
        logger.warning("World-Builder instruction timed out for %s: %s", template_id, exc)
        return _TIMEOUT_MESSAGE
    logger.exception("World-Builder instruction failed for %s: %s", template_id, exc)
    return _UNAVAILABLE_MESSAGE


def _clean_note(note: Optional[str]) -> Optional[str]:
    text = (note or "").strip()
    return text[:_NOTE_MAX] or None


@router.post(
    "/{template_id}/editor/world-builder/suggest",
    response_model=WorldBuilderSuggestionsResponse,
)
async def world_builder_suggest(
    template_id: str,
    payload: WorldBuilderInstructionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ask the World-Builder for up to 3 change proposals for a free-text instruction.

    Always returns HTTP 200 with either proposals or a short, provider-neutral
    ``error`` string, mirroring the AI fix suggestion endpoint.
    """
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    instruction = payload.instruction.strip()
    summary = _summarize_world_for_fix(await _build_adventure_editor_assets(template_id, db))
    generated_at = datetime.now(UTC).isoformat()
    try:
        wrapper, _served_provider = await _generate_llm_proposals(
            user_prompt=_instruction_prompt(instruction, summary),
            current_user=current_user,
            response_model=_WorldBuilderLLMResponse,
            gm_kwargs={"system_prompt": _SYSTEM_PROMPT},
            timeout_seconds=settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS,
            allow_fallback=True,
        )
    except Exception as exc:
        return WorldBuilderSuggestionsResponse(
            instruction=instruction,
            generated_at=generated_at,
            error=_failure_message(exc, template_id),
        )

    raw_proposals = ((wrapper.proposals if wrapper else []) or [])[:_MAX_PROPOSALS]
    sanitized = sanitize_proposals(raw_proposals, summary, allow_create=True)
    response = WorldBuilderSuggestionsResponse(
        instruction=instruction,
        proposals=sanitized.proposals,
        note=_clean_note(getattr(wrapper, "note", None)),
        generated_at=generated_at,
    )
    if sanitized.rejected:
        logger.warning(
            "World-Builder proposals for %s: kept %d of %d, rejected: %s",
            template_id,
            len(sanitized.proposals),
            len(raw_proposals),
            "; ".join(sanitized.rejected),
        )
    if raw_proposals and not sanitized.proposals:
        response.error = sanitized.error_message()
    return response


@router.post(
    "/{template_id}/editor/world-builder/apply",
    response_model=WorldBuilderApplyResponse,
)
async def world_builder_apply(
    template_id: str,
    payload: WorldBuilderApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply the chosen World-Builder proposal; its patches are authoritative (no LLM call)."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    patches = payload.proposal.patches or []
    if not patches:
        return WorldBuilderApplyResponse(
            status="no_op", message="The selected proposal contained no patches to apply."
        )

    applied_tags, failed_resolution = await _apply_patches(
        db, template_id, adv, patches, allow_create=True
    )
    if applied_tags:
        await db.commit()
    else:
        await db.rollback()

    status, message = _apply_result(len(applied_tags), len(patches), failed_resolution)
    if failed_resolution and not applied_tags:
        message = _STALE_MESSAGE
    return WorldBuilderApplyResponse(status=status, applied_targets=applied_tags, message=message)
