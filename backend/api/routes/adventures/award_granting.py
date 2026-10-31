"""Grants awards to the player: from the GM (``earned_award_keys``) and from scripts
(``tw.awards.grant``). Each award is earned once per adventure and announced in the chat."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.rules.award_keys import canonical_award_keys

logger = logging.getLogger(__name__)

CHECKPOINT_REASON_AWARD_GRANTED = "AWARD_GRANTED"
# The game UI recognises this prefix to show the award overlay.
AWARD_MESSAGE_PREFIX = "Award Achievement: "


def _already_earned(user_awards: list[dict[str, Any]], key: str, adventure_id: str) -> bool:
    return any(
        ea.get("key") == key
        and (ea.get("template_id") == adventure_id or ea.get("adventure_id") == adventure_id)
        for ea in user_awards
    )


def record_earned_awards(
    user: Any, adventure: Any, session_id: str, keys: Iterable[Any]
) -> list[dict[str, Any]]:
    """Adds the not yet earned awards to ``user.earned_awards``; returns their definitions."""
    award_defs = {aw.get("key"): aw for aw in (adventure.awards or []) if aw.get("key")}
    user_awards = list(user.earned_awards or [])
    now = datetime.now(UTC).isoformat()
    granted: list[dict[str, Any]] = []
    for key in canonical_award_keys(keys, adventure.awards or []):
        award = award_defs.get(key)
        if not award:
            logger.warning("[Awards] Tried to grant non-existent award: %s", key)
            continue
        if _already_earned(user_awards, key, adventure.id):
            continue
        user_awards.append(
            {
                "key": key,
                "title": award.get("title") or key,
                "description": award.get("description"),
                "tier": award.get("tier"),
                "template_id": adventure.id,
                "adventure_id": adventure.id,
                "adventure_title": adventure.title,
                "session_id": session_id,
                "earned_at": now,
            }
        )
        granted.append(award)
    if granted:
        user.earned_awards = user_awards
        flag_modified(user, "earned_awards")
    return granted


async def grant_awards(manager: Any, keys: Iterable[Any]) -> list[str]:
    """Grants the awards, writes one chat message per new award and queues a checkpoint."""
    granted = record_earned_awards(manager.user, manager.adventure, manager.state.session_id, keys)
    messages: list[str] = []
    for award in granted:
        message = f"{AWARD_MESSAGE_PREFIX}{award.get('title') or award.get('key')}"
        await manager._save_chat_message("system", message)
        messages.append(message)
    if granted:
        manager._queue_checkpoint(CHECKPOINT_REASON_AWARD_GRANTED)
    return messages
