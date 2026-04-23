from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class SessionStateBase(BaseModel):
    current_scene_id: str
    in_game_time: int = 0
    inventory: List[str] = []
    entity_states: Dict[str, Any] = {}
    exit_states: Dict[str, Any] = {}
    discovered_scenes: List[str] = []
    is_paused: bool = False
    is_completed: bool = False
    is_debug_enabled: bool = False

class SessionStateCreate(SessionStateBase):
    session_id: str

class SessionStateUpdate(BaseModel):
    scene_id: Optional[str] = None
    current_scene_id: Optional[str] = None
    in_game_time: Optional[int] = None
    inventory: Optional[List[str]] = None
    entity_states: Optional[Dict[str, Any]] = None
    exit_states: Optional[Dict[str, Any]] = None
    discovered_scenes: Optional[List[str]] = None
    is_paused: Optional[bool] = None
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
