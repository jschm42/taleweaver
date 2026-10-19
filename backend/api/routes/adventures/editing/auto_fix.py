"""Post-generation quality pass: validate a fresh adventure and auto-apply AI fixes.

Reuses the editor pipeline (validation run -> fix proposals -> patch apply) so
the result is identical to a user clicking "AI-Fix" on every finding and
accepting the first proposal. Remaining findings stay in the persisted
validation run and are visible in the editor's Validation tab.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.ai_fix_apply import _apply_patches, _commit_fix
from backend.api.routes.adventures.editing.ai_fix_suggest import generate_fix_proposals
from backend.api.routes.adventures.editing.validation import execute_validation_run
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
    db: AsyncSession, template_id: str, user: User, include_ai: bool = True
) -> AutoFixReport:
    """Validate the adventure and apply the top AI fix proposal to each finding."""
    run = await execute_validation_run(db, template_id, user, include_ai)
    findings = _prioritized([*run.structural_findings, *run.ai_findings])
    report = AutoFixReport(findings_total=len(findings))
    if not findings:
        return report

    result = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    adventure = result.scalars().first()
    if adventure is None:
        return report

    for finding in findings[:MAX_AUTO_FIX_FINDINGS]:
        report.attempted += 1
        try:
            fixed = await _auto_fix_finding(db, template_id, user, adventure, finding)
        except Exception:
            logger.exception("Auto-fix failed for %s on %s", finding.code, template_id)
            await db.rollback()
            await db.refresh(user)
            await db.refresh(adventure)
            continue
        report.fixed += int(fixed)

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
    await db.commit()
    try:
        await run_post_generation_auto_fix(db, template_id, user)
    except Exception:
        logger.exception("Post-generation auto-fix failed for %s", template_id)
        await db.rollback()
