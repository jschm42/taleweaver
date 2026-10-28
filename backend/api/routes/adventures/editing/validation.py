"""Validation run endpoints: structural/AI validation, latest run, finding deletion."""

import datetime as _dt
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.generation_error_log import record_generation_error
from backend.core.llm_router import GameMasterLLM
from backend.core.validators_prompts import (
    AI_VALIDATION_SYSTEM_PROMPT,
    AI_VALIDATION_USER_PROMPT_TEMPLATE,
)
from backend.core.world_validator import validate_adventure
from backend.models.user import User
from backend.models.validation_run import ValidationRun
from backend.schemas.validation import (
    DeleteValidationFindingsRequest,
    ValidationFinding,
    ValidationRunRequest,
    ValidationRunResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])

# The init_script defines the global helper / dialog handler functions, so it is
# sent with a much larger budget than ordinary text fields: a truncated script
# makes the LLM report handlers defined past the cut as missing.
_MAX_INIT_SCRIPT_LEN = 20000


def _coerce_for_json(value: Any, max_field_len: int) -> Any:
    # SQLAlchemy TimestampMixin exposes created_at / updated_at as
    # ``datetime`` instances that ``json.dumps`` cannot encode.
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, _dt.timedelta):
        return value.total_seconds()
    if isinstance(value, str) and len(value) > max_field_len:
        return value[:max_field_len] + "..."
    return value


def _summarize_for_ai(payload: dict, *, max_field_len: int = 1500) -> dict:
    """Trim large text fields on the editor payload before sending it to an LLM.

    Keeps the manifest shape but prevents a single oversized ``description``
    or sequence walkthrough from blowing out the context window. Also converts
    ``datetime`` / ``date`` values to ISO-8601 strings so the result is
    JSON-serialisable (SQLAlchemy TimestampMixin fields otherwise break
    ``json.dumps``).
    """
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()

    def _walk(value):
        if isinstance(value, dict):
            return {k: _walk(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_walk(v) for v in value]
        return _coerce_for_json(value, max_field_len)

    return _walk(payload)


def _raw_init_script(debug_payload: Any) -> str:
    raw = debug_payload.model_dump() if hasattr(debug_payload, "model_dump") else debug_payload
    adventure = (raw or {}).get("adventure") or {}
    init_script = adventure.get("init_script")
    if not isinstance(init_script, str):
        return ""
    return _coerce_for_json(init_script, _MAX_INIT_SCRIPT_LEN)


def _build_ai_validation_prompt(debug_payload: Any) -> str:
    summary = _summarize_for_ai(debug_payload)
    adventure = summary.get("adventure") or {}
    adventure.pop("init_script", None)
    sequences_list = adventure.get("sequences") or []
    scripts_list = adventure.get("scripts") or []

    def _dump(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    return AI_VALIDATION_USER_PROMPT_TEMPLATE.format(
        title=adventure.get("title", ""),
        language=adventure.get("language", ""),
        rule_enforcement_mode=adventure.get("rule_enforcement_mode", "rpg"),
        teaser=adventure.get("teaser", "") or "",
        plot=adventure.get("plot", "") or "",
        rules=adventure.get("rules", "") or "",
        intro_text=adventure.get("intro_text", "") or "",
        sequence_count=len(sequences_list),
        sequences_json=_dump(sequences_list),
        scene_count=len(summary.get("scenes") or []),
        scenes_json=_dump(summary.get("scenes") or []),
        exit_count=len(summary.get("exits") or []),
        exits_json=_dump(summary.get("exits") or []),
        npc_count=len(summary.get("npcs") or []),
        npcs_json=_dump(summary.get("npcs") or []),
        object_count=len(summary.get("objects") or []),
        objects_json=_dump(summary.get("objects") or []),
        quest_count=len(adventure.get("quests") or []),
        quests_json=_dump(adventure.get("quests") or []),
        script_count=len(scripts_list),
        scripts_json=_dump(scripts_list),
        init_script=_raw_init_script(debug_payload) or "(none)",
    )


async def _run_ai_validation(
    debug_payload: Any, user: User, template_id: str
) -> tuple[list[ValidationFinding], Optional[str]]:
    """Return (AI findings, skipped reason). Never raises; failures become a reason."""
    scene_count = len(debug_payload.scenes or [])
    if scene_count > settings.MAX_AI_VALIDATION_SCENES:
        logger.info(
            "Skipping AI validation for %s: %d scenes exceeds limit of %d",
            template_id,
            scene_count,
            settings.MAX_AI_VALIDATION_SCENES,
        )
        return [], "scene_limit_exceeded"

    from backend.api.routes.adventures.schemas import AIValidationResponse

    llm_settings = user.llm_settings or {}
    provider = (
        llm_settings.get("complex_model_provider")
        or llm_settings.get("small_model_provider")
        or "openai"
    )
    model = llm_settings.get("complex_model") or "gpt-4o"
    try:
        gm = GameMasterLLM(user=user, provider=provider, model_category="complex")
        response = await gm.aexecute_complex_task(
            system_prompt=AI_VALIDATION_SYSTEM_PROMPT,
            user_prompt=_build_ai_validation_prompt(debug_payload),
            response_model=AIValidationResponse,
            model=model,
        )
    except Exception as exc:
        logger.exception("AI validation failed for %s: %s", template_id, exc)
        record_generation_error(
            exc, stage="ai_validation", template_id=template_id, user_id=user.id
        )
        return [], "ai_error"

    findings = [
        ValidationFinding(
            severity="warn",  # AI may only emit warn-level findings
            code=f.code,
            message=f.message,
            location=f.location,
            context=f.context,
        )
        for f in (response.findings if response else [])
    ]
    return findings, None


async def execute_validation_run(
    db: AsyncSession, template_id: str, user: User, include_ai: bool
) -> ValidationRunResponse:
    """Run structural (and optionally AI) validation and persist it as the latest run."""
    from datetime import datetime

    user_id = user.id
    debug_payload = await _build_adventure_editor_assets(template_id, db)
    structural = validate_adventure(debug_payload)

    ai_findings: list[ValidationFinding] = []
    ai_skipped_reason: Optional[str] = "ai_not_requested"
    if include_ai:
        ai_findings, ai_skipped_reason = await _run_ai_validation(debug_payload, user, template_id)

    run_at_dt = datetime.now(_dt.UTC)
    structural_dicts = [f.model_dump() for f in structural]
    ai_dicts = [f.model_dump() for f in ai_findings]

    persisted = ValidationRun(
        template_id=template_id,
        user_id=user_id,
        include_ai=bool(include_ai),
        structural_findings=structural_dicts,
        ai_findings=ai_dicts,
        ai_skipped_reason=ai_skipped_reason,
        structural_finding_count=len(structural_dicts),
        ai_finding_count=len(ai_dicts),
        error_count=sum(1 for f in structural_dicts + ai_dicts if f.get("severity") == "error"),
        warning_count=sum(1 for f in structural_dicts + ai_dicts if f.get("severity") == "warn"),
        run_at=run_at_dt,
    )
    db.add(persisted)
    try:
        await db.commit()
    except Exception as exc:
        logger.exception("Failed to persist validation run for %s: %s", template_id, exc)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to persist validation run.") from exc

    return ValidationRunResponse(
        structural_findings=structural,
        ai_findings=ai_findings,
        ai_skipped_reason=ai_skipped_reason,
        run_at=run_at_dt.isoformat(),
    )


@router.post(
    "/{template_id}/editor/validate",
    response_model=ValidationRunResponse,
)
async def run_editor_validation(
    template_id: str,
    payload: ValidationRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run structural validation, and optionally an AI logic-validation pass.

    On save, the editor calls this with ``include_ai=False`` for fast,
    deterministic feedback. The "Run full validation" button in the
    Validation tab uses ``include_ai=True`` and is the only path that
    triggers the LLM call.
    """
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    return await execute_validation_run(db, template_id, current_user, bool(payload.include_ai))


@router.get(
    "/{template_id}/editor/validation/latest",
    response_model=None,
)
async def get_latest_validation_run(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the latest persisted ValidationRun for the (template, user) pair.

    Returns ``null`` when no validation has been run yet for this user on
    this adventure. The editor uses this to rehydrate the findings state on
    tab open without forcing the user to re-run validation.
    """

    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    res = await db.execute(
        select(ValidationRun)
        .where(
            ValidationRun.template_id == template_id,
            ValidationRun.user_id == current_user.id,
        )
        .order_by(ValidationRun.run_at.desc(), ValidationRun.created_at.desc())
        .limit(1)
    )
    run = res.scalars().first()
    if run is None:
        return None

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


def _recount_validation_findings(run: ValidationRun) -> None:
    """Recompute the *_count columns on the ValidationRun from its JSON arrays.

    Called after any in-place mutation (deletion of entries) so the response and
    badge counts stay accurate.
    """
    structural = list(run.structural_findings or [])
    ai_list = list(run.ai_findings or [])
    combined = structural + ai_list
    run.structural_finding_count = len(structural)
    run.ai_finding_count = len(ai_list)
    run.error_count = sum(1 for e in combined if str(e.get("severity", "")).lower() == "error")
    run.warning_count = sum(1 for e in combined if str(e.get("severity", "")).lower() == "warn")


@router.post(
    "/{template_id}/editor/validation/latest/findings/delete",
)
async def delete_validation_findings(
    template_id: str,
    payload: DeleteValidationFindingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently remove findings from the latest persisted ValidationRun.

    Unlike dismissals (which are UI-only state), this mutation persists so the
    next rehydrate via ``GET /validation/latest`` no longer returns the entries.
    The endpoint only touches the latest run for the (template, user) pair —
    previous runs remain intact for audit.
    """
    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    res = await db.execute(
        select(ValidationRun)
        .where(
            ValidationRun.template_id == template_id,
            ValidationRun.user_id == current_user.id,
        )
        .order_by(ValidationRun.run_at.desc(), ValidationRun.created_at.desc())
        .limit(1)
    )
    run = res.scalars().first()

    if run is None:
        # No persisted state to mutate. Mirror the no-op shape so the client
        # can keep the in-memory state authoritative.
        return {
            "status": "success",
            "deleted": 0,
            "structural_remaining": 0,
            "ai_remaining": 0,
            "validation_run": None,
        }

    before_structural = list(run.structural_findings or [])
    before_ai = list(run.ai_findings or [])

    if payload.delete_all:
        run.structural_findings = []
        run.ai_findings = []
        flag_modified(run, "structural_findings")
        flag_modified(run, "ai_findings")
        deleted = len(before_structural) + len(before_ai)
    else:
        targets_structural: set[tuple[str, str]] = set()
        targets_ai: set[tuple[str, str]] = set()
        for ref in payload.findings:
            key = (str(ref.code or "").strip(), str(ref.location or "").strip())
            if not key[0]:
                continue
            if ref.source == "ai":
                targets_ai.add(key)
            else:
                targets_structural.add(key)

        def _matches(entry: Any, targets: set[tuple[str, str]]) -> bool:
            return (
                str(entry.get("code") or "").strip(),
                str(entry.get("location") or "").strip(),
            ) in targets

        new_structural = [e for e in before_structural if not _matches(e, targets_structural)]
        new_ai = [e for e in before_ai if not _matches(e, targets_ai)]
        deleted = (len(before_structural) - len(new_structural)) + (len(before_ai) - len(new_ai))
        run.structural_findings = new_structural
        run.ai_findings = new_ai
        flag_modified(run, "structural_findings")
        flag_modified(run, "ai_findings")

    _recount_validation_findings(run)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to persist validation deletion."
        ) from exc

    await db.refresh(run)

    return {
        "status": "success",
        "deleted": deleted,
        "structural_remaining": run.structural_finding_count,
        "ai_remaining": run.ai_finding_count,
        "validation_run": {
            "structural_findings": list(run.structural_findings or []),
            "ai_findings": list(run.ai_findings or []),
            "ai_skipped_reason": run.ai_skipped_reason,
            "run_at": run.run_at.isoformat() if run.run_at else None,
            "structural_finding_count": run.structural_finding_count,
            "ai_finding_count": run.ai_finding_count,
            "error_count": run.error_count,
            "warning_count": run.warning_count,
        },
    }


# ---------------------------------------------------------------------------
# AI fix suggestions / apply
# ---------------------------------------------------------------------------


def _finding_signature(finding: ValidationFinding) -> str:
    """Stable signature used to round-trip a finding through the suggestion / apply pipeline."""
    location = (finding.location or "").strip()
    context = finding.context or {}
    payload = json.dumps(context, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"{finding.severity}|{finding.code}|{location}|{payload}"
