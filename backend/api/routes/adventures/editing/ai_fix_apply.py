"""Endpoint that applies a chosen AI fix proposal to the adventure template."""

import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.ai_fix_llm import _evict_cached_suggestions
from backend.api.routes.adventures.editing.ai_fix_patches import (
    _apply_proposal_patch,
    _clean_updates,
)
from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.validation import (
    _finding_signature,
    _recount_validation_findings,
)
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.validation_run import ValidationRun
from backend.schemas.validation import (
    AIFixApplyRequest,
    AIFixApplyResponse,
    FixProposalEntityPatch,
    ValidationFinding,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])

_STALE_REFERENCE_MESSAGE = (
    "The cached AI reference is out of date. Please click AI-Fix again to regenerate."
)


async def _apply_patches(
    db: AsyncSession,
    template_id: str,
    adv: AdventureTemplate,
    patches: list[FixProposalEntityPatch],
) -> tuple[list[str], bool]:
    """Apply each patch once per target. Returns (applied tags, any stale reference)."""
    applied_tags: list[str] = []
    seen_keys: set[tuple[str, str]] = set()
    failed_resolution = False
    for proposal_patch in patches:
        clean = _clean_updates(proposal_patch.target_type, proposal_patch.field_updates)
        if not clean:
            continue
        try:
            tag = await _apply_proposal_patch(
                db=db,
                template_id=template_id,
                adv=adv,
                patch=proposal_patch.model_copy(update={"field_updates": clean}),
            )
        except HTTPException as exc:
            if exc.status_code == 400 and "could not be resolved" in str(exc.detail):
                failed_resolution = True
                continue
            raise
        key = (str(proposal_patch.target_type), (proposal_patch.target_id or "").strip())
        if not tag or key in seen_keys:
            continue
        seen_keys.add(key)
        applied_tags.append(tag)
    return applied_tags, failed_resolution


def _matches_signature(entry: Any, signature: str) -> bool:
    try:
        vf = ValidationFinding(**entry) if isinstance(entry, dict) else entry
        return _finding_signature(vf) == signature
    except Exception:
        return False


def _matches_code_location(entry: Any, code: str, location: str) -> bool:
    if not isinstance(entry, dict):
        return False
    return (
        str(entry.get("code") or "").strip() == code
        and str(entry.get("location") or "").strip() == location
    )


def _without_finding(findings: list[Any], signature: str) -> tuple[list[Any], bool]:
    """Drop the fixed finding by exact signature, else by code + location."""
    kept = [e for e in findings if not _matches_signature(e, signature)]
    return kept, len(kept) != len(findings)


def _prune_fixed_finding(run: ValidationRun, signature: str) -> None:
    """Remove the fixed finding from the run so it does not reappear on reload."""
    before_ai = list(run.ai_findings or [])
    before_structural = list(run.structural_findings or [])
    new_ai, ai_changed = _without_finding(before_ai, signature)
    new_structural, structural_changed = _without_finding(before_structural, signature)

    # Fallback if signature serialization differed: match on code & location
    parts = signature.split("|", 3)
    if not (ai_changed or structural_changed) and len(parts) >= 3:
        code, location = parts[1].strip(), parts[2].strip()
        new_ai = [e for e in before_ai if not _matches_code_location(e, code, location)]
        new_structural = [
            e for e in before_structural if not _matches_code_location(e, code, location)
        ]

    if len(new_ai) == len(before_ai) and len(new_structural) == len(before_structural):
        return
    run.ai_findings = new_ai
    run.structural_findings = new_structural
    flag_modified(run, "ai_findings")
    flag_modified(run, "structural_findings")
    _recount_validation_findings(run)


async def _latest_run(db: AsyncSession, template_id: str, user_id: str) -> Optional[ValidationRun]:
    run_res = await db.execute(
        select(ValidationRun)
        .where(ValidationRun.template_id == template_id, ValidationRun.user_id == user_id)
        .order_by(ValidationRun.run_at.desc(), ValidationRun.created_at.desc())
        .limit(1)
    )
    return run_res.scalars().first()


def _run_snapshot(run: ValidationRun) -> dict[str, Any]:
    return {
        "structural_findings": list(run.structural_findings or []),
        "ai_findings": list(run.ai_findings or []),
        "ai_skipped_reason": run.ai_skipped_reason,
        "run_at": run.run_at.isoformat() if run.run_at else None,
        "structural_finding_count": run.structural_finding_count,
        "ai_finding_count": run.ai_finding_count,
        "error_count": run.error_count,
        "warning_count": run.warning_count,
    }


async def _commit_fix(
    db: AsyncSession, template_id: str, user_id: str, signature: str
) -> Optional[dict[str, Any]]:
    """Persist the applied patches, prune the fixed finding, and drop cached proposals."""
    run = await _latest_run(db, template_id, user_id)
    if run is not None:
        _prune_fixed_finding(run, signature)
    await db.commit()
    await _evict_cached_suggestions(
        db=db, template_id=template_id, user_id=user_id, signature=signature
    )
    if run is None:
        return None
    await db.refresh(run)
    return _run_snapshot(run)


def _apply_result(applied: int, total: int, failed_resolution: bool) -> tuple[str, str]:
    status: Literal["applied", "no_op", "partial"] = "no_op"
    if applied:
        status = "partial" if applied < total else "applied"
        return status, f"Applied {applied} patch(es) out of {total}."
    if failed_resolution:
        return status, _STALE_REFERENCE_MESSAGE
    return status, "No changes were applied."


@router.post(
    "/{template_id}/editor/validate/findings/apply-fix",
    response_model=AIFixApplyResponse,
)
async def ai_apply_fix_proposal(
    template_id: str,
    payload: AIFixApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply the chosen fix proposal directly to the adventure template.

    The proposal's ``patches[]`` are treated as the authoritative source of
    truth; no second LLM call is made. Field updates that fall outside the
    per-target allowlist are silently dropped.
    """
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    # Read before any rollback: a rollback expires ``current_user`` (same session).
    user_id = current_user.id
    proposal_patches = payload.proposal.patches or []
    if not proposal_patches:
        return AIFixApplyResponse(
            status="no_op",
            applied_targets=[],
            message="The selected proposal contained no patches to apply.",
        )

    applied_tags, failed_resolution = await _apply_patches(db, template_id, adv, proposal_patches)
    updated_run_dict = None
    if applied_tags:
        updated_run_dict = await _commit_fix(db, template_id, user_id, payload.finding_signature)
    else:
        await db.rollback()
        if failed_resolution:
            await _evict_cached_suggestions(
                db=db,
                template_id=template_id,
                user_id=user_id,
                signature=payload.finding_signature,
            )

    status, message = _apply_result(len(applied_tags), len(proposal_patches), failed_resolution)
    return AIFixApplyResponse(
        status=status,
        applied_targets=applied_tags,
        message=message,
        validation_run=updated_run_dict,
    )
