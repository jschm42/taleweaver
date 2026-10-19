"""Post-generation validation + auto-fix pass."""

from unittest.mock import AsyncMock

import pytest

from backend.api.routes.adventures.editing import auto_fix
from backend.api.routes.adventures.schemas import CreateAdventureTemplatePayload
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.schemas.validation import (
    AIFixSuggestionsResponse,
    FixProposal,
    FixProposalEntityPatch,
    ValidationFinding,
    ValidationRunResponse,
)
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

# Bound at import time: conftest stubs ``auto_fix.run_auto_fix_pass_safely`` for all other tests.
_REAL_SAFE_WRAPPER = auto_fix.run_auto_fix_pass_safely


def _finding(code: str, severity: str) -> ValidationFinding:
    return ValidationFinding(
        severity=severity, code=code, message=f"{code} broken", location="scene:START"
    )


def _proposal() -> FixProposal:
    return FixProposal(
        title="Fix",
        summary="Apply a fix",
        patches=[
            FixProposalEntityPatch(
                target_type="scene",
                target_id="START",
                description="d",
                field_updates={"description": "x"},
            )
        ],
    )


async def _seed() -> tuple[User, str]:
    async with TestSessionLocal() as session:
        user = User(username="autofix_user", hashed_password="x", role="user")
        session.add(user)
        await session.flush()
        session.add(AdventureTemplate(id="autofix-tpl", owner_id=user.id, title="T", language="en"))
        await session.commit()
        await session.refresh(user)
        return user, "autofix-tpl"


def test_auto_validate_and_fix_defaults_to_enabled() -> None:
    assert CreateAdventureTemplatePayload(title="New").auto_validate_and_fix is True


async def test_auto_fix_applies_first_proposal_errors_first(monkeypatch) -> None:
    # Arrange
    user, template_id = await _seed()
    run = ValidationRunResponse(
        structural_findings=[_finding("W1", "warn"), _finding("E1", "error")],
        ai_findings=[_finding("AI1", "warn")],
        ai_skipped_reason=None,
        run_at="2026-10-18T00:00:00Z",
    )
    monkeypatch.setattr(auto_fix, "execute_validation_run", AsyncMock(return_value=run))
    asked: list[str] = []

    async def fake_proposals(_db, _tpl, _user, request):
        asked.append(request.finding_code)
        proposals = [] if request.finding_code == "AI1" else [_proposal()]
        return AIFixSuggestionsResponse(
            finding_signature=f"sig-{request.finding_code}", proposals=proposals, generated_at="now"
        )

    monkeypatch.setattr(auto_fix, "generate_fix_proposals", fake_proposals)
    monkeypatch.setattr(
        auto_fix, "_apply_patches", AsyncMock(return_value=(["scene:START"], False))
    )
    commit_fix = AsyncMock(return_value=None)
    monkeypatch.setattr(auto_fix, "_commit_fix", commit_fix)

    # Act
    async with TestSessionLocal() as db:
        db_user = await db.get(User, user.id)
        report = await auto_fix.run_post_generation_auto_fix(db, template_id, db_user)

    # Assert
    assert asked[0] == "E1"
    assert report.findings_total == 3
    assert report.attempted == 3
    assert report.fixed == 2
    assert report.remaining == 1
    assert commit_fix.await_count == 2


async def test_auto_fix_caps_number_of_llm_fix_attempts(monkeypatch) -> None:
    # Arrange
    user, template_id = await _seed()
    findings = [_finding(f"W{i}", "warn") for i in range(auto_fix.MAX_AUTO_FIX_FINDINGS + 5)]
    run = ValidationRunResponse(structural_findings=findings, ai_findings=[], run_at="now")
    monkeypatch.setattr(auto_fix, "execute_validation_run", AsyncMock(return_value=run))
    proposals = AsyncMock(
        return_value=AIFixSuggestionsResponse(
            finding_signature="s", proposals=[], generated_at="now"
        )
    )
    monkeypatch.setattr(auto_fix, "generate_fix_proposals", proposals)

    # Act
    async with TestSessionLocal() as db:
        report = await auto_fix.run_post_generation_auto_fix(
            db, template_id, await db.get(User, user.id)
        )

    # Assert
    assert proposals.await_count == auto_fix.MAX_AUTO_FIX_FINDINGS
    assert report.fixed == 0


async def test_safe_wrapper_swallows_failures_and_skips_cancelled(monkeypatch) -> None:
    # Arrange
    user, template_id = await _seed()
    failing = AsyncMock(side_effect=RuntimeError("llm down"))
    monkeypatch.setattr(auto_fix, "run_post_generation_auto_fix", failing)

    # Act
    async with TestSessionLocal() as db:
        db_user = await db.get(User, user.id)
        await _REAL_SAFE_WRAPPER(db, template_id, db_user)
        adventure = await db.get(AdventureTemplate, template_id)
        adventure.creation_status = "Cancelled"
        await db.commit()
        await _REAL_SAFE_WRAPPER(db, template_id, db_user)

    # Assert
    assert failing.await_count == 1
