"""Schemas and normalization helpers for procedural Dynamic Scenes and exits."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SceneImageMode = Literal["off", "inherit", "simple", "hq"]
NpcImageMode = Literal["off", "simple", "hq"]
AudioMode = Literal["inherit", "empty", "generate"]
DangerLevel = Literal["peaceful", "low", "medium", "high", "deadly", "random"]

DEFAULT_ALLOWED_ENTITY_TYPES: tuple[str, ...] = ("NPC", "OBJECT", "CONTAINER", "SWITCH")

_AUDIO_MODE_ALIASES: dict[str, AudioMode] = {
    "off": "empty",
    "disabled": "empty",
    "none": "empty",
    "silent": "empty",
}


class DynamicZoneConfig(BaseModel):
    """Configuration attached to an exit that expands procedurally into dynamic scenes."""

    enabled: bool = True
    zone_id: str = Field(..., min_length=1, max_length=40)
    theme: str = Field(..., min_length=1, max_length=1000)
    depth: int = Field(default=1, ge=1, le=10)
    max_depth: int = Field(default=3, ge=1, le=6)
    danger_level: DangerLevel = "medium"
    max_npcs: int = Field(default=2, ge=0, le=5)
    audio_mode: Optional[AudioMode] = None
    allowed_entity_types: list[str] = Field(
        default_factory=lambda: list(DEFAULT_ALLOWED_ENTITY_TYPES)
    )
    cul_de_sac_on_max_depth: bool = True


class DynamicGenerationConfig(BaseModel):
    """Adventure-level settings controlling how dynamic scenes render visuals and music."""

    scene_image_mode: SceneImageMode = "simple"
    npc_image_mode: NpcImageMode = "simple"
    item_image_mode: NpcImageMode = "simple"
    audio_mode: AudioMode = "inherit"
    max_npcs: int = Field(default=2, ge=0, le=5)
    interlude_quote_enabled: bool = True


class DynamicGeneratedNpc(BaseModel):
    """Scoped NPC generated inside a dynamic scene."""

    id: str = Field(..., min_length=1, max_length=48)
    name: str = Field(..., min_length=1, max_length=100)
    npc_type: Literal["HUMANOID", "ANIMAL", "MONSTER", "BEING"] = "HUMANOID"
    role: str = Field(default="Wanderer", max_length=100)
    description: str = Field(..., min_length=1, max_length=1500)
    visual_description: str = Field(default="", max_length=1000)
    attitude: Literal["friendly", "neutral", "hostile"] = "neutral"
    combat_role: Literal["none", "minion", "standard", "elite", "boss"] = "none"
    dialogue_style: str = Field(default="Speaks naturally in plain full sentences.", max_length=200)


class DynamicGeneratedObject(BaseModel):
    """Scoped object, container, readable, or switch generated inside a dynamic scene."""

    id: str = Field(..., min_length=1, max_length=48)
    name: str = Field(..., min_length=1, max_length=100)
    item_type: Literal["STANDARD", "CONSUMABLE", "CONTAINER", "READABLE", "SWITCH"] = "STANDARD"
    description: str = Field(..., min_length=1, max_length=1500)
    visual_description: str = Field(default="", max_length=1000)
    is_takeable: bool = True
    effect_type: Optional[str] = Field(default=None, max_length=60)
    effect_value: Optional[int] = Field(default=None)
    text_log_content: Optional[str] = Field(default=None, max_length=1000)


class DynamicGeneratedChildExit(BaseModel):
    """Deeper dynamic passage spawned from a non-terminal dynamic scene."""

    label: str = Field(..., min_length=1, max_length=120)
    theme_hint: str = Field(default="", max_length=400)


class DynamicGeneratedScenePayload(BaseModel):
    """Compact LLM output schema for a single procedurally generated dynamic scene."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=2000)
    visual_description: str = Field(default="", max_length=1000)
    music_prompt: str = Field(default="", max_length=600)
    npcs: list[DynamicGeneratedNpc] = Field(default_factory=list)
    objects: list[DynamicGeneratedObject] = Field(default_factory=list)
    forward_exits: list[DynamicGeneratedChildExit] = Field(default_factory=list)


class DynamicInterludeQuotePayload(BaseModel):
    """Short atmospheric NPC quote shown while a dynamic scene generates."""

    speaker: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="", max_length=100)
    quote: str = Field(..., min_length=1, max_length=280)


def _slugify_identifier(raw: Any, fallback: str = "dynamic_zone", max_len: int = 40) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", str(raw or "").strip().lower()).strip("_")
    return (cleaned or fallback)[:max_len]


def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def normalize_dynamic_zone(raw: Any) -> Optional[dict[str, Any]]:
    """Return a clean DynamicZoneConfig dict or None when disabled/empty."""
    if not isinstance(raw, dict):
        return None
    if raw.get("enabled") is False:
        return None
    theme = str(raw.get("theme") or "").strip()
    if not theme:
        return None

    zone_id = _slugify_identifier(raw.get("zone_id") or theme[:24], fallback="dynamic_zone")
    max_depth = _clamp_int(raw.get("max_depth"), default=3, low=1, high=6)
    depth = _clamp_int(raw.get("depth"), default=1, low=1, high=max_depth)
    max_npcs = _clamp_int(raw.get("max_npcs"), default=2, low=0, high=5)

    danger = str(raw.get("danger_level") or "medium").strip().lower()
    if danger not in {"peaceful", "low", "medium", "high", "deadly", "random"}:
        danger = "medium"

    raw_audio = str(raw.get("audio_mode") or "").strip().lower()
    raw_audio = _AUDIO_MODE_ALIASES.get(raw_audio, raw_audio)
    zone_audio_mode: Optional[AudioMode] = (
        raw_audio if raw_audio in {"inherit", "empty", "generate"} else None  # type: ignore[assignment]
    )

    raw_types = raw.get("allowed_entity_types")
    if isinstance(raw_types, list) and raw_types:
        allowed_types = [str(t).strip() for t in raw_types if str(t).strip()]
    else:
        allowed_types = list(DEFAULT_ALLOWED_ENTITY_TYPES)

    cul_de_sac = raw.get("cul_de_sac_on_max_depth")
    if cul_de_sac is None:
        cul_de_sac = True

    return DynamicZoneConfig(
        enabled=True,
        zone_id=zone_id,
        theme=theme[:1000],
        depth=depth,
        max_depth=max_depth,
        danger_level=danger,  # type: ignore[arg-type]
        max_npcs=max_npcs,
        audio_mode=zone_audio_mode,
        allowed_entity_types=allowed_types,
        cul_de_sac_on_max_depth=bool(cul_de_sac),
    ).model_dump()


def normalize_dynamic_generation(raw: Any) -> dict[str, Any]:
    """Return a clean DynamicGenerationConfig dict with safe defaults."""
    data = raw if isinstance(raw, dict) else {}

    scene_mode = str(data.get("scene_image_mode") or "simple").strip().lower()
    if scene_mode not in {"off", "inherit", "simple", "hq"}:
        scene_mode = "simple"

    npc_mode = str(data.get("npc_image_mode") or "simple").strip().lower()
    if npc_mode not in {"off", "simple", "hq"}:
        npc_mode = "simple"

    item_mode = str(data.get("item_image_mode") or "simple").strip().lower()
    if item_mode not in {"off", "simple", "hq"}:
        item_mode = "simple"

    audio_mode = str(data.get("audio_mode") or "inherit").strip().lower()
    audio_mode = _AUDIO_MODE_ALIASES.get(audio_mode, audio_mode)
    if audio_mode not in {"inherit", "empty", "generate"}:
        audio_mode = "inherit"

    max_npcs = _clamp_int(data.get("max_npcs"), default=2, low=0, high=5)

    interlude = data.get("interlude_quote_enabled")
    if interlude is None:
        interlude = True

    return DynamicGenerationConfig(
        scene_image_mode=scene_mode,  # type: ignore[arg-type]
        npc_image_mode=npc_mode,  # type: ignore[arg-type]
        item_image_mode=item_mode,  # type: ignore[arg-type]
        audio_mode=audio_mode,  # type: ignore[arg-type]
        max_npcs=max_npcs,
        interlude_quote_enabled=bool(interlude),
    ).model_dump()


def build_dynamic_placeholder_scene_id(
    zone_id: str,
    depth: int = 1,
    index: int = 1,
    suffix: str = "",
) -> str:
    """Build a deterministic, valid scene ID <= 30 chars for a dynamic exit target."""
    slug = _slugify_identifier(zone_id, fallback="ZONE", max_len=14).upper()
    clean_suffix = re.sub(r"[^A-Z0-9]+", "", str(suffix or "").upper())[:6]
    tail = f"_{clean_suffix}" if clean_suffix else ""
    candidate = f"DYN_{slug}_D{max(1, int(depth))}_{max(1, int(index))}{tail}"
    return candidate[:30]


def is_dynamic_exit_dict(ex: Any) -> bool:
    """Return True if an exit dictionary defines an enabled dynamic zone."""
    if not isinstance(ex, dict):
        return False
    return normalize_dynamic_zone(ex.get("dynamic_zone")) is not None
