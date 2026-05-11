from typing import Any

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
    scene_id: str | None = None
    current_scene_id: str | None = None
    in_game_time: int | None = None
    inventory: list[str] | None = None
    entity_states: dict[str, Any] | None = None
    exit_states: dict[str, Any] | None = None
    discovered_scenes: list[str] | None = None
    is_completed: bool | None = None
    is_debug_enabled: bool | None = None

class GameSessionBase(BaseModel):
    user_id: str
    avatar_id: str
    template_id: str
    status: str = "active"

class GameSessionCreate(GameSessionBase):
    pass

class GameSessionUpdate(BaseModel):
    status: str | None = None

class GameSession(GameSessionBase):
    id: str
    state: SessionStateBase | None = None
    model_config = {"from_attributes": True}
