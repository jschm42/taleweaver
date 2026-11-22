"""Post-generation quality pass: validate a fresh adventure and auto-apply AI fixes.

Reuses the editor pipeline (validation run -> fix proposals -> patch apply) so
the result is identical to a user clicking "AI-Fix" on every finding and
accepting the first proposal. Remaining findings stay in the persisted
validation run and are visible in the editor's Validation tab; a compact summary
is also appended to the generation log for the generation view.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.ai_fix_apply import _apply_patches, _commit_fix
from backend.api.routes.adventures.editing.ai_fix_suggest import generate_fix_proposals
from backend.api.routes.adventures.editing.auto_fix_log import (
    append_validation_log,
    build_validation_log_entry,
)
from backend.api.routes.adventures.editing.validation import (
    _finding_signature,
    execute_validation_run,
)
from backend.core.generation_error_log import record_generation_error
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.schemas.validation import AIFixSuggestionsRequest, ValidationFinding

logger = logging.getLogger(__name__)

# Each fix costs one LLM call; cap the pass so generation time stays bounded.
MAX_AUTO_FIX_FINDINGS = 12
_SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


@dataclass
class AutoFixReport:
    findings_total: int = 0
    attempted: int = 0
    fixed: int = 0
    errors: int = 0
    warnings: int = 0
    ai_skipped_reason: Optional[str] = None
    resolved: list[ValidationFinding] = field(default_factory=list)
    unresolved: list[ValidationFinding] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return self.findings_total - self.fixed


def _prioritized(findings: list[ValidationFinding]) -> list[ValidationFinding]:
    return sorted(findings, key=lambda f: _SEVERITY_ORDER.get(str(f.severity), 3))


async def _auto_fix_finding(
    db: AsyncSession,
    template_id: str,
    user: User,
    adventure: AdventureTemplate,
    finding: ValidationFinding,
) -> bool:
    request = AIFixSuggestionsRequest(
        finding_code=finding.code,
        finding_message=finding.message,
        finding_location=finding.location,
        finding_context=finding.context,
        finding_severity=finding.severity,
    )
    response = await generate_fix_proposals(db, template_id, user, request)
    if response.error or not response.proposals:
        logger.info("Auto-fix: no proposal for %s (%s)", finding.code, response.error or "empty")
        return False

    applied, _stale = await _apply_patches(
        db, template_id, adventure, response.proposals[0].patches
    )
    if not applied:
        await db.rollback()
        # A rollback expires loaded instances; reload what the next iteration needs.
        await db.refresh(user)
        await db.refresh(adventure)
        return False

    await _commit_fix(db, template_id, user.id, response.finding_signature)
    return True


async def run_post_generation_auto_fix(
    db: AsyncSession,
    template_id: str,
    user: User,
    include_ai: bool = True,
    skip_signatures: Optional[set] = None,
) -> AutoFixReport:
    """Validate the adventure and apply the top AI fix proposal to each finding.

    ``skip_signatures``: findings that existed before (a region build fixes only its own)."""
    run = await execute_validation_run(db, template_id, user, include_ai)
    skip = skip_signatures or set()
    findings = _prioritized(
        [
            f
            for f in [*run.structural_findings, *run.ai_findings]
            if _finding_signature(f) not in skip
        ]
    )
    report = AutoFixReport(
        findings_total=len(findings),
        errors=sum(1 for f in findings if f.severity == "error"),
        warnings=sum(1 for f in findings if f.severity != "error"),
        ai_skipped_reason=run.ai_skipped_reason,
    )
    if not findings:
        return report

    result = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    adventure = result.scalars().first()
    if adventure is None:
        report.unresolved = findings
        return report

    user_id = user.id
    for finding in findings[:MAX_AUTO_FIX_FINDINGS]:
        report.attempted += 1
        try:
            fixed = await _auto_fix_finding(db, template_id, user, adventure, finding)
        except Exception as exc:
            logger.exception("Auto-fix failed for %s on %s", finding.code, template_id)
            record_generation_error(
                exc, stage=f"auto_fix:{finding.code}", template_id=template_id, user_id=user_id
            )
            await db.rollback()
            await db.refresh(user)
            await db.refresh(adventure)
            fixed = False
        report.fixed += int(fixed)
        (report.resolved if fixed else report.unresolved).append(finding)

    # Findings beyond the cap are never attempted and stay unresolved.
    report.unresolved.extend(findings[MAX_AUTO_FIX_FINDINGS:])

    logger.info(
        "Post-generation auto-fix for %s: %d findings, %d attempted, %d fixed",
        template_id,
        report.findings_total,
        report.attempted,
        report.fixed,
    )
    return report


async def run_auto_fix_pass_safely(db: AsyncSession, template_id: str, user: User) -> None:
    """Best-effort wrapper for the generation pipeline; never fails the generation."""
    adventure = (
        (await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id)))
        .scalars()
        .first()
    )
    if adventure is None or adventure.creation_status == "Cancelled":
        return
    adventure.creation_status = "Validating and auto-fixing"
    user_id = user.id
    await db.commit()
    report: Optional[AutoFixReport] = None
    failure: Optional[str] = None
    try:
        report = await run_post_generation_auto_fix(db, template_id, user)
    except Exception as exc:
        logger.exception("Post-generation auto-fix failed for %s", template_id)
        entry = record_generation_error(
            exc, stage="post_generation_auto_fix", template_id=template_id, user_id=user_id
        )
        await db.rollback()
        failure = f"{entry['content']} (Error ID {entry['details']['error_id']})"
    await _log_validation_result(db, template_id, build_validation_log_entry(report, failure))


async def _log_validation_result(db: AsyncSession, template_id: str, entry: dict) -> None:
    """Surface the validation outcome in the generation view; never fails the generation."""
    try:
        adventure = await db.get(AdventureTemplate, template_id, populate_existing=True)
        if adventure is None:
            return
        append_validation_log(adventure, entry)
        await db.commit()
    except Exception:
        logger.exception("Could not log validation result for %s", template_id)
        await db.rollback()
