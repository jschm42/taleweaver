"""Endpoint that asks the LLM for fix proposals for a validation finding."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.ai_fix_context import (
    _format_finding_context_block,
    _format_focused_world_block,
    _signing,
    _summarize_world_for_fix,
)
from backend.api.routes.adventures.editing.ai_fix_llm import (
    _AllProvidersFailedError,
    _generate_llm_proposals,
    _get_cached_suggestions,
    _summarize_outcomes,
    _write_cached_suggestions,
)
from backend.api.routes.adventures.editing.ai_fix_targets import _allowed_fields_for
from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.api.routes.adventures.schemas import AISuggestFixWrapperResponse
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.validators_prompts import AI_FIX_SUGGESTIONS_SYSTEM_PROMPT
from backend.models.user import User
from backend.schemas.validation import (
    AIFixSuggestionsRequest,
    AIFixSuggestionsResponse,
    FixProposal,
    FixProposalEntityPatch,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])

_MAX_PROPOSALS = 3
_PATCH_TARGET_TYPES = {"scene", "object", "npc", "exit", "protagonist", "adventure"}
_PROPOSAL_FIELDS = (
    "title",
    "summary",
    "rationale",
    "patches",
    "target_type",
    "target_id",
    "description",
    "field_updates",
    "note",
)
_TIMEOUT_MESSAGE = "The AI service did not respond in time. Please retry in a moment."
_UNAVAILABLE_MESSAGE = "The AI service is currently unavailable. Please retry in a moment."


def _as_dict(value: Any) -> Optional[dict[str, Any]]:
    """Normalize an LLM-returned proposal/patch (dict, pydantic model, or object) to a dict."""
    if value is None or isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
        except Exception:
            return None
        return dumped if isinstance(dumped, dict) else None
    collected = {f: getattr(value, f) for f in _PROPOSAL_FIELDS if hasattr(value, f)}
    return collected or None


def _clean_patch(raw: Any) -> Optional[FixProposalEntityPatch]:
    p_dict = _as_dict(raw)
    if p_dict is None:
        return None
    target_type = str(p_dict.get("target_type") or "").strip()
    field_updates = p_dict.get("field_updates") or {}
    if target_type not in _PATCH_TARGET_TYPES or not isinstance(field_updates, dict):
        return None
    if not field_updates:
        return None
    allowed = _allowed_fields_for(target_type)
    target_id = p_dict.get("target_id")
    return FixProposalEntityPatch(
        target_type=target_type,  # type: ignore[arg-type]
        target_id=str(target_id).strip() if target_id is not None else None,
        description=str(p_dict.get("description") or "").strip()[:280],
        field_updates={str(k): v for k, v in field_updates.items() if k in allowed},
    )


def _clean_proposal(raw: Any) -> Optional[FixProposal]:
    raw_dict = _as_dict(raw)
    if raw_dict is None:
        return None
    title = str(raw_dict.get("title") or "").strip()
    summary_text = str(raw_dict.get("summary") or "").strip()
    if not title or not summary_text:
        return None
    patches = [p for p in (_clean_patch(x) for x in raw_dict.get("patches") or []) if p]
    if not patches:
        return None
    rationale = raw_dict.get("rationale")
    return FixProposal(
        title=title[:120],
        summary=summary_text[:600],
        rationale=(str(rationale).strip()[:400] if rationale else None),
        patches=patches,
    )


def _suggestion_prompt(payload: AIFixSuggestionsRequest, summary: dict[str, Any]) -> str:
    world_block = _format_focused_world_block(summary, location=payload.finding_location)
    return (
        f"=== ORIGINAL FINDING ===\n"
        f"- Code: {payload.finding_code}\n"
        f"- Severity: {payload.finding_severity}\n"
        f"- Location: {(payload.finding_location or '').strip()}\n"
        f"- Message: {payload.finding_message}\n"
        f"{_format_finding_context_block(payload)}\n\n"
        f"{world_block}\n"
        f"Produce up to 3 distinct, immediately applicable fix proposals for the finding above.\n"
        f"Return ONLY the JSON object with a top-level 'proposals' key."
    )


def _failure_message(exc: Exception, template_id: str) -> str:
    """User-facing, provider-neutral message for a failed suggestion call (logged here)."""
    if isinstance(exc, _AllProvidersFailedError):
        logger.warning("AI fix suggestion unavailable for %s: %s", template_id, exc)
        return _summarize_outcomes(exc.outcomes)
    if isinstance(exc, TimeoutError):
        logger.warning(
            "AI fix suggestion timed out for %s after %.0fs: %s",
            template_id,
            settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS,
            exc,
        )
        return _TIMEOUT_MESSAGE
    logger.exception("AI fix suggestion failed for %s: %s", template_id, exc)
    return _UNAVAILABLE_MESSAGE


async def _cache_response(
    db: AsyncSession, template_id: str, user_id: str, response: AIFixSuggestionsResponse
) -> None:
    try:
        await _write_cached_suggestions(
            db=db,
            template_id=template_id,
            user_id=user_id,
            signature=response.finding_signature,
            response_payload=response.model_dump(),
        )
    except Exception as cache_exc:
        logger.warning(
            "Failed to persist AI fix cache for %s/%s: %s",
            template_id,
            response.finding_signature,
            cache_exc,
        )


@router.post(
    "/{template_id}/editor/validate/findings/suggest-fix",
    response_model=AIFixSuggestionsResponse,
)
async def ai_suggest_fix_for_finding(
    template_id: str,
    payload: AIFixSuggestionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suggest up to 3 different fixes for an AI-detected validation finding.

    Fast-path on cache hit (per (template, user, finding_signature)).
    Otherwise: focused world context, hard watchdog, provider fallback,
    persist on success. Always returns HTTP 200 with either proposals or a
    short, anbieter-neutral ``error`` string.
    """
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    return await generate_fix_proposals(db, template_id, current_user, payload)


async def generate_fix_proposals(
    db: AsyncSession,
    template_id: str,
    current_user: User,
    payload: AIFixSuggestionsRequest,
) -> AIFixSuggestionsResponse:
    """Cached-or-generated fix proposals for one finding (ownership is checked by callers)."""
    # Read before the cache lookup, which may commit/rollback and expire ``current_user``.
    user_id = current_user.id
    signature = _signing(payload)
    cached = await _get_cached_suggestions(
        db=db, template_id=template_id, user_id=user_id, signature=signature
    )
    if cached:
        return AIFixSuggestionsResponse(**{"error": None, **cached})

    debug_payload = await _build_adventure_editor_assets(template_id, db)
    user_prompt = _suggestion_prompt(payload, _summarize_world_for_fix(debug_payload))
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        wrapper, _served_provider = await _generate_llm_proposals(
            user_prompt=user_prompt,
            current_user=current_user,
            response_model=AISuggestFixWrapperResponse,
            gm_kwargs={"system_prompt": AI_FIX_SUGGESTIONS_SYSTEM_PROMPT},
            timeout_seconds=settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS,
            allow_fallback=True,
        )
    except Exception as exc:
        return AIFixSuggestionsResponse(
            finding_signature=signature,
            proposals=[],
            generated_at=generated_at,
            error=_failure_message(exc, template_id),
        )

    raw_proposals = ((wrapper.proposals if wrapper else []) or [])[:_MAX_PROPOSALS]
    response = AIFixSuggestionsResponse(
        finding_signature=signature,
        proposals=[p for p in (_clean_proposal(raw) for raw in raw_proposals) if p],
        generated_at=generated_at,
    )
    if response.proposals:
        await _cache_response(db, template_id, user_id, response)
    return response
