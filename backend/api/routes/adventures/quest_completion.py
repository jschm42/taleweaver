"""Side-quest completion: mark quests completed, pay their XP and announce them.

Shared by the regular turn (``TurnStateApplier``) and the progress re-check that runs after
scripts changed the state (``out_of_turn_progress``).
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Optional

from backend.engine.rules.quest_manager import QuestManager
from backend.models.chat import ChatMessage

logger = logging.getLogger(__name__)

CHECKPOINT_REASON_QUEST_UPDATE = "QUEST_UPDATE"


def mark_quests_completed(
    state: Any, quest_ids: list[str], game_id: Optional[str] = None
) -> list[dict]:
    """Sets the given open quests to ``completed``; returns the quests that changed."""
    if not quest_ids:
        return []
    quests = deepcopy(state.quests or [])
    changed: list[dict] = []
    for qid in dict.fromkeys(quest_ids):
        for quest in quests:
            if quest.get("id") != qid or quest.get("status") == "completed":
                continue
            quest["status"] = "completed"
            changed.append(quest)
            if game_id:
                logger.info("[Turn %s] Quest completed: %s", game_id, qid)
    if changed:
        state.quests = quests
    return changed


def hard_rule_quest_ids(
    avatar: Any, state: Any, script_context: Any = None, event: Any = None
) -> list[str]:
    """IDs of open quests whose hard rules (or heuristic goals) are met right now."""
    return QuestManager.evaluate_quests(
        avatar,
        state,
        new_inventory_items=getattr(event, "new_inventory_items", None),
        new_scene_id=getattr(event, "new_scene_id", None),
        updated_entities=getattr(event, "updated_entities", None),
        script_context=script_context,
    )


def announce_completed_quests(owner: Any, quests: list[dict]) -> list[str]:
    """Pays each quest's XP, stores one chat line per quest and queues a checkpoint.

    ``owner`` is a turn manager or a ``TurnStateApplier`` (both expose ``db``, ``state``,
    ``avatar`` and ``_queue_checkpoint``).
    """
    if not quests:
        return []
    owner._queue_checkpoint(CHECKPOINT_REASON_QUEST_UPDATE)
    messages: list[str] = []
    for quest in quests:
        title = quest.get("title") or quest.get("id")
        xp_reward = int(quest.get("exp_reward") or 0)
        msg = f"Side-quest completed: {title}"
        if xp_reward > 0:
            owner.avatar.exp = (owner.avatar.exp or 0) + xp_reward
            msg = f"{msg} (+{xp_reward} XP)"
        owner.db.add(ChatMessage(session_id=owner.state.session_id, role="system", content=msg))
        messages.append(msg)
    return messages
