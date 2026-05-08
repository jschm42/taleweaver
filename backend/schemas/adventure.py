from pydantic import BaseModel, Field, field_validator
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

class AwardSchema(BaseModel):
    key: str
    title: str
    description: str
    tier: Literal["bronze", "silver", "gold"]
    requirement: str
    is_earned: bool = False

class AdventureTemplateBase(BaseModel):
    title: str = Field(..., max_length=50)
    image_url: Optional[str] = None
    teaser: Optional[str] = Field(None, max_length=300)
    version: Optional[str] = Field(None, max_length=15)
    original_prompt: Optional[str] = Field(None, max_length=20000)
    rule_enforcement_mode: Optional[Literal["rpg", "story", "chat"]] = "rpg"
    time_per_turn: Optional[int] = 5
    pacing_minutes: Optional[int] = 5
    clock_enabled: Optional[bool] = False
    time_system: Optional[str] = "calendar"
    time_config: Optional[Dict[str, Any]] = None
    
    generate_npc_images: bool = True
    generate_item_images: bool = True
    generate_scene_images: bool = True
    automatic_cover_generation: bool = True
    
    selected_image_styles: Optional[List[Dict[str, Any]]] = None
    selected_tone: Optional[Dict[str, Any]] = None
    game_over_rules: Optional[Dict[str, Any]] = None
    quests: Optional[List[QuestSchema]] = None
    awards: Optional[List[AwardSchema]] = None
    is_completed: bool = False
    min_scenes: Optional[int] = 1
    max_scenes: Optional[int] = 5
    
    award_generation_enabled: bool = True
    min_awards: int = 3
    max_awards: int = 8
    is_adventure_generator: bool = False


    # Narrative Meta (User editable in Plot tab)
    plot: Optional[str] = None
    rules: Optional[str] = None
    intro_text: Optional[str] = None
    walkthrough: Optional[str] = None
    completed_condition: Optional[str] = None
    gameover_condition: Optional[str] = None

    # GM Capabilities
    allow_dynamic_items: Optional[bool] = True


class AdventureTemplateCreate(AdventureTemplateBase):
    pass

class AdventureTemplateUpdate(BaseModel):
    title: Optional[str] = None
    teaser: Optional[str] = Field(None, max_length=300)
    version: Optional[str] = Field(None, max_length=15)
    original_prompt: Optional[str] = Field(None, max_length=20000)
    rule_enforcement_mode: Optional[Literal["rpg", "story", "chat", "strict"]] = None
    time_per_turn: Optional[int] = None
    pacing_minutes: Optional[int] = None
    clock_enabled: Optional[bool] = None
    time_system: Optional[str] = None
    time_config: Optional[Dict[str, Any]] = None
    selected_image_styles: Optional[List[Dict[str, Any]]] = None
    selected_tone: Optional[Dict[str, Any]] = None
    game_over_rules: Optional[Dict[str, Any]] = None
    min_scenes: Optional[int] = None
    max_scenes: Optional[int] = None
    max_awards: Optional[int] = None
    is_adventure_generator: Optional[bool] = None
    
    # Editable Narrative Meta
    plot: Optional[str] = None
    rules: Optional[str] = None
    intro_text: Optional[str] = None
    walkthrough: Optional[str] = None
    completed_condition: Optional[str] = None
    gameover_condition: Optional[str] = None

    # GM Capabilities
    allow_dynamic_items: Optional[bool] = None
    
    # Status and Warnings
    creation_error: Optional[str] = None
    
    # Extra fields for frontend convenience
    selected_style_id: Optional[str] = None
    selected_tone_id: Optional[str] = None

    @field_validator("selected_tone", mode="before")
    @classmethod
    def parse_legacy_tone(cls, v):
        if isinstance(v, str):
            return {"id": v, "name": v.capitalize()}
        return v

    @field_validator("selected_image_styles", mode="before")
    @classmethod
    def parse_legacy_styles(cls, v):
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], str):
            return [{"id": s, "name": s.capitalize()} for s in v]
        return v

class AdventureTemplateInDBBase(AdventureTemplateBase):
    id: str
    model_config = {"from_attributes": True}

class AdventureTemplate(AdventureTemplateInDBBase):
    pass

class AdventureTemplateDebugResponse(BaseModel):
    adventure: Dict[str, Any]
    protagonist: Optional[Dict[str, Any]] = None
    scenes: List[Dict[str, Any]]
    npcs: List[Dict[str, Any]]
    objects: List[Dict[str, Any]]
    exits: List[Dict[str, Any]]
    entities_all: Optional[List[Dict[str, Any]]] = None
