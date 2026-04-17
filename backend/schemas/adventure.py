from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal

class QuestSchema(BaseModel):
    id: str
    title: str
    description: str
    goal: str
    impact: str
    exp_reward: int
    is_main: bool
    status: Literal["open", "completed"] = "open"

class AdventureBase(BaseModel):
    title: str = Field(..., max_length=50)
    image_url: Optional[str] = None
    context: Optional[str] = Field(None, max_length=2000)
    strict_rules: Optional[bool] = True
    rule_enforcement_mode: Optional[str] = "strict"
    time_per_turn: Optional[int] = 5
    pacing_minutes: Optional[int] = 5
    clock_enabled: Optional[bool] = False
    selected_image_styles: Optional[List[str]] = None
    selected_tone: Optional[str] = None
    game_over_rules: Optional[Dict[str, Any]] = None
    quests: Optional[List[QuestSchema]] = None
    is_completed: bool = False


class AdventureCreate(AdventureBase):
    pass

class AdventureUpdate(BaseModel):
    title: Optional[str] = None
    strict_rules: Optional[bool] = None
    rule_enforcement_mode: Optional[str] = None
    time_per_turn: Optional[int] = None
    pacing_minutes: Optional[int] = None
    clock_enabled: Optional[bool] = None
    selected_image_styles: Optional[List[str]] = None
    selected_tone: Optional[str] = None
    game_over_rules: Optional[Dict[str, Any]] = None

class AdventureInDBBase(AdventureBase):
    id: str

    class Config:
        from_attributes = True

class Adventure(AdventureInDBBase):
    pass

class AdventureDebugResponse(BaseModel):
    adventure: Dict[str, Any]
    protagonist: Optional[Dict[str, Any]] = None
    scenes: List[Dict[str, Any]]
    npcs: List[Dict[str, Any]]
    objects: List[Dict[str, Any]]
    exits: List[Dict[str, Any]]
