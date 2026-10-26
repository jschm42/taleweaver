"""NPC persistence and portraits."""

from __future__ import annotations

from typing import Any, Optional

from backend.core.config import settings
from backend.engine.elevenlabs_voices import VoiceOption, custom_voice_id, resolve_voice_reference
from backend.engine.image_prompt_context import build_npc_image_prompt, clean_appearance
from backend.engine.manifest_apply.assets import find_duplicate_image_url, needs_image
from backend.engine.manifest_apply.context import ApplyContext
from backend.engine.manifest_apply.visuals import (
    generate_image,
    pick_existing_image,
    placeholder_image,
    t2i_config,
    uses_advanced_model,
)
from backend.engine.voice_casting import CastingCandidate, cast_npc_voices, resolve_voice_setup
from backend.models.world_entity import WorldEntity

# NPC settings that may appear at the top level (generated manifests) or inside
# `metadata_json` (exported manifests). The top-level value wins.
_METADATA_FIELDS = (
    "equipped_weapon_id",
    "equipped_armor_id",
    "special_actions",
    "attack_mode",
    "attack_trigger",
    "special_chance",
    "on_defeat_script",
    "on_defeat_text",
    "on_protagonist_enters_scene_script",
    "on_protagonist_enters_scene_text",
    "on_interact_script",
    "on_interact_text",
)
_METADATA_DEFAULTS: dict[str, Any] = {"special_actions": [], "attack_mode": "PASSIVE"}


def inventory_item_id(entry: Any) -> Optional[str]:
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return None
    return next(
        (
            entry[k]
            for k in ("id", "item_id", "object_id")
            if isinstance(entry.get(k), str) and entry[k].strip()
        ),
        None,
    )


def npc_metadata(npc: dict[str, Any]) -> dict[str, Any]:
    """Keeps every stored NPC setting (so new fields survive export/import) and normalizes the known ones."""
    stored = dict(npc["metadata_json"]) if isinstance(npc.get("metadata_json"), dict) else {}
    metadata = dict(stored)
    for key in _METADATA_FIELDS:
        value = npc.get(key)
        if value in (None, "", []):
            value = stored.get(key)
        if value in (None, "", []):
            value = _METADATA_DEFAULTS.get(key)
        metadata[key] = value
    return metadata


def npc_inventory_ids(npc: dict[str, Any]) -> list[str]:
    ids = [i for i in (inventory_item_id(e) for e in npc.get("inventory") or []) if i]
    meta = npc_metadata(npc)
    for equipped in (meta.get("equipped_weapon_id"), meta.get("equipped_armor_id")):
        if equipped and equipped not in ids:
            ids.append(equipped)
    return ids


def _is_moveable(npc: dict[str, Any]) -> bool:
    if npc.get("moveable") is not None:
        return bool(npc.get("moveable"))
    return str(npc.get("movement_type") or "").upper() == "MOVABLE"


async def _generate_portrait(
    ctx: ApplyContext, npc: dict[str, Any], idx: int, total: int
) -> Optional[str]:
    from backend.engine.media_engine import MediaEngine

    prompt = build_npc_image_prompt(npc["name"], npc["description"], npc.get("appearance"))
    user_config, api_keys = t2i_config(ctx)
    return await generate_image(
        ctx,
        status=f"Envisioning Portrait {idx}/{total}: {npc['name']}...",
        prompt=prompt,
        factory=lambda: MediaEngine.generate_entity_image(
            prompt,
            ctx.template_id,
            npc["id"],
            "NPC",
            user_config,
            api_keys,
            style_instruction=ctx.style_instruction,
            use_advanced_model=uses_advanced_model(ctx, "profile_model_quality", "advanced"),
        ),  # fmt: skip
        timeout=float(settings.VISUAL_TIMEOUT),
        failure_label=f"NPC image generation for {ctx.template_id}/{npc['id']}",
    )


async def _npc_image(
    ctx: ApplyContext,
    npc: dict[str, Any],
    processed: list[dict],
    cache: dict[str, str],
    position: tuple[int, int],
) -> Optional[str]:
    image_url = await pick_existing_image(
        ctx,
        kind="npc",
        label=f"NPC: {npc.get('name')}",
        source_asset_id=npc.get("source_asset_id"),
        before=[
            find_duplicate_image_url(npc, processed, cache),
            ctx.existing_images.get(npc["id"]),
        ],
        after=[npc.get("image_url")],
    )
    if not needs_image(image_url):
        return image_url
    if ctx.user and ctx.gen_npc:
        image_url = await _generate_portrait(ctx, npc, *position)
    if not needs_image(image_url):
        return image_url
    return await placeholder_image(ctx, npc["id"], category="NPC", subdir="entities")


def _casting_candidate(npc: dict[str, Any], voices: list[VoiceOption]) -> CastingCandidate:
    """Custom voices are kept; others outside the list (or names the world builder wrote) are
    mapped to a list id or recast."""
    text = " ".join(str(npc.get(key) or "") for key in ("name", "description", "character"))
    voice = npc.get("voice")
    if custom_voice_id(voice) is None:
        voice = resolve_voice_reference(voice, voices)
    return CastingCandidate(str(npc["id"]), text, voice)


def _stored_voice(npc: dict[str, Any], cast: dict[str, Optional[str]]) -> Optional[str]:
    """What to store: a custom voice as written, else the cast voice (imports keep theirs under Gemini)."""
    if custom_voice_id(npc.get("voice")):
        return npc["voice"]
    return cast.get(npc["id"]) or npc.get("voice")


def _npc_entity(
    ctx: ApplyContext,
    npc: dict[str, Any],
    image_url: Optional[str],
    default_scene_id: str,
    voice: Optional[str] = None,
) -> WorldEntity:
    moveable = _is_moveable(npc)
    declared_movable = str(npc.get("movement_type") or "").upper() == "MOVABLE"
    return WorldEntity(
        id=npc["id"],
        template_id=ctx.template_id,
        entity_type="NPC",
        name=npc["name"],
        description=npc["description"],
        appearance=clean_appearance(npc.get("appearance")),
        goal=npc.get("goal"),
        character=npc.get("character"),
        current_scene_id=npc.get("start_scene_id")
        or npc.get("current_scene_id")
        or default_scene_id,
        spatial_position=npc.get("spatial_position"),
        image_url=image_url,
        voice=voice,
        npc_type=npc.get("npc_type"),
        movement_type="MOVABLE"
        if (npc.get("moveable") is True or declared_movable)
        else "STATIONARY",
        moveable=moveable,
        allowed_scenes=npc.get("allowed_scenes") or [],
        notes=npc.get("notes") or None,
        hp=npc.get("hp"),
        max_hp=npc.get("hp"),
        mana=npc.get("mana"),
        max_mana=npc.get("mana"),
        stamina=npc.get("stamina"),
        max_stamina=npc.get("stamina"),
        is_hidden=npc.get("is_hidden", False),
        reveal_rule=npc.get("reveal_rule") or None,
        is_attackable=npc.get("is_attackable", True),
        is_killable=npc.get("is_killable", True),
        metadata_json=npc_metadata(npc),
    )


async def persist_npcs(
    ctx: ApplyContext, npcs: list[dict[str, Any]], default_scene_id: str
) -> dict[str, list[str]]:
    """Persists NPCs with portraits. Returns NPC id -> inventory item ids."""
    processed: list[dict] = []
    image_cache: dict[str, str] = {}
    total = len(npcs)
    setup = await resolve_voice_setup(ctx.db)
    voices = cast_npc_voices(setup, [_casting_candidate(npc, setup.voices) for npc in npcs])
    for idx, npc in enumerate(npcs, start=1):
        if npc["id"] in ctx.seen_entity_ids:
            continue
        ctx.seen_entity_ids.add(npc["id"])
        image_url = await _npc_image(ctx, npc, processed, image_cache, (idx, total))
        if image_url:
            image_cache[npc["id"]] = image_url
        processed.append(npc)
        voice = _stored_voice(npc, voices)
        ctx.db.add(_npc_entity(ctx, npc, image_url, default_scene_id, voice))
        await ctx.commit_and_refresh()
    return {npc["id"]: npc_inventory_ids(npc) for npc in npcs}
