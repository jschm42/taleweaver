"""``/walkthrough reveal``: unlocks the current chapter's walkthrough for XP.

Only the active sequence can be unlocked, each one for ``WALKTHROUGH_REVEAL_COST`` XP. The first
unlock of an adventure also grants the negative "Spoiler Seeker" award.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.core.awards import SPOILER_SEEKER_AWARD
from backend.engine.rules.walkthrough_unlocks import (
    WALKTHROUGH_REVEAL_COST,
    mark_revealed,
    walkthrough_status,
)


def _award_entry(handler: Any) -> dict[str, Any]:
    adventure = getattr(handler.manager, "adventure", None)
    adv_id = adventure.id if adventure else (handler.state.template_id or "")
    return {
        "key": SPOILER_SEEKER_AWARD["key"],
        "title": SPOILER_SEEKER_AWARD["title"],
        "description": SPOILER_SEEKER_AWARD["description"],
        "tier": SPOILER_SEEKER_AWARD["tier"],
        "requirement": SPOILER_SEEKER_AWARD["requirement"],
        "template_id": adv_id,
        "adventure_id": adv_id,
        "adventure_title": adventure.title if adventure else "Adventure",
        "session_id": handler.state.session_id,
        "earned_at": datetime.now(UTC).isoformat(),
    }


async def _grant_spoiler_award(handler: Any) -> None:
    entry = _award_entry(handler)
    user_awards = list(handler.user.earned_awards or [])
    already_earned = any(
        ea.get("key") == entry["key"]
        and (
            ea.get("adventure_id") == entry["adventure_id"]
            or ea.get("session_id") == entry["session_id"]
        )
        for ea in user_awards
    )
    if already_earned:
        return
    handler.user.earned_awards = [*user_awards, entry]
    flag_modified(handler.user, "earned_awards")
    await handler.manager._save_chat_message(
        "system", f"Negative award received: {SPOILER_SEEKER_AWARD['title']}"
    )


async def reveal_current_walkthrough(handler: Any) -> str:
    """Charges the XP and unlocks the active chapter; returns the player-facing reply."""
    status = walkthrough_status(handler.manager.adventure, handler.state)
    current = status["current"]
    if current is None:
        return "There is no walkthrough for the current chapter."
    if status["current_revealed"]:
        return f"The walkthrough for {current['name']} is already unlocked."

    handler.avatar.exp = (handler.avatar.exp or 0) - WALKTHROUGH_REVEAL_COST
    flag_modified(handler.avatar, "exp")
    mark_revealed(handler.state, current["sequence_id"])
    await _grant_spoiler_award(handler)
    return (
        f"Walkthrough unlocked: {current['name']} (-{WALKTHROUGH_REVEAL_COST} XP). "
        "You can view it via the menu. Later chapters must be unlocked separately."
    )
