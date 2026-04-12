"""
WebSocket endpoint for real-time game communication.

Handles the main game loop: slash commands are routed directly to the
CommandParser (O(1) JSON mutations), while natural-language input is
forwarded to the GameMasterLLM. In strict_rules mode the LLM returns a
structured GameEvent that is validated and applied by the RuleEngine.
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.core.database import AsyncSessionLocal
from backend.models.adventure import Adventure
from backend.models.game_state import GameState
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.user import User

from backend.engine.command_parser import CommandParser
from backend.engine.rule_engine import RuleEngine, GameEvent, GameOverException
from backend.core.llm_router import GameMasterLLM
from backend.engine.memory_manager import MemoryManager

router = APIRouter(prefix="/ws", tags=["WebSocket"])
logger = logging.getLogger(__name__)

# Default LLM model used for all game interactions
DEFAULT_MODEL = "openai/gpt-4o-mini"


class ConnectionManager:
    """Manages active WebSocket connections keyed by game_id."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, game_id: str) -> None:
        await ws.accept()
        self.active_connections[game_id] = ws
        logger.info("WebSocket connected for game %s", game_id)

    def disconnect(self, game_id: str) -> None:
        if game_id in self.active_connections:
            del self.active_connections[game_id]
            logger.info("WebSocket disconnected for game %s", game_id)

    async def send_message(self, message: str, game_id: str, role: str = "assistant") -> None:
        """Sends a chat message payload to the client."""
        if game_id in self.active_connections:
            payload = json.dumps({"role": role, "content": message})
            await self.active_connections[game_id].send_text(payload)

    async def broadcast_sheet(self, game_id: str, sheet: dict) -> None:
        """Sends a full character-sheet snapshot to the client."""
        if game_id in self.active_connections:
            payload = json.dumps({"type": "sheet_update", "data": sheet})
            await self.active_connections[game_id].send_text(payload)

    async def send_game_over(self, game_id: str, reason: str) -> None:
        """Notifies the client that the game has ended."""
        if game_id in self.active_connections:
            payload = json.dumps({"type": "game_over", "reason": reason})
            await self.active_connections[game_id].send_text(payload)


manager = ConnectionManager()


def _build_sheet(avatar: Avatar) -> dict:
    """Builds a serialisable character-sheet snapshot from an Avatar ORM object."""
    return {
        "name": avatar.name,
        "hp": avatar.hp,
        "stamina": avatar.stamina,
        "mana": avatar.mana,
        "stats": avatar.stats,
        "inventory": avatar.inventory,
        "equipment": avatar.equipment,
        "status_effects": avatar.status_effects,
    }


@router.websocket("/adventure/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str) -> None:
    """
    Main WebSocket game loop.

    Expected client message format:
        {"content": "<player input>"}

    Server sends one of:
        {"role": "assistant"|"system", "content": "..."}   — chat message
        {"type": "sheet_update", "data": {...}}             — character sheet
        {"type": "game_over", "reason": "..."}             — game-over event
    """
    await manager.connect(websocket, game_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                user_msg = payload.get("content", "").strip()
            except json.JSONDecodeError:
                await manager.send_message("Invalid message format. Expected JSON with 'content' key.", game_id, "system")
                continue

            if not user_msg:
                continue

            async with AsyncSessionLocal() as db:
                # --- Load game state ---
                state_res = await db.execute(select(GameState).where(GameState.id == game_id))
                state = state_res.scalars().first()
                if not state:
                    await manager.send_message("System Error: Game session not found.", game_id, "system")
                    continue

                if state.is_paused:
                    await manager.send_message("The game is currently paused.", game_id, "system")
                    continue

                av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
                avatar = av_res.scalars().first()

                u_res = await db.execute(select(User).where(User.id == state.user_id))
                user = u_res.scalars().first()

                adv_res = await db.execute(select(Adventure).where(Adventure.id == state.adventure_id))
                adventure = adv_res.scalars().first()

                # --- Slash-command fast path (no LLM call) ---
                if user_msg.startswith("/"):
                    response = CommandParser.parse_command(avatar, user_msg)
                    await db.commit()
                    await manager.send_message(response, game_id, "system")
                    await manager.broadcast_sheet(game_id, _build_sheet(avatar))
                    continue

                # --- Natural-language path ---
                user_chat = ChatMessage(game_state_id=game_id, role="user", content=user_msg)
                db.add(user_chat)
                await db.flush()

                hist_res = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.game_state_id == game_id)
                    .order_by(ChatMessage.created_at.asc())
                )
                history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in hist_res.scalars().all()
                ]

                try:
                    llm = GameMasterLLM(user)
                    context_messages = MemoryManager.build_context(avatar, "A dark fantasy world.", history)
                    system_prompt = context_messages[0]["content"]

                    if adventure and adventure.strict_rules:
                        # Structured output: LLM returns a validated GameEvent
                        game_event: GameEvent = llm.execute_complex_task(
                            system_prompt=system_prompt,
                            user_prompt=user_msg,
                            response_schema=GameEvent,
                            model=DEFAULT_MODEL,
                        )
                        try:
                            narrative = RuleEngine.apply_event(avatar, game_event)
                        except GameOverException as exc:
                            await db.commit()
                            await manager.send_message(str(exc), game_id, "system")
                            await manager.broadcast_sheet(game_id, _build_sheet(avatar))
                            await manager.send_game_over(game_id, str(exc))
                            continue

                        response_text = narrative
                    else:
                        # Free-form narrative response
                        response_text = llm.execute_simple_task(
                            system_prompt=system_prompt,
                            user_prompt=user_msg,
                            model=DEFAULT_MODEL,
                        )

                    gm_chat = ChatMessage(game_state_id=game_id, role="assistant", content=response_text)
                    db.add(gm_chat)
                    await db.commit()

                    await manager.send_message(response_text, game_id, "assistant")
                    await manager.broadcast_sheet(game_id, _build_sheet(avatar))

                except Exception:
                    logger.exception("LLM processing error for game %s", game_id)
                    await manager.send_message("The Game Master is momentarily unavailable. Please try again.", game_id, "system")

    except WebSocketDisconnect:
        manager.disconnect(game_id)
