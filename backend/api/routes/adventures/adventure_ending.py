"""The ending card of a finished adventure (win or game over), stored as a chat message.

The terminal epilogue saves it right after the epilogue narration. The story feed renders the
``adventure_ending`` message as a card at that position, so it survives reloads and stays above
anything the player does after a win. The message never reaches the LLM: prompt building only
reads ``user``, ``assistant`` and ``system`` messages.
"""

from __future__ import annotations

import json
from typing import Any

from backend.models.chat import ChatMessage

ADVENTURE_ENDING_ROLE = "adventure_ending"


def _count_completed(quests: list[Any]) -> tuple[int, int]:
    entries = [q for q in quests if isinstance(q, dict)]
    return sum(1 for q in entries if q.get("status") == "completed"), len(entries)


def _count_awards(manager: Any) -> tuple[int, int]:
    adventure = manager.adventure
    if adventure is None:
        return 0, 0
    total = len(adventure.awards or [])
    earned = [
        award
        for award in (manager.user.earned_awards or [] if manager.user else [])
        if isinstance(award, dict)
        and adventure.id in (award.get("adventure_id"), award.get("template_id"))
    ]
    return min(len(earned), total) if total else len(earned), total


def build_ending_payload(manager: Any) -> dict[str, Any]:
    """Outcome, the script's end message and a short tally for the card."""
    session = manager.state.session
    quests_done, quests_total = _count_completed(list(manager.state.quests or []))
    awards_earned, awards_total = _count_awards(manager)
    return {
        "outcome": "won" if session.status == "completed" else "lost",
        "reason": str(session.status_note or "").strip(),
        "adventure_title": manager.adventure.title if manager.adventure else "",
        "exp": int(manager.avatar.exp or 0) if manager.avatar else 0,
        "quests_completed": quests_done,
        "quests_total": quests_total,
        "awards_earned": awards_earned,
        "awards_total": awards_total,
    }


async def save_ending_card(manager: Any) -> ChatMessage:
    """Stores the ending card as a chat message (flushed, not committed)."""
    content = json.dumps(build_ending_payload(manager), ensure_ascii=False)
    message = ChatMessage(
        session_id=manager.state.session_id, role=ADVENTURE_ENDING_ROLE, content=content
    )
    manager.db.add(message)
    await manager.db.flush()
    return message
