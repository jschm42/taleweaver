from pydantic import BaseModel, Field, model_validator, field_validator
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from backend.schemas.adventure import AdventureTemplateUpdate, AdventureTemplateDebugResponse

class CreateAdventureTemplatePayload(BaseModel):
    """Payload for creating a new adventure. Backwards-compatible with previous tests (avatar_name optional)."""
    id: Optional[str] = None  # Client-side UUID optional; server will generate if missing
    title: str
    avatar_name: Optional[str] = None
    image_url: Optional[str] = None
    language: Optional[str] = None
    original_prompt: Optional[str] = None
    intro_text: Optional[str] = None
    rule_enforcement_mode: Optional[Literal["rpg", "story", "chat"]] = "rpg"
    generate_scene_images: bool = False
    generate_npc_images: bool = False
    generate_item_images: bool = False
    time_per_turn: int = 5
    pacing_minutes: Optional[int] = None
    clock_enabled: Optional[bool] = False
    game_over_rules: Optional[Dict[str, Any]] = None
    selected_image_styles: Optional[List[Dict[str, Any]]] = None
    selected_tone: Optional[Dict[str, Any]] = None
    # Advanced/import fields
    original_manifest: Optional[Dict[str, Any]] = None
    automatic_cover_generation: Optional[bool] = False
    pacing: Optional[Dict[str, Any]] = None
    min_scenes: int = 1
    max_scenes: int = 5
    award_generation_enabled: bool = False
    min_awards: int = 3
    max_awards: int = 8
    is_adventure_generator: bool = False

    @model_validator(mode='after')
    def validate_scene_range(self) -> 'CreateAdventureTemplatePayload':
        if self.max_scenes < self.min_scenes:
            raise ValueError("max_scenes must be greater than or equal to min_scenes")
        return self

class AdventureTemplateResponse(BaseModel):
    """Full adventure details returned to the client."""
    id: str
    title: str
    teaser: Optional[str] = None
    language: Optional[str] = None
    origin_id: Optional[str] = None

    rule_enforcement_mode: str
    time_per_turn: int
    pacing_minutes: int
    clock_enabled: bool
    game_over_rules: Optional[Dict[str, Any]]
    selected_image_styles: Optional[List[Dict[str, Any]]] = None
    selected_tone: Optional[Dict[str, Any]] = None
    original_prompt: Optional[str] = None
    quests: Optional[List[Dict[str, Any]]] = None
    awards: Optional[List[Dict[str, Any]]] = None
    is_completed: bool = False
    is_ready: bool = True
    creation_status: Optional[str] = None
    creation_error: Optional[str] = None
    image_url: Optional[str] = None
    is_adventure_generator: bool = False
    min_scenes: int = 1
    max_scenes: int = 5


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

    # GM Capabilities
    allow_dynamic_items: bool = True

    # Narrative Meta (User editable in Plot tab)
    plot: Optional[str] = None
    rules: Optional[str] = None
    intro_text: Optional[str] = None
    walkthrough: Optional[str] = None
    completed_condition: Optional[str] = None
    gameover_condition: Optional[str] = None

    model_config = {"from_attributes": True}

class GameSessionResponse(BaseModel):
    """Summary of a game session (SessionState + linked entities)."""
    game_id: str
    template_id: Optional[str] = None
    adventure_id: Optional[str] = None
    avatar_id: str
    profile_image: Optional[str] = None
    adventure_title: str
    image_url: Optional[str] = None
    scene_id: str
    current_scene_name: Optional[str] = None
    in_game_time: int
    is_ready: bool = True
    creation_status: Optional[str] = None
    creation_error: Optional[str] = None
    selected_tone: Optional[Dict[str, Any]] = None
    progress: int = 0
    quest_count: int = 0
    completed_quest_count: int = 0
    award_count: int = 0
    earned_award_count: int = 0
    created_at: Optional[datetime] = None
    status: str = "active"
    status_note: Optional[str] = None

    @field_validator("selected_tone", mode="before")
    @classmethod
    def parse_legacy_tone(cls, v):
        if isinstance(v, str):
            return {"id": v, "name": v.capitalize()}
        return v

class AdventureTemplateSummaryResponse(BaseModel):
    """Summary of an adventure template for management views."""
    template_id: str
    title: str
    teaser: Optional[str] = None
    language: Optional[str] = None
    image_url: Optional[str] = None
    is_ready: bool = True
    creation_status: Optional[str] = None
    creation_error: Optional[str] = None
    selected_tone: Optional[Dict[str, Any]] = None
    progress: int = 0
    quest_count: int = 0
    completed_quest_count: int = 0
    active_game_id: Optional[str] = None
    has_active_session: bool = False
    scene_id: Optional[str] = None
    current_scene_name: Optional[str] = None
    origin_id: Optional[str] = None
    is_adventure_generator: bool = False

    @field_validator("selected_tone", mode="before")
    @classmethod
    def parse_legacy_tone(cls, v):
        if isinstance(v, str):
            return {"id": v, "name": v.capitalize()}
        return v

class ImportCheckItem(BaseModel):
    title: str
    origin_id: Optional[str] = None
    already_exists: bool
    existing_template_id: Optional[str] = None

class ImportCheckResponse(BaseModel):
    available_imports: List[ImportCheckItem]

class ChatRequest(BaseModel):
    content: str
    auto_visualize: bool = False
    language: Optional[str] = None

class ChatResponse(BaseModel):
    messages: List[Dict[str, Any]]
    sheet: Dict[str, Any]
    combat: Optional[Dict[str, Any]] = None
    mermaid: Optional[str] = None
    nodes: Optional[Dict[str, Any]] = None
    entities: Optional[List[Dict[str, Any]]] = None
    npc_metadata: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    adventure_image: Optional[str] = None
    quests: Optional[List[Dict[str, Any]]] = None
    awards: Optional[List[Dict[str, Any]]] = None
    is_completed: bool = False
    game_over: bool = False
    game_completed: bool = False
    status_note: Optional[str] = None
    full_world: Optional[AdventureTemplateDebugResponse] = None

class AdventureTemplateImportPayload(BaseModel):
    url: Optional[str] = None
    file_path: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    rule_enforcement_mode: Optional[str] = None
