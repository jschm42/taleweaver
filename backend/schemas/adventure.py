from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class AdventureBase(BaseModel):
    title: str = Field(..., max_length=50)
    image_url: Optional[str] = None
    context: Optional[str] = Field(None, max_length=2000)
    strict_rules: Optional[bool] = True
    heartbeat_interval: Optional[int] = 60
    game_over_rules: Optional[Dict[str, Any]] = None

class AdventureCreate(AdventureBase):
    character_id: str

class AdventureUpdate(BaseModel):
    title: Optional[str] = None
    strict_rules: Optional[bool] = None
    heartbeat_interval: Optional[int] = None
    game_over_rules: Optional[Dict[str, Any]] = None

class AdventureInDBBase(AdventureBase):
    id: str

    class Config:
        from_attributes = True

class Adventure(AdventureInDBBase):
    pass
