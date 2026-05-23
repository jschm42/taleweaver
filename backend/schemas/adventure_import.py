from __future__ import annotations
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from backend.core.adventure_format import CURRENT_VERSION, FORMAT_NAME


class Pacing(BaseModel):
    scene_length: Optional[Literal["short", "normal", "long"]] = Field(None, description="short|normal|long")
    event_frequency: Optional[Literal["low", "normal", "high"]] = Field(None, description="low|normal|high")
    notes: Optional[str] = None


class Protagonist(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    image_hint: Optional[str] = None
    hp: Optional[int] = None
    mana: Optional[int] = None
    stamina: Optional[int] = None


class CharacterSpec(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    start_scene_id: Optional[str] = None
    is_npc: Optional[bool] = True
    image_hint: Optional[str] = None
    npc_type: Optional[str] = None
    movement_type: Optional[str] = None
    hp: Optional[int] = None
    mana: Optional[int] = None
    stamina: Optional[int] = None


class SceneSpec(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    is_hidden: Optional[bool] = False


class ItemSpec(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    start_scene_id: Optional[str] = None
    properties: Optional[dict[str, Any]] = None


class AdventureTemplateImportPayload(BaseModel):
    format: str = Field(default=FORMAT_NAME, description="Canonical TaleWeaver import format")
    version: str = Field(default=CURRENT_VERSION, description="Import format version, e.g. '1.0'")
    id: Optional[str] = None
    title: str
    teaser: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    story_idea: Optional[str] = None
    tone: Optional[str] = None
    image_style: Optional[str] = None
    image_styles: Optional[list[str]] = None
    rule_enforcement_mode: Optional[Literal["rpg", "story", "chat"]] = None
    pacing: Optional[Pacing] = None
    protagonist: Optional[Protagonist] = None
    characters: Optional[list[CharacterSpec]] = None
    scenes: Optional[list[SceneSpec]] = None
    items: Optional[list[ItemSpec]] = None
    objects: Optional[list[ItemSpec]] = None
    time_per_turn: Optional[int] = None
    pacing_minutes: Optional[int] = None
    clock_enabled: Optional[bool] = None
    start_date: Optional[str] = None
    start_time: Optional[str] = None
    start_datetime: Optional[str] = None
    quests: Optional[list[dict[str, Any]]] = None
    metadata: Optional[dict[str, Any]] = None
    generate_npc_images: bool = False
    generate_item_images: bool = False
    automatic_cover_generation: bool = False
    min_scenes: Optional[int] = None
    max_scenes: Optional[int] = None
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    container_generation_enabled: bool = True
    min_containers: Optional[int] = None
    max_containers: Optional[int] = None
    text_log_generation_enabled: bool = True
    min_text_logs: Optional[int] = None
    max_text_logs: Optional[int] = None
    quest_generation_enabled: bool = True
    min_quests: Optional[int] = None
    max_quests: Optional[int] = None
    award_generation_enabled: bool = False
    min_awards: Optional[int] = None
    max_awards: Optional[int] = None
