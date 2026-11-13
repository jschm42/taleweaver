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
NPC_TYPE_CAP_KEYS: tuple[str, ...] = ("humanoid", "being", "animal", "monster")
SPAWN_CHANCE_KEYS: tuple[str, ...] = (
    "npc",
    "enemy",
    "humanoid",
    "being",
    "animal",
    "monster",
    "item",
    "container",
    "switch",
)
DEFAULT_SPAWN_CHANCES: dict[str, int] = {
    "npc": 55,
    "enemy": 35,
    "humanoid": 50,
    "being": 20,
    "animal": 30,
    "monster": 25,
    "item": 75,
    "container": 30,
    "switch": 20,
}

_AUDIO_MODE_ALIASES: dict[str, AudioMode] = {
    "off": "empty",
    "disabled": "empty",
    "none": "empty",
    "silent": "empty",
}


class DynamicNpcTypeCaps(BaseModel):
    """Per-NPC-type maximum spawn caps (0-5) for dynamic scenes."""

    humanoid: int = Field(default=2, ge=0, le=5)
    being: int = Field(default=2, ge=0, le=5)
    animal: int = Field(default=2, ge=0, le=5)
    monster: int = Field(default=2, ge=0, le=5)


class DynamicNpcTypeCapsOverride(BaseModel):
    """Optional exit-level overrides for per-NPC-type caps (None = inherit)."""

    humanoid: Optional[int] = Field(default=None, ge=0, le=5)
    being: Optional[int] = Field(default=None, ge=0, le=5)
    animal: Optional[int] = Field(default=None, ge=0, le=5)
    monster: Optional[int] = Field(default=None, ge=0, le=5)


class DynamicSpawnChances(BaseModel):
    """Percentage chances (0-100) controlling dynamic entity and object spawns."""

    npc: int = Field(default=55, ge=0, le=100)
    enemy: int = Field(default=35, ge=0, le=100)
    humanoid: int = Field(default=50, ge=0, le=100)
    being: int = Field(default=20, ge=0, le=100)
    animal: int = Field(default=30, ge=0, le=100)
    monster: int = Field(default=25, ge=0, le=100)
    item: int = Field(default=75, ge=0, le=100)
    container: int = Field(default=30, ge=0, le=100)
    switch: int = Field(default=20, ge=0, le=100)


class DynamicSpawnChancesOverride(BaseModel):
    """Optional exit-level overrides for spawn chances (None = inherit)."""

    npc: Optional[int] = Field(default=None, ge=0, le=100)
    enemy: Optional[int] = Field(default=None, ge=0, le=100)
    humanoid: Optional[int] = Field(default=None, ge=0, le=100)
    being: Optional[int] = Field(default=None, ge=0, le=100)
    animal: Optional[int] = Field(default=None, ge=0, le=100)
    monster: Optional[int] = Field(default=None, ge=0, le=100)
    item: Optional[int] = Field(default=None, ge=0, le=100)
    container: Optional[int] = Field(default=None, ge=0, le=100)
    switch: Optional[int] = Field(default=None, ge=0, le=100)


class DynamicZoneConfig(BaseModel):
    """Configuration attached to an exit that expands procedurally into dynamic scenes."""

    enabled: bool = True
    zone_id: str = Field(..., min_length=1, max_length=40)
    theme: str = Field(..., min_length=1, max_length=1000)
    depth: int = Field(default=1, ge=1, le=10)
    max_depth: int = Field(default=3, ge=1, le=6)
    danger_level: DangerLevel = "medium"
    max_npcs: int = Field(default=2, ge=0, le=5)
    npc_type_caps: Optional[DynamicNpcTypeCapsOverride] = None
    spawn_chances: Optional[DynamicSpawnChancesOverride] = None
    audio_mode: Optional[AudioMode] = None
    allowed_entity_types: list[str] = Field(
        default_factory=lambda: list(DEFAULT_ALLOWED_ENTITY_TYPES)
    )
    cul_de_sac_on_max_depth: bool = True
    on_after_generated_script: Optional[str] = Field(default=None, max_length=8000)


class DynamicGenerationConfig(BaseModel):
    """Adventure-level settings controlling how dynamic scenes render visuals and music."""

    scene_image_mode: SceneImageMode = "simple"
    npc_image_mode: NpcImageMode = "simple"
    item_image_mode: NpcImageMode = "simple"
    audio_mode: AudioMode = "inherit"
    max_npcs: int = Field(default=2, ge=0, le=5)
    npc_type_caps: DynamicNpcTypeCaps = Field(default_factory=DynamicNpcTypeCaps)
    spawn_chances: DynamicSpawnChances = Field(default_factory=DynamicSpawnChances)
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
    """Scoped object, equipment, consumable, container, readable, or switch in a dynamic scene."""

    id: str = Field(..., min_length=1, max_length=48)
    name: str = Field(..., min_length=1, max_length=100)
    item_type: Literal[
        "STANDARD", "CONSUMABLE", "WEARABLE", "WEAPON", "CONTAINER", "READABLE", "SWITCH"
    ] = "STANDARD"
    description: str = Field(..., min_length=1, max_length=1500)
    visual_description: str = Field(default="", max_length=1000)
    is_takeable: bool = True
    wearable_slots: list[str] = Field(default_factory=list)
    stat_modifier_strength: int = Field(default=0, ge=-5, le=10)
    stat_modifier_dexterity: int = Field(default=0, ge=-5, le=10)
    stat_modifier_intelligence: int = Field(default=0, ge=-5, le=10)
    stat_modifier_wisdom: int = Field(default=0, ge=-5, le=10)
    stat_modifier_charisma: int = Field(default=0, ge=-5, le=10)
    stat_modifier_armor_class: int = Field(default=0, ge=-5, le=10)
    hp_change: int = Field(default=0, ge=-100, le=100)
    stamina_change: int = Field(default=0, ge=-100, le=100)
    mana_change: int = Field(default=0, ge=-100, le=100)
    damage_dice: Optional[str] = Field(default=None, max_length=20)
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


def _clamp_optional_int(value: Any, low: int, high: int) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(low, min(high, parsed))


def _normalize_npc_type_caps(raw: Any, *, partial: bool = False) -> Optional[dict[str, Any]]:
    data = raw if isinstance(raw, dict) else {}
    if partial:
        result = {key: _clamp_optional_int(data.get(key), 0, 5) for key in NPC_TYPE_CAP_KEYS}
        return result if any(v is not None for v in result.values()) else None
    return {key: _clamp_int(data.get(key), default=2, low=0, high=5) for key in NPC_TYPE_CAP_KEYS}


def _normalize_spawn_chances(raw: Any, *, partial: bool = False) -> Optional[dict[str, Any]]:
    data = raw if isinstance(raw, dict) else {}
    if partial:
        result = {key: _clamp_optional_int(data.get(key), 0, 100) for key in SPAWN_CHANCE_KEYS}
        return result if any(v is not None for v in result.values()) else None
    return {
        key: _clamp_int(data.get(key), default=DEFAULT_SPAWN_CHANCES[key], low=0, high=100)
        for key in SPAWN_CHANCE_KEYS
    }


def resolve_effective_dynamic_rules(
    zone: dict[str, Any], generation_config: Optional[dict[str, Any]] = None
) -> tuple[dict[str, int], dict[str, int]]:
    """Merge adventure dynamic_generation defaults with per-exit zone overrides."""
    base_cfg = normalize_dynamic_generation(generation_config)
    base_caps = dict(base_cfg.get("npc_type_caps") or {})
    base_chances = dict(base_cfg.get("spawn_chances") or {})

    zone_caps = zone.get("npc_type_caps") if isinstance(zone.get("npc_type_caps"), dict) else {}
    zone_chances = zone.get("spawn_chances") if isinstance(zone.get("spawn_chances"), dict) else {}

    eff_caps = {
        key: _clamp_int(
            zone_caps[key] if zone_caps.get(key) is not None else base_caps.get(key),
            default=2,
            low=0,
            high=5,
        )
        for key in NPC_TYPE_CAP_KEYS
    }
    eff_chances = {
        key: _clamp_int(
            zone_chances[key] if zone_chances.get(key) is not None else base_chances.get(key),
            default=DEFAULT_SPAWN_CHANCES[key],
            low=0,
            high=100,
        )
        for key in SPAWN_CHANCE_KEYS
    }
    return eff_caps, eff_chances


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

    caps_override = _normalize_npc_type_caps(raw.get("npc_type_caps"), partial=True)
    chances_override = _normalize_spawn_chances(raw.get("spawn_chances"), partial=True)
    raw_after_script = raw.get("on_after_generated_script")
    after_script = str(raw_after_script).strip() if raw_after_script is not None else ""

    return DynamicZoneConfig(
        enabled=True,
        zone_id=zone_id,
        theme=theme[:1000],
        depth=depth,
        max_depth=max_depth,
        danger_level=danger,  # type: ignore[arg-type]
        max_npcs=max_npcs,
        npc_type_caps=(
            DynamicNpcTypeCapsOverride.model_validate(caps_override) if caps_override else None
        ),
        spawn_chances=(
            DynamicSpawnChancesOverride.model_validate(chances_override)
            if chances_override
            else None
        ),
        audio_mode=zone_audio_mode,
        allowed_entity_types=allowed_types,
        cul_de_sac_on_max_depth=bool(cul_de_sac),
        on_after_generated_script=after_script[:8000] if after_script else None,
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
    npc_type_caps = _normalize_npc_type_caps(data.get("npc_type_caps"), partial=False)
    spawn_chances = _normalize_spawn_chances(data.get("spawn_chances"), partial=False)

    interlude = data.get("interlude_quote_enabled")
    if interlude is None:
        interlude = True

    return DynamicGenerationConfig(
        scene_image_mode=scene_mode,  # type: ignore[arg-type]
        npc_image_mode=npc_mode,  # type: ignore[arg-type]
        item_image_mode=item_mode,  # type: ignore[arg-type]
        audio_mode=audio_mode,  # type: ignore[arg-type]
        max_npcs=max_npcs,
        npc_type_caps=DynamicNpcTypeCaps.model_validate(npc_type_caps),
        spawn_chances=DynamicSpawnChances.model_validate(spawn_chances),
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
