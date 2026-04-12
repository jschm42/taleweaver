import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import AsyncSessionLocal
from backend.models.game_state import GameState
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.user import User

from backend.engine.command_parser import CommandParser
from backend.core.llm_router import GameMasterLLM
from backend.engine.memory_manager import MemoryManager

router = APIRouter(prefix="/ws", tags=["WebSocket"])
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, game_id: str):
        await ws.accept()
        self.active_connections[game_id] = ws

    def disconnect(self, game_id: str):
        if game_id in self.active_connections:
            del self.active_connections[game_id]

    async def send_message(self, message: str, game_id: str, role: str = "assistant"):
        if game_id in self.active_connections:
            payload = json.dumps({"role": role, "content": message})
            await self.active_connections[game_id].send_text(payload)
            
    async def broadcast_sheet(self, game_id: str, sheet: dict):
        if game_id in self.active_connections:
            payload = json.dumps({"type": "sheet_update", "data": sheet})
            await self.active_connections[game_id].send_text(payload)

manager = ConnectionManager()

@router.websocket("/adventure/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await manager.connect(websocket, game_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                user_msg = payload.get("content", "").strip()
            except json.JSONDecodeError:
                continue

            if not user_msg:
                continue
                
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(GameState).where(GameState.id == game_id))
                state = result.scalars().first()
                if not state:
                    await manager.send_message("System Error: Game not found.", game_id, "system")
                    continue

                av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
                avatar = av_res.scalars().first()
                
                u_res = await db.execute(select(User).where(User.id == state.user_id))
                user = u_res.scalars().first()

                # Bypass LLM for slash commands
                if user_msg.startswith("/"):
                    response = CommandParser.parse_command(avatar, user_msg)
                    await db.commit()
                    await manager.send_message(response, game_id, "system")
                    await manager.broadcast_sheet(game_id, {
                        "hp": avatar.hp, "inventory": avatar.inventory, "equipment": avatar.equipment
                    })
                    continue
                
                # Text Chat
                user_chat = ChatMessage(game_state_id=game_id, role="user", content=user_msg)
                db.add(user_chat)
                await db.flush()

                hist_res = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.game_state_id == game_id)
                    .order_by(ChatMessage.created_at.asc())
                )
                history = [{"role": msg.role, "content": msg.content} for msg in hist_res.scalars().all()]
                
                try:
                    llm = GameMasterLLM(user)
                    context_messages = MemoryManager.build_context(avatar, "A dark fantasy world.", history)
                    
                    response_text = llm.execute_simple_task(
                        system_prompt=context_messages[0]["content"],
                        user_prompt=user_msg,
                        model="openai/gpt-4o-mini"
                    )
                    
                    gm_chat = ChatMessage(game_state_id=game_id, role="assistant", content=response_text)
                    db.add(gm_chat)
                    await db.commit()
                    
                    await manager.send_message(response_text, game_id, "assistant")

                except Exception as e:
                    logger.exception("LLM Error")
                    await manager.send_message(f"GM Error: {str(e)}", game_id, "system")

    except WebSocketDisconnect:
        manager.disconnect(game_id)
