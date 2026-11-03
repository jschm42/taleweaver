"""Using a protagonist talent during a turn (``/talent`` command or typed ``use``/``cast``).

The engine part is deterministic: it checks the unlock state, the uses left and the cost,
resolves the target in the current scene, pays the cost, counts the use and runs the
talent's ``on_use_script`` (with a ``talent`` dict in scope). A successful use then chains
a Game Master turn that narrates the effect (``[TALENT_USED]`` reaction prompt).

Talents are used outside fights; during combat the fight controls take over.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.turn_pass_flow import sse_system
from backend.engine.rules.talents import (
    TALENT_COMMAND,
    TalentRequest,
    availability_problem,
    normalize_talents,
    parse_talent_command,
    parse_typed_talent,
    uses_left,
)

logger = logging.getLogger(__name__)

_COMMAND_USAGE = f"Usage: {TALENT_COMMAND} <talent> [| <target>]"


@dataclass
class TalentTarget:
    id: str
    name: str
    kind: str  # "NPC" | "ITEM"


@dataclass
class TalentOutcome:
    """System messages to stream and, after a successful use, the Game Master prompt."""

    messages: list[str] = field(default_factory=list)
    reaction_prompt: Optional[str] = None


def _talents(manager: Any) -> list[dict[str, Any]]:
    return normalize_talents((manager.avatar.stats or {}).get("talents"))


def resolve_talent_request(manager: Any, user_msg: str) -> Optional[TalentRequest]:
    """The talent use the message asks for, or None for an ordinary turn."""
    talents = _talents(manager)
    if (user_msg or "").strip().lower().startswith(TALENT_COMMAND):
        return parse_talent_command(talents, user_msg)
    return parse_typed_talent(talents, user_msg)


def _talent_list_text(manager: Any) -> str:
    stats = manager.avatar.stats or {}
    unlocked = set(stats.get("unlocked_talents") or [])
    names = [t["name"] for t in _talents(manager) if t["id"] in unlocked]
    if not names:
        return "You have no talents yet."
    return "Your talents: " + ", ".join(names) + f". {_COMMAND_USAGE}"


async def _find_item_target(manager: Any, hint: str) -> Optional[TalentTarget]:
    low = hint.strip().lower()
    entities = await AdventureLogic.build_session_entities(manager.db, manager.state)
    carried = [e for e in manager.avatar.inventory or [] if isinstance(e, dict)]
    scene_items = [e for e in entities if str(e.get("entity_type") or "").upper() == "OBJECT"]
    for entry in [*carried, *scene_items]:
        if low in (str(entry.get("id") or "").lower(), str(entry.get("name") or "").lower()):
            return TalentTarget(str(entry.get("id")), str(entry.get("name") or entry["id"]), "ITEM")
    return None


async def _find_npc_target(manager: Any, hint: str) -> Optional[TalentTarget]:
    npc = await manager._find_scene_npc_by_hint(hint)
    return TalentTarget(str(npc.id), str(npc.name), "NPC") if npc else None


async def _resolve_target(
    manager: Any, talent: dict[str, Any], hint: str
) -> tuple[Optional[TalentTarget], Optional[str]]:
    """(target, problem). Talents without a target type ignore the hint."""
    kind = talent["target_type"]
    if kind == "NONE":
        return None, None
    if not hint:
        if kind == "ANY":
            return None, None
        noun = "whom" if kind == "NPC" else "what"
        return (
            None,
            f"Use {talent['name']} on {noun}? Name a target, e.g. 'use {talent['name']} on ...'.",
        )
    finders = {
        "NPC": (_find_npc_target,),
        "ITEM": (_find_item_target,),
        "ANY": (_find_npc_target, _find_item_target),
    }[kind]
    for finder in finders:
        target = await finder(manager, hint)
        if target:
            return target, None
    return None, f"There is no '{hint}' here to use {talent['name']} on."


def _pay_and_count(manager: Any, talent: dict[str, Any]) -> int:
    """Pays the cost and counts the use. Returns the uses so far."""
    avatar = manager.avatar
    cost_type = talent["cost_type"]
    setattr(avatar, cost_type, max(0, int(getattr(avatar, cost_type) or 0) - talent["cost"]))
    stats = dict(avatar.stats or {})
    uses = dict(stats.get("talent_uses") or {})
    uses[talent["id"]] = int(uses.get(talent["id"]) or 0) + 1
    stats["talent_uses"] = uses
    avatar.stats = stats
    flag_modified(avatar, "stats")
    return uses[talent["id"]]


def _usage_line(talent: dict[str, Any], target: Optional[TalentTarget]) -> str:
    on_target = f" on {target.name}" if target else ""
    cost = f" (-{talent['cost']} {talent['cost_type'].title()})" if talent["cost"] else ""
    return f"✨ You use {talent['name']}{on_target}{cost}."


async def _run_on_use_script(
    manager: Any, talent: dict[str, Any], target: Optional[TalentTarget], uses: int
) -> list[str]:
    code = str(talent.get("on_use_script") or "").strip()
    if not code:
        return []
    scope = {
        "talent": {
            "id": talent["id"],
            "name": talent["name"],
            "target_id": target.id if target else None,
            "target_name": target.name if target else None,
            "target_type": target.kind if target else None,
            "uses": uses,
            "uses_left": uses_left(talent, (manager.avatar.stats or {}).get("talent_uses") or {}),
        }
    }
    try:
        return await manager._execute_inline_script(
            code, "talent_on_use", talent["id"], extra_scope=scope
        )
    except Exception:
        logger.exception("[Turn %s] Talent script failed", manager.game_id)
        return []


def _reaction_prompt(talent: dict[str, Any], target: Optional[TalentTarget]) -> str:
    on_target = f" on {target.name} (ID {target.id})" if target else ""
    prompt = (
        f"[TALENT_USED] The player just used the talent '{talent['name']}'{on_target}. "
        f"Talent: {talent['description'] or talent['name']}. "
        "The engine already paid its cost and ran its effects: do not change the player's "
        "mana or stamina for it again. As the Game Master, narrate what the talent does in this "
        "moment, let present NPCs react in character and apply any consequences that now trigger."
    )
    hint = str(talent.get("gm_hint") or "").strip()
    return f"{prompt} Author's instruction for this talent: {hint}" if hint else prompt


async def use_talent(manager: Any, request: TalentRequest) -> TalentOutcome:
    """Runs the deterministic part of a talent use."""
    talent = request.talent
    if talent is None:
        if not request.query:
            return TalentOutcome([_talent_list_text(manager)])
        return TalentOutcome([f"You have no talent called '{request.query}'. {_COMMAND_USAGE}"])

    stats = manager.avatar.stats or {}
    pool = int(getattr(manager.avatar, talent["cost_type"]) or 0)
    problem = availability_problem(talent, stats, pool)
    target, target_problem = (
        (None, None) if problem else await _resolve_target(manager, talent, request.target_hint)
    )
    problem = problem or target_problem
    if problem:
        return TalentOutcome([problem])

    uses = _pay_and_count(manager, talent)
    messages = [_usage_line(talent, target)]
    text = str(talent.get("on_use_text") or "").strip()
    if text:
        messages.append(text)
    for message in messages:
        await manager._save_chat_message("system", message)
    messages += await _run_on_use_script(manager, talent, target, uses)
    return TalentOutcome(messages, _reaction_prompt(talent, target))


async def stream_talent_turn(
    manager: Any, user_input: str, request: TalentRequest, language: Optional[str]
) -> AsyncGenerator[str, None]:
    """Streams a talent use: engine messages, then the Game Master's narration."""
    if user_input and not user_input.lower().startswith(TALENT_COMMAND):
        await manager._save_chat_message("user", user_input)
    outcome = await use_talent(manager, request)
    if not outcome.reaction_prompt:
        for message in outcome.messages:
            await manager._save_chat_message("system", message)
    for message in outcome.messages:
        yield sse_system(message)
    if not outcome.reaction_prompt:
        await manager.db.commit()
        yield await manager._command_final_event()
        return

    yield f"event: status\ndata: {json.dumps({'content': 'The Game Master reacts...'})}\n\n"
    try:
        async for chunk in manager._run_llm_cycle(
            outcome.reaction_prompt, False, language=language
        ):
            yield chunk
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        from backend.api.routes.adventures import gameplay_logic as gl

        detail = gl._friendly_llm_error_message(exc) or gl._friendly_llm_unexpected_error_message()
        yield f"event: error\ndata: {json.dumps({'detail': detail, 'retryable': True})}\n\n"
