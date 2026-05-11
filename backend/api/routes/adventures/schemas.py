from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator

from backend.schemas.adventure import AdventureTemplateDebugResponse


class CreateAdventureTemplatePayload(BaseModel):
    """Payload for creating a new adventure. Backwards-compatible with previous tests (avatar_name optional)."""
    id: str | None = None  # Client-side UUID optional; server will generate if missing
    title: str
    avatar_name: str | None = None
    image_url: str | None = None
    teaser: str | None = None
    version: str | None = None
    language: str | None = None
    original_prompt: str | None = None
    intro_text: str | None = None
    rule_enforcement_mode: Literal["rpg", "story", "chat"] | None = "rpg"
    generate_scene_images: bool = False
    generate_npc_images: bool = False
    generate_item_images: bool = False
    automatic_npc_voice_assignment: bool = True
    time_per_turn: int = 5
    pacing_minutes: int | None = None
    clock_enabled: bool | None = False
    game_over_rules: dict[str, Any] | None = None
    selected_image_styles: list[dict[str, Any]] | None = None
    selected_tone: dict[str, Any] | None = None
    tts_director_notes: str | None = None
    # Advanced/import fields
    original_manifest: dict[str, Any] | None = None
    automatic_cover_generation: bool | None = False
    pacing: dict[str, Any] | None = None
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
    teaser: str | None = None
    version: str | None = None
    language: str | None = None
    origin_id: str | None = None

    rule_enforcement_mode: str
    time_per_turn: int
    pacing_minutes: int
    clock_enabled: bool
    game_over_rules: dict[str, Any] | None
    selected_image_styles: list[dict[str, Any]] | None = None
    selected_tone: dict[str, Any] | None = None
    original_prompt: str | None = None
    quests: list[dict[str, Any]] | None = None
    awards: list[dict[str, Any]] | None = None
    is_completed: bool = False
    is_ready: bool = True
    creation_status: str | None = None
    creation_error: str | None = None
    image_url: str | None = None
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
    plot: str | None = None
    rules: str | None = None
    intro_text: str | None = None
    walkthrough: str | None = None
    completed_condition: str | None = None
    gameover_condition: str | None = None
    tts_director_notes: str | None = None

    model_config = {"from_attributes": True}

class GameSessionResponse(BaseModel):
    """Summary of a game session (SessionState + linked entities)."""
    game_id: str
    template_id: str | None = None
    adventure_id: str | None = None
    avatar_id: str
    profile_image: str | None = None
    adventure_title: str
    adventure_version: str | None = None
    image_url: str | None = None
    scene_id: str
    current_scene_name: str | None = None
    in_game_time: int
    is_ready: bool = True
    creation_status: str | None = None
    creation_error: str | None = None
    selected_tone: dict[str, Any] | None = None
    progress: int = 0
    quest_count: int = 0
    completed_quest_count: int = 0
    award_count: int = 0
    earned_award_count: int = 0
    created_at: datetime | None = None
    status: str = "active"
    status_note: str | None = None

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
    teaser: str | None = None
    version: str | None = None
    language: str | None = None
    image_url: str | None = None
    is_ready: bool = True
    creation_status: str | None = None
    creation_error: str | None = None
    selected_tone: dict[str, Any] | None = None
    progress: int = 0
    quest_count: int = 0
    completed_quest_count: int = 0
    active_game_id: str | None = None
    has_active_session: bool = False
    scene_id: str | None = None
    current_scene_name: str | None = None
    origin_id: str | None = None
    is_adventure_generator: bool = False

    @field_validator("selected_tone", mode="before")
    @classmethod
    def parse_legacy_tone(cls, v):
        if isinstance(v, str):
            return {"id": v, "name": v.capitalize()}
        return v

class ImportCheckItem(BaseModel):
    title: str
    origin_id: str | None = None
    already_exists: bool
    existing_template_id: str | None = None

class ImportCheckResponse(BaseModel):
    available_imports: list[ImportCheckItem]

class ChatRequest(BaseModel):
    content: str
    auto_visualize: bool = False
    language: str | None = None


class TerminalEpilogueRequest(BaseModel):
    language: str | None = None


class TerminalEpilogueResponse(BaseModel):
    content: str | None = None
    game_over: bool = False
    game_completed: bool = False
    status_note: str | None = None
    input_locked: bool = False
    pending_terminal_epilogue: bool = False

class ChatResponse(BaseModel):
    messages: list[dict[str, Any]]
    sheet: dict[str, Any]
    combat: dict[str, Any] | None = None
    mermaid: str | None = None
    nodes: dict[str, Any] | None = None
    entities: list[dict[str, Any]] | None = None
    npc_metadata: dict[str, Any] | None = None
    image_url: str | None = None
    adventure_image: str | None = None
    quests: list[dict[str, Any]] | None = None
    awards: list[dict[str, Any]] | None = None
    is_completed: bool = False
    game_over: bool = False
    game_completed: bool = False
    status_note: str | None = None
    input_locked: bool = False
    pending_terminal_epilogue: bool = False
    full_world: AdventureTemplateDebugResponse | None = None

class AdventureTemplateImportPayload(BaseModel):
    url: str | None = None
    file_path: str | None = None
    content: dict[str, Any] | None = None
    rule_enforcement_mode: str | None = None

class SuggestPromptRequest(BaseModel):
    target_type: Literal["cover", "scene", "npc", "object", "protagonist"]
    target_id: str

class SuggestPromptResponse(BaseModel):
    suggested_prompt: str
