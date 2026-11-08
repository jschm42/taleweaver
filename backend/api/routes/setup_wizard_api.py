"""Setup wizard state: whether the guided first-run configuration is pending, skipped,
dismissed for good, or completed.

The state is stored per user and is not part of the server-wide settings, so one
user dismissing the wizard does not hide it for another user.
"""

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.user import User

router = APIRouter(prefix="/settings/setup-wizard", tags=["Setup Wizard"])

WizardState = Literal["pending", "skipped", "dismissed", "completed"]

_DEFAULT_STATE: dict[str, Any] = {"state": "pending", "visuals_opt_out": False}


class SetupWizardResponse(BaseModel):
    state: WizardState
    visuals_opt_out: bool


class SetupWizardPayload(BaseModel):
    state: Optional[WizardState] = None
    visuals_opt_out: Optional[bool] = None


def _read_state(user: User) -> SetupWizardResponse:
    stored = {**_DEFAULT_STATE, **(user.setup_wizard or {})}
    return SetupWizardResponse.model_validate(stored)


@router.get("", response_model=SetupWizardResponse)
async def get_setup_wizard(current_user: User = Depends(get_current_user)):
    """Return the wizard state of the current user."""
    return _read_state(current_user)


@router.put("", response_model=SetupWizardResponse)
async def update_setup_wizard(
    payload: SetupWizardPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merge the given fields into the wizard state of the current user."""
    current = _read_state(current_user).model_dump()
    changes = payload.model_dump(exclude_none=True)
    current_user.setup_wizard = {**current, **changes}
    await db.commit()
    return _read_state(current_user)
