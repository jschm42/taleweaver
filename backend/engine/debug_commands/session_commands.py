"""``/debug`` sub-commands that toggle session flags or fire game triggers."""

from __future__ import annotations

from copy import deepcopy
from typing import Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.debug_commands.context import DebugContext
from backend.engine.rules.sequence_walkthrough import (
    format_walkthrough_steps,
    sequence_walkthrough_steps,
)

_LOG_ON_MESSAGE = (
    "[DEBUG_LOG_ON] Technical logging enabled. You will now see GameEvent outcomes in chat."
)
_LOG_OFF_MESSAGE = "[DEBUG_LOG_OFF] Technical logging disabled."


async def log_on(ctx: DebugContext) -> str:
    ctx.state.is_debug_enabled = True
    return _LOG_ON_MESSAGE


async def log_off(ctx: DebugContext) -> str:
    ctx.state.is_debug_enabled = False
    return _LOG_OFF_MESSAGE


async def log_toggle(ctx: DebugContext) -> Optional[str]:
    """``/debug log on|off``; anything else falls through to the usage text."""
    parts = ctx.parts
    if len(parts) < 2:
        return None
    toggles = {"on": log_on, "off": log_off}
    handler = toggles.get(parts[1].lower())
    return await handler(ctx) if handler else None


async def npc_drop_items(ctx: DebugContext) -> str:
    parts = ctx.parts
    if len(parts) >= 2 and parts[1].lower() == "drop_items":
        return "[TRIGGER_NPC_DROP_ITEMS]"
    return "DEBUG ERROR: Usage: /debug npc drop_items"


async def dynamic_items(ctx: DebugContext) -> str:
    parts = ctx.parts
    if len(parts) < 3 or parts[1].lower() != "dynamic":
        return "DEBUG ERROR: Usage: /debug item dynamic [on/off]"
    cmd = parts[2].lower()
    if cmd == "on":
        return "DEBUG ERROR: Spontaneous item generation is permanently disabled in this version."
    if cmd == "off":
        ctx.state.allow_dynamic_items = False
        return "[DEBUG_DYNAMIC_ITEMS_OFF] Dynamic item generation disabled for this session."
    return "DEBUG ERROR: Usage: /debug item dynamic [on/off]"


async def game_won(ctx: DebugContext) -> str:
    state = ctx.state
    if state.quests:
        new_quests = deepcopy(state.quests)
        for quest in new_quests:
            if quest.get("is_main"):
                quest["status"] = "completed"
        state.quests = new_quests
        flag_modified(state, "quests")
    return "[TRIGGER_GAME_COMPLETED] Debug: Manual victory trigger."


async def game_over(ctx: DebugContext) -> str:
    return "[TRIGGER_GAME_OVER] Debug: Manual game over trigger."


async def quest_finished(ctx: DebugContext) -> str:
    state = ctx.state
    if not state.quests:
        return "DEBUG: No quests found in session state."
    new_quests = deepcopy(state.quests)
    target = next((q for q in new_quests if q.get("status") == "open"), None)
    if not target:
        return "DEBUG: No open quests found to finish."
    target["status"] = "completed"
    state.quests = new_quests
    flag_modified(state, "quests")
    return f"DEBUG: Quest '{target.get('title') or target.get('id')}' marked as completed."


async def open_exit(ctx: DebugContext) -> str:
    parts = ctx.parts
    if len(parts) < 2:
        return "DEBUG ERROR: Usage: /debug open_exit [EXIT_ID]"
    exit_id = parts[1]
    overrides = dict(ctx.state.exit_states or {})
    entry = dict(overrides.get(exit_id) or {})
    entry["is_locked"] = False
    overrides[exit_id] = entry
    ctx.state.exit_states = overrides
    flag_modified(ctx.state, "exit_states")
    return f"DEBUG: Exit '{exit_id}' is now unlocked."


async def walkthrough(ctx: DebugContext) -> str:
    steps = sequence_walkthrough_steps(
        getattr(ctx.adventure, "sequences", None), ctx.state.active_sequence_id
    )
    if not steps:
        return "DEBUG: No walkthrough available for this adventure."
    guide = format_walkthrough_steps(steps)
    return f"[TRIGGER_WALKTHROUGH_REVEAL_FREE] --- DEBUG: WALKTHROUGH ---\n{guide}"


async def gen_item(ctx: DebugContext) -> str:
    parts = ctx.args.split(" ", 1)
    if len(parts) < 2:
        return "DEBUG ERROR: Usage: /debug gen_item [PROMPT]"
    return f"[TRIGGER_GEN_ITEM] {parts[1]}"
