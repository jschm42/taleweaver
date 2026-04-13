from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class AdventureBase(BaseModel):
    title: str = Field(..., max_length=50)
    image_url: Optional[str] = None
    context: Optional[str] = Field(None, max_length=2000)
    strict_rules: Optional[bool] = True
    time_per_turn: Optional[int] = 5
    game_over_rules: Optional[Dict[str, Any]] = None

class AdventureCreate(AdventureBase):
    character_id: str

class AdventureUpdate(BaseModel):
    title: Optional[str] = None
    strict_rules: Optional[bool] = None
    time_per_turn: Optional[int] = None
    game_over_rules: Optional[Dict[str, Any]] = None

class AdventureInDBBase(AdventureBase):
    id: str

    class Config:
        from_attributes = True

class Adventure(AdventureInDBBase):
    pass

class AdventureDebugResponse(BaseModel):
    adventure: Dict[str, Any]
    scenes: List[Dict[str, Any]]
    npcs: List[Dict[str, Any]]
    objects: List[Dict[str, Any]]
    exits: List[Dict[str, Any]]
