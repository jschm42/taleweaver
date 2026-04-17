from pydantic import BaseModel
from typing import Optional

class GameStateBase(BaseModel):
    scene_id: str
    in_game_time: Optional[int] = 0

class GameStateCreate(GameStateBase):
    user_id: str
    avatar_id: str
    adventure_id: str

class GameStateUpdate(BaseModel):
    scene_id: Optional[str] = None
    in_game_time: Optional[int] = None

class GameStateInDBBase(GameStateBase):
    id: str
    user_id: str
    avatar_id: str
    adventure_id: str

    model_config = {"from_attributes": True}

class GameState(GameStateInDBBase):
    pass
