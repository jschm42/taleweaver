from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, field_validator, model_validator

from backend.schemas.adventure import AdventureTemplateDebugResponse


class CreateAdventureTemplatePayload(BaseModel):
    """Payload for creating a new adventure. Backwards-compatible with previous tests (avatar_name optional)."""
    id: Optional[str] = None  # Client-side UUID optional; server will generate if missing
    title: str
    avatar_name: Optional[str] = None
    image_url: Optional[str] = None
    teaser: Optional[str] = None
    version: Optional[str] = None
    language: Optional[str] = None
    original_prompt: Optional[str] = None
    intro_text: Optional[str] = None
    rule_enforcement_mode: Optional[Literal["rpg", "story", "chat"]] = "rpg"
    generate_scene_images: bool = False
    generate_npc_images: bool = False
    generate_item_images: bool = False
    automatic_npc_voice_assignment: bool = True
    time_per_turn: int = 5
    pacing_minutes: Optional[int] = None
    clock_enabled: Optional[bool] = False
    game_over_rules: Optional[dict[str, Any]] = None
    selected_image_styles: Optional[list[dict[str, Any]]] = None
    selected_tone: Optional[dict[str, Any]] = None
    tts_director_notes: Optional[str] = None
    # Advanced/import fields
    original_manifest: Optional[dict[str, Any]] = None
    automatic_cover_generation: Optional[bool] = False
    pacing: Optional[dict[str, Any]] = None
    min_scenes: int = 1
    max_scenes: int = 5
    award_generation_enabled: bool = False
    min_awards: int = 3
    max_awards: int = 8
    is_adventure_generator: bool = False
    cover_source_adventure_id: Optional[str] = None
    cover_source_adventure_name: Optional[str] = None
    cover_similarity_percent: int = 50
    allow_reuse_source_assets: bool = True

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

    @field_validator("cover_similarity_percent")
    @classmethod
    def validate_cover_similarity(cls, value: int) -> int:
        return max(0, min(100, int(value)))

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
    version: Optional[str] = None
    language: Optional[str] = None
    origin_id: Optional[str] = None

    rule_enforcement_mode: str
    strict_rules: bool = True
    time_per_turn: int
    pacing_minutes: int
    clock_enabled: bool
    game_over_rules: Optional[dict[str, Any]]
    selected_image_styles: Optional[list[dict[str, Any]]] = None
    selected_tone: Optional[dict[str, Any]] = None
    original_prompt: Optional[str] = None
    quests: Optional[list[dict[str, Any]]] = None
    awards: Optional[list[dict[str, Any]]] = None
    is_completed: bool = False
    is_ready: bool = True
    creation_status: Optional[str] = None
    creation_error: Optional[str] = None
    image_url: Optional[str] = None
    is_adventure_generator: bool = False
    cover_source_adventure_id: Optional[str] = None
    cover_source_adventure_name: Optional[str] = None
    cover_similarity_percent: int = 50
    allow_reuse_source_assets: bool = True
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
    tts_director_notes: Optional[str] = None

    model_config = {"from_attributes": True}

class GameSessionResponse(BaseModel):
    """Summary of a game session (SessionState + linked entities)."""
    game_id: str
    template_id: Optional[str] = None
    adventure_id: Optional[str] = None
    avatar_id: str
    profile_image: Optional[str] = None
    adventure_title: str
    adventure_version: Optional[str] = None
    image_url: Optional[str] = None
    scene_id: str
    current_scene_name: Optional[str] = None
    in_game_time: int
    is_ready: bool = True
    creation_status: Optional[str] = None
    creation_error: Optional[str] = None
    selected_tone: Optional[dict[str, Any]] = None
    progress: int = 0
    quest_count: int = 0
    completed_quest_count: int = 0
    award_count: int = 0
    earned_award_count: int = 0
    created_at: Optional[datetime] = None
    status: str = "active"
    status_note: Optional[str] = None
    copied_from_id: Optional[str] = None

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
    version: Optional[str] = None
    language: Optional[str] = None
    image_url: Optional[str] = None
    is_ready: bool = True
    creation_status: Optional[str] = None
    creation_error: Optional[str] = None
    selected_tone: Optional[dict[str, Any]] = None
    progress: int = 0
    quest_count: int = 0
    completed_quest_count: int = 0
    active_game_id: Optional[str] = None
    has_active_session: bool = False
    scene_id: Optional[str] = None
    current_scene_name: Optional[str] = None
    origin_id: Optional[str] = None
    is_adventure_generator: bool = False
    cover_source_adventure_id: Optional[str] = None
    cover_source_adventure_name: Optional[str] = None

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
    available_imports: list[ImportCheckItem]

class ChatRequest(BaseModel):
    content: str
    auto_visualize: bool = False
    language: Optional[str] = None


class TerminalEpilogueRequest(BaseModel):
    language: Optional[str] = None


class TerminalEpilogueResponse(BaseModel):
    content: Optional[str] = None
    game_over: bool = False
    game_completed: bool = False
    status_note: Optional[str] = None
    input_locked: bool = False
    pending_terminal_epilogue: bool = False

class ChatResponse(BaseModel):
    messages: list[dict[str, Any]]
    sheet: dict[str, Any]
    combat: Optional[dict[str, Any]] = None
    map_data: Optional[dict[str, Any]] = None
    nodes: Optional[dict[str, Any]] = None
    entities: Optional[list[dict[str, Any]]] = None
    npc_metadata: Optional[dict[str, Any]] = None
    image_url: Optional[str] = None
    adventure_image: Optional[str] = None
    quests: Optional[list[dict[str, Any]]] = None
    awards: Optional[list[dict[str, Any]]] = None
    is_completed: bool = False
    game_over: bool = False
    game_completed: bool = False
    status_note: Optional[str] = None
    input_locked: bool = False
    pending_terminal_epilogue: bool = False
    full_world: Optional[AdventureTemplateDebugResponse] = None

class AdventureTemplateImportPayload(BaseModel):
    url: Optional[str] = None
    file_path: Optional[str] = None
    content: Optional[dict[str, Any]] = None
    rule_enforcement_mode: Optional[str] = None

class SuggestPromptRequest(BaseModel):
    target_type: Literal["cover", "scene", "npc", "object", "protagonist"]
    target_id: str

class SuggestPromptResponse(BaseModel):
    suggested_prompt: str

class AdventureTemplateUpdate(BaseModel):
    """Payload for partial updates to an adventure template."""
    title: Optional[str] = None
    teaser: Optional[str] = None
    version: Optional[str] = None
    language: Optional[str] = None
    intro_text: Optional[str] = None
    original_prompt: Optional[str] = None
    rule_enforcement_mode: Optional[Literal["rpg", "story", "chat"]] = None
    time_per_turn: Optional[int] = None
    pacing_minutes: Optional[int] = None
    clock_enabled: Optional[bool] = None
    generate_scene_images: Optional[bool] = None
    generate_npc_images: Optional[bool] = None
    generate_item_images: Optional[bool] = None
    selected_image_styles: Optional[list[dict[str, Any]]] = None
    selected_tone: Optional[dict[str, Any]] = None
    min_scenes: Optional[int] = None
    max_scenes: Optional[int] = None
    award_generation_enabled: Optional[bool] = None
    min_awards: Optional[int] = None
    max_awards: Optional[int] = None
    plot: Optional[str] = None
    rules: Optional[str] = None
    walkthrough: Optional[str] = None
    completed_condition: Optional[str] = None
    gameover_condition: Optional[str] = None
    tts_director_notes: Optional[str] = None
    creation_error: Optional[str] = None
    strict_rules: Optional[bool] = None
    game_over_rules: Optional[dict[str, Any]] = None
    selected_style_id: Optional[str] = None
    selected_tone_id: Optional[str] = None
    time_system: Optional[str] = None
    allow_dynamic_items: Optional[bool] = None

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


class TraitGenerationRequest(BaseModel):
    target_type: Literal["npc", "protagonist"]
    name: str
    description: str
    adventure_theme: Optional[str] = None
    target_field: Optional[Literal["goal", "character"]] = None

class TraitGenerationResponse(BaseModel):
    goal: str
    character: str

