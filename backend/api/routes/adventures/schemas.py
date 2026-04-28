from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from backend.schemas.adventure import AdventureTemplateUpdate, AdventureTemplateDebugResponse

class CreateAdventureTemplatePayload(BaseModel):
    """Payload for creating a new adventure. Backwards-compatible with previous tests (avatar_name optional)."""
    id: Optional[str] = None  # Client-side UUID optional; server will generate if missing
    title: str
    avatar_name: Optional[str] = None
    image_url: Optional[str] = None
    context: Optional[str] = None
    strict_rules: bool = True
    rule_enforcement_mode: Optional[Literal["rpg", "story", "chat"]] = "rpg"
    generate_scene_images: bool = False
    generate_npc_images: bool = False
    generate_item_images: bool = False
    time_per_turn: int = 5
    pacing_minutes: Optional[int] = None
    clock_enabled: Optional[bool] = False
    game_over_rules: Optional[Dict[str, Any]] = None
    selected_image_styles: Optional[List[str]] = None
    selected_tone: Optional[str] = None
    # Advanced/import fields
    original_manifest: Optional[Dict[str, Any]] = None
    automatic_cover_generation: Optional[bool] = False
    pacing: Optional[Dict[str, Any]] = None
    min_scenes: int = 1
    max_scenes: int = 5
    award_generation_enabled: bool = False
    min_awards: int = 3
    max_awards: int = 8

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
    strict_rules: bool
    rule_enforcement_mode: str
    time_per_turn: int
    pacing_minutes: int
    clock_enabled: bool
    game_over_rules: Optional[Dict[str, Any]]
    selected_image_styles: Optional[List[str]] = None
    selected_tone: Optional[str] = None
    context: Optional[str] = None
    quests: Optional[List[Dict[str, Any]]] = None
    awards: Optional[List[Dict[str, Any]]] = None
    is_completed: bool = False

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
    selected_tone: Optional[str] = None
    progress: int = 0
    quest_count: int = 0
    completed_quest_count: int = 0
    award_count: int = 0
    earned_award_count: int = 0
    created_at: Optional[datetime] = None

class AdventureTemplateSummaryResponse(BaseModel):
    """Summary of an adventure template for management views."""
    template_id: str
    title: str
    teaser: Optional[str] = None
    image_url: Optional[str] = None
    is_ready: bool = True
    creation_status: Optional[str] = None
    creation_error: Optional[str] = None
    selected_tone: Optional[str] = None
    progress: int = 0
    quest_count: int = 0
    completed_quest_count: int = 0
    active_game_id: Optional[str] = None
    has_active_session: bool = False
    scene_id: Optional[str] = None
    current_scene_name: Optional[str] = None

class ChatRequest(BaseModel):
    content: str
    auto_visualize: bool = False

class ChatResponse(BaseModel):
    messages: List[Dict[str, Any]]
    sheet: Dict[str, Any]
    mermaid: Optional[str] = None
    nodes: Optional[Dict[str, Any]] = None
    entities: Optional[List[Dict[str, Any]]] = None
    npc_metadata: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    adventure_image: Optional[str] = None
    quests: Optional[List[Dict[str, Any]]] = None
    awards: Optional[List[Dict[str, Any]]] = None
    is_completed: bool = False
    full_world: Optional[AdventureTemplateDebugResponse] = None

class AdventureTemplateImportPayload(BaseModel):
    url: Optional[str] = None
    file_path: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    rule_enforcement_mode: Optional[str] = None
