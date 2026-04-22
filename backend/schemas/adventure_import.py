from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal

from backend.core.adventure_format import FORMAT_NAME, CURRENT_VERSION


class Pacing(BaseModel):
    scene_length: Optional[Literal["short", "normal", "long"]] = Field(None, description="short|normal|long")
    event_frequency: Optional[Literal["low", "normal", "high"]] = Field(None, description="low|normal|high")
    notes: Optional[str] = None


class Protagonist(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    image_hint: Optional[str] = None


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
    properties: Optional[Dict[str, Any]] = None


class AdventureImportPayload(BaseModel):
    format: str = Field(default=FORMAT_NAME, description="Canonical TaleWeaver import format")
    version: str = Field(default=CURRENT_VERSION, description="Import format version, e.g. '1.0'")
    id: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    story_idea: Optional[str] = None
    tone: Optional[str] = None
    image_style: Optional[str] = None
    image_styles: Optional[List[str]] = None
    rule_enforcement_mode: Optional[Literal["rpg", "story", "chat"]] = None
    pacing: Optional[Pacing] = None
    protagonist: Optional[Protagonist] = None
    characters: Optional[List[CharacterSpec]] = None
    scenes: Optional[List[SceneSpec]] = None
    items: Optional[List[ItemSpec]] = None
    objects: Optional[List[ItemSpec]] = None
    time_per_turn: Optional[int] = None
    pacing_minutes: Optional[int] = None
    clock_enabled: Optional[bool] = None
    start_date: Optional[str] = None
    start_time: Optional[str] = None
    start_datetime: Optional[str] = None
    quests: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    generate_npc_images: bool = False
    generate_item_images: bool = False
    automatic_cover_generation: bool = False
    min_scenes: Optional[int] = 1
    max_scenes: Optional[int] = 5
