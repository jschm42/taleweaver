from typing import Any, Optional

from pydantic import BaseModel


class SessionStateBase(BaseModel):
    current_scene_id: str
    in_game_time: int = 0
    inventory: list[str] = []
    entity_states: dict[str, Any] = {}
    exit_states: dict[str, Any] = {}
    discovered_scenes: list[str] = []
    is_completed: bool = False
    is_debug_enabled: bool = False

class SessionStateCreate(SessionStateBase):
    session_id: str

class SessionStateUpdate(BaseModel):
    scene_id: Optional[str] = None
    current_scene_id: Optional[str] = None
    in_game_time: Optional[int] = None
    inventory: Optional[list[str]] = None
    entity_states: Optional[dict[str, Any]] = None
    exit_states: Optional[dict[str, Any]] = None
    discovered_scenes: Optional[list[str]] = None
    is_completed: Optional[bool] = None
    is_debug_enabled: Optional[bool] = None

class GameSessionBase(BaseModel):
    user_id: str
    avatar_id: str
    template_id: str
    status: str = "active"

class GameSessionCreate(GameSessionBase):
    pass

class GameSessionUpdate(BaseModel):
    status: Optional[str] = None

class GameSession(GameSessionBase):
    id: str
    state: Optional[SessionStateBase] = None
    model_config = {"from_attributes": True}
