from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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
    image_url: str | None = None
    teaser: str | None = Field(None, max_length=300)
    version: str | None = Field(None, max_length=15)
    original_prompt: str | None = Field(None, max_length=20000)
    rule_enforcement_mode: Literal["rpg", "story", "chat"] | None = "rpg"
    time_per_turn: int | None = 5
    pacing_minutes: int | None = 5
    clock_enabled: bool | None = False
    time_system: str | None = "calendar"
    time_config: dict[str, Any] | None = None
    
    generate_npc_images: bool = True
    generate_item_images: bool = True
    generate_scene_images: bool = True
    automatic_cover_generation: bool = True
    
    selected_image_styles: list[dict[str, Any]] | None = None
    selected_tone: dict[str, Any] | None = None
    game_over_rules: dict[str, Any] | None = None
    quests: list[QuestSchema] | None = None
    awards: list[AwardSchema] | None = None
    is_completed: bool = False
    min_scenes: int | None = 1
    max_scenes: int | None = 5
    
    award_generation_enabled: bool = True
    min_awards: int = 3
    max_awards: int = 8
    is_adventure_generator: bool = False


    # Narrative Meta (User editable in Plot tab)
    plot: str | None = None
    rules: str | None = None
    intro_text: str | None = None
    walkthrough: str | None = None
    completed_condition: str | None = None
    gameover_condition: str | None = None
    tts_director_notes: str | None = None

    # GM Capabilities
    allow_dynamic_items: bool | None = True


class AdventureTemplateCreate(AdventureTemplateBase):
    pass

class AdventureTemplateUpdate(BaseModel):
    title: str | None = None
    teaser: str | None = Field(None, max_length=300)
    version: str | None = Field(None, max_length=15)
    original_prompt: str | None = Field(None, max_length=20000)
    rule_enforcement_mode: Literal["rpg", "story", "chat", "strict"] | None = None
    time_per_turn: int | None = None
    pacing_minutes: int | None = None
    clock_enabled: bool | None = None
    time_system: str | None = None
    time_config: dict[str, Any] | None = None
    selected_image_styles: list[dict[str, Any]] | None = None
    selected_tone: dict[str, Any] | None = None
    game_over_rules: dict[str, Any] | None = None
    min_scenes: int | None = None
    max_scenes: int | None = None
    max_awards: int | None = None
    is_adventure_generator: bool | None = None
    
    # Editable Narrative Meta
    plot: str | None = None
    rules: str | None = None
    intro_text: str | None = None
    walkthrough: str | None = None
    completed_condition: str | None = None
    gameover_condition: str | None = None
    tts_director_notes: str | None = None

    # GM Capabilities
    allow_dynamic_items: bool | None = None
    
    # Status and Warnings
    creation_error: str | None = None
    
    # Extra fields for frontend convenience
    selected_style_id: str | None = None
    selected_tone_id: str | None = None

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
    adventure: dict[str, Any]
    protagonist: dict[str, Any] | None = None
    scenes: list[dict[str, Any]]
    npcs: list[dict[str, Any]]
    objects: list[dict[str, Any]]
    exits: list[dict[str, Any]]
    entities_all: list[dict[str, Any]] | None = None
