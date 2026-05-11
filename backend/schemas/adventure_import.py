from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.core.adventure_format import CURRENT_VERSION, FORMAT_NAME


class Pacing(BaseModel):
    scene_length: Literal["short", "normal", "long"] | None = Field(None, description="short|normal|long")
    event_frequency: Literal["low", "normal", "high"] | None = Field(None, description="low|normal|high")
    notes: str | None = None


class Protagonist(BaseModel):
    name: str | None = None
    role: str | None = None
    description: str | None = None
    image_hint: str | None = None
    hp: int | None = None
    mana: int | None = None
    stamina: int | None = None


class CharacterSpec(BaseModel):
    id: str | None = None
    name: str | None = None
    role: str | None = None
    description: str | None = None
    start_scene_id: str | None = None
    is_npc: bool | None = True
    image_hint: str | None = None
    npc_type: str | None = None
    movement_type: str | None = None
    hp: int | None = None
    mana: int | None = None
    stamina: int | None = None


class SceneSpec(BaseModel):
    id: str | None = None
    title: str | None = None
    description: str | None = None
    is_hidden: bool | None = False


class ItemSpec(BaseModel):
    id: str | None = None
    name: str | None = None
    type: str | None = None
    description: str | None = None
    start_scene_id: str | None = None
    properties: dict[str, Any] | None = None


class AdventureTemplateImportPayload(BaseModel):
    format: str = Field(default=FORMAT_NAME, description="Canonical TaleWeaver import format")
    version: str = Field(default=CURRENT_VERSION, description="Import format version, e.g. '1.0'")
    id: str | None = None
    title: str
    teaser: str | None = None
    subtitle: str | None = None
    description: str | None = None
    story_idea: str | None = None
    tone: str | None = None
    image_style: str | None = None
    image_styles: list[str] | None = None
    rule_enforcement_mode: Literal["rpg", "story", "chat"] | None = None
    pacing: Pacing | None = None
    protagonist: Protagonist | None = None
    characters: list[CharacterSpec] | None = None
    scenes: list[SceneSpec] | None = None
    items: list[ItemSpec] | None = None
    objects: list[ItemSpec] | None = None
    time_per_turn: int | None = None
    pacing_minutes: int | None = None
    clock_enabled: bool | None = None
    start_date: str | None = None
    start_time: str | None = None
    start_datetime: str | None = None
    quests: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
    generate_npc_images: bool = False
    generate_item_images: bool = False
    automatic_cover_generation: bool = False
    min_scenes: int | None = 1
    max_scenes: int | None = 5
