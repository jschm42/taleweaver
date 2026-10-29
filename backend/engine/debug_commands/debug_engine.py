from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.debug_commands import (
    entity_commands,
    inspect_commands,
    session_commands,
    world_commands,
)
from backend.engine.debug_commands.context import DebugContext, DebugHandler
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.user import User

_USAGE = (
    "DEBUG USAGE: /debug [on/off | npc drop_items | item dynamic on/off | session | szene | heal "
    "| scenes | npcs | items | exits | plot | context | map | reveal_map | log on/off | walkthrough "
    "| engine | award(s) | game_won | game_over | quest_finished | claim_awards | delete_item X "
    "| kill NPC | open_exit ID | gen_item PROMPT]"
)

# Sub-command -> handler. A handler returning None falls back to the usage text.
_HANDLERS: dict[str, DebugHandler] = {
    "szene": inspect_commands.scene_info,
    "entities": inspect_commands.scene_entities,
    "plot": inspect_commands.plot_context,
    "context": inspect_commands.plot_context,
    "map": inspect_commands.world_stats,
    "session": inspect_commands.session_info,
    "engine": inspect_commands.engine_info,
    "scenes": inspect_commands.list_scenes,
    "npcs": inspect_commands.list_npcs,
    "items": inspect_commands.list_items,
    "exits": inspect_commands.list_exits,
    "log": session_commands.log_toggle,
    "on": session_commands.log_on,
    "off": session_commands.log_off,
    "npc": session_commands.npc_drop_items,
    "item": session_commands.dynamic_items,
    "game_won": session_commands.game_won,
    "game_over": session_commands.game_over,
    "quest_finished": session_commands.quest_finished,
    "open_exit": session_commands.open_exit,
    "walkthrough": session_commands.walkthrough,
    "gen_item": session_commands.gen_item,
    "heal": entity_commands.heal,
    "unhide": entity_commands.unhide,
    "npc_note": entity_commands.npc_note,
    "note": entity_commands.npc_note,
    "moveable": entity_commands.moveable,
    "delete_item": entity_commands.delete_item,
    "exp": entity_commands.grant_exp,
    "award": world_commands.grant_awards,
    "awards": world_commands.grant_awards,
    "claim_awards": world_commands.grant_awards,
    "reveal_map": world_commands.reveal_map,
}


class DebugEngine:
    @staticmethod
    async def handle_debug_command(
        db: AsyncSession,
        state: SessionState,
        args: str,
        user: Optional[User] = None,
        adventure: Optional[AdventureTemplate] = None,
        avatar: Optional[Any] = None,
    ) -> str:
        """
        Processes /debug sub-commands and returns atmospheric yet technical info.

        Optional ``user`` and ``adventure`` objects are required for sub-commands
        that mutate persistent data (e.g. ``award``).
        """
        sub = args.split(" ", maxsplit=1)[0].lower() if args else ""
        handler = _HANDLERS.get(sub)
        if handler is None:
            return _USAGE
        ctx = DebugContext(db, state, args, user=user, adventure=adventure, avatar=avatar)
        return await handler(ctx) or _USAGE
