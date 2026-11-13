"""Scoped LLM generators for procedural Dynamic Scenes and interlude quotes."""

from __future__ import annotations

import logging
import random
import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.turn_context_helpers import resolve_model_settings
from backend.core.api_keys import has_api_key
from backend.core.llm_router import GameMasterLLM
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedScenePayload,
    DynamicInterludeQuotePayload,
    normalize_dynamic_zone,
)

logger = logging.getLogger(__name__)

_LOCAL_LLM_PROVIDERS = {"ollama", "lmstudio"}
_RANDOM_DANGER_CHOICES: tuple[str, ...] = ("peaceful", "low", "medium", "high", "deadly")
_SPEAKING_NPC_TYPES = {"HUMANOID", "BEING"}
_NON_SPEAKING_NPC_TYPES = {"ANIMAL", "MONSTER"}


def _is_speaking_npc(npc: Any) -> bool:
    """Return True if an NPC candidate is a speaking type (HUMANOID or BEING)."""
    if not isinstance(npc, dict) or not npc.get("name"):
        return False
    explicit_type = str(npc.get("npc_type") or "").strip().upper()
    if explicit_type:
        return explicit_type in _SPEAKING_NPC_TYPES
    role_type = str(npc.get("role") or "").strip().upper()
    return role_type not in _NON_SPEAKING_NPC_TYPES


def _pick_interlude_npc(candidate_npcs: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Choose a random living speaking NPC (HUMANOID/BEING) for the transition quote."""
    speaking = [npc for npc in candidate_npcs if _is_speaking_npc(npc)]
    if not speaking:
        return None
    alive = [npc for npc in speaking if not npc.get("is_defeated")]
    pool = alive or speaking
    return random.choice(pool)


def _strip_outer_quotes(text: str) -> str:
    cleaned = str(text or "").strip()
    if len(cleaned) >= 2 and cleaned[0] in {'"', "'", "“", "„"} and cleaned[-1] in {'"', "'", "”"}:
        return cleaned[1:-1].strip()
    return cleaned


def _build_interlude_prompts(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    exit_label: str,
    zone_theme: str,
    chosen_npc: Optional[dict[str, Any]],
    language: str,
) -> tuple[str, str]:
    npc_hint = (
        f"Speak in the voice of existing NPC '{chosen_npc['name']}' "
        f"(Character/Role: {chosen_npc.get('character') or chosen_npc.get('goal') or 'Companion'}; "
        f"Bio: {str(chosen_npc.get('description') or '')[:160]})."
        if chosen_npc
        else "Invent a brief, evocative speaker fitting the adventure tone (e.g. a seasoned scout, old chronicler, or whispered memory)."
    )
    system_prompt = (
        "You write ultra-short atmospheric transition quotes for an interactive RPG.\n"
        f"Return strict JSON matching the schema. Write ALL quote text strictly in {language}.\n"
        "The quote must be 1 to 2 short sentences (under 200 characters), evocative, and fit the tone."
    )
    user_prompt = (
        f"Adventure: {adventure_title}\n"
        f"Tone: {adventure_tone or 'Atmospheric Adventure'}\n"
        f"Setting excerpt: {adventure_setting[:300]}\n"
        f"Origin scene: {origin_scene_name}\n"
        f"Passage taken: {exit_label}\n"
        f"Destination zone theme: {zone_theme}\n"
        f"Speaker directive: {npc_hint}\n"
        "Respond with JSON fields: speaker, role, quote."
    )
    return system_prompt, user_prompt


def _has_provider_credentials(user: Any, provider: str) -> bool:
    if provider in _LOCAL_LLM_PROVIDERS:
        return True
    keys = getattr(user, "encrypted_api_keys", None) or {}
    return has_api_key(keys, provider)


async def generate_dynamic_interlude_quote(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    exit_label: str,
    zone_theme: str,
    candidate_npcs: list[dict[str, Any]],
    user: Any,
    db: AsyncSession,
    adventure_id: Optional[str] = None,
    game_id: Optional[str] = None,
    language: str = "English",
) -> Optional[dict[str, Any]]:
    """Generate a short NPC quote with the fast small model while a dynamic scene loads."""
    del db  # reserved for future settings lookups
    chosen_npc = _pick_interlude_npc(candidate_npcs)
    if chosen_npc is None:
        return None
    llm_settings = dict(getattr(user, "llm_settings", None) or {})
    resolved = resolve_model_settings(llm_settings)
    provider = str(resolved["small_model_provider"])
    model = str(resolved["small_model"])

    if not _has_provider_credentials(user, provider):
        return None

    system_prompt, user_prompt = _build_interlude_prompts(
        adventure_title=adventure_title,
        adventure_setting=adventure_setting,
        adventure_tone=adventure_tone,
        origin_scene_name=origin_scene_name,
        exit_label=exit_label,
        zone_theme=zone_theme,
        chosen_npc=chosen_npc,
        language=language or "English",
    )

    try:
        llm = GameMasterLLM(user, provider=provider, model_category="small")
        payload = await llm.aexecute_complex_task(
            system_prompt,
            user_prompt,
            DynamicInterludeQuotePayload,
            model,
            adventure_id=adventure_id,
            game_id=game_id,
            operation="dynamic_scene.interlude_quote",
            phase="transition",
        )
        quote_text = _strip_outer_quotes(payload.quote)[:260]
        if not quote_text:
            return None
        speaker = chosen_npc["name"] if chosen_npc else (payload.speaker or "Voice in the Mist")
        role = (
            str(chosen_npc.get("role") or payload.role or "")
            if chosen_npc
            else str(payload.role or "")
        )
        image_url = chosen_npc.get("image_url") if chosen_npc else None
        return {
            "quote": quote_text,
            "speaker_name": speaker,
            "speaker_role": role,
            "npc_id": chosen_npc.get("id") if chosen_npc else None,
            "voice": chosen_npc.get("voice") if chosen_npc else None,
            "image_url": image_url,
            "speaker": speaker,
            "role": role,
            "avatar_url": image_url,
        }
    except Exception as exc:
        logger.debug("Dynamic interlude quote skipped due to error: %s", exc)
        return None


def _roll_scene_plan(zone: dict[str, Any], max_npcs: int) -> dict[str, Any]:
    """Roll per-scene NPC and object composition targets so rooms feel varied."""
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    is_climax = depth >= max_depth and cul_de_sac

    allowed_tokens = {
        str(token or "").strip().upper()
        for token in (zone.get("allowed_entity_types") or ["NPC", "OBJECT", "CONTAINER", "SWITCH"])
    }
    npc_allowed = bool(allowed_tokens & {"NPC", "FRIENDLY_NPC", "HOSTILE_NPC"})
    target_npcs = random.randint(0, max_npcs) if (npc_allowed and max_npcs > 0) else 0

    allow_container = ("CONTAINER" in allowed_tokens) and (
        random.random() < (0.60 if is_climax else 0.30)
    )
    allow_switch = (
        ("SWITCH" in allowed_tokens) and (not allow_container) and (random.random() < 0.20)
    )

    target_objects = random.randint(1, 3) if is_climax else random.randint(0, 3)
    if (allow_container or allow_switch) and target_objects == 0:
        target_objects = 1

    allowed_item_types = ["STANDARD", "CONSUMABLE", "READABLE"]
    if allow_container:
        allowed_item_types.append("CONTAINER")
    if allow_switch:
        allowed_item_types.append("SWITCH")

    return {
        "target_npcs": target_npcs,
        "target_objects": target_objects,
        "allow_container": allow_container,
        "allow_switch": allow_switch,
        "allowed_item_types": allowed_item_types,
    }


def _apply_scene_plan_to_payload(
    payload: DynamicGeneratedScenePayload,
    scene_plan: dict[str, Any],
) -> None:
    """Enforce rolled NPC/object limits and disallow unrolled containers or switches."""
    payload.npcs = list(payload.npcs or [])[: int(scene_plan["target_npcs"])]
    target_objects = int(scene_plan["target_objects"])
    sliced_objects = list(payload.objects or [])[:target_objects]

    allow_switch = bool(scene_plan["allow_switch"])
    allow_container = bool(scene_plan["allow_container"])
    seen_switch = False
    seen_container = False

    for obj in sliced_objects:
        if obj.item_type == "SWITCH":
            if not allow_switch or seen_switch:
                obj.item_type = "STANDARD"
            else:
                seen_switch = True
        elif obj.item_type == "CONTAINER":
            if not allow_container or seen_container:
                obj.item_type = "STANDARD"
            else:
                seen_container = True

    payload.objects = sliced_objects


def _build_scene_prompts(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    origin_scene_description: str,
    exit_label: str,
    zone: dict[str, Any],
    language: str,
    effective_danger: str,
    max_npcs: int,
    scene_plan: dict[str, Any],
) -> tuple[str, str]:
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    is_climax = depth >= max_depth and cul_de_sac
    allowed = ", ".join(
        zone.get("allowed_entity_types") or ["NPC", "OBJECT", "CONTAINER", "SWITCH"]
    )

    depth_rule = (
        f"CLIMAX DEPTH ({depth}/{max_depth}): This is the end of the zone (cul-de-sac). "
        "Set forward_exits to an empty list []. Provide a memorable climax (reward container, lore discovery, or boss/guardian encounter)."
        if is_climax
        else f"EXPANSION DEPTH ({depth}/{max_depth}): Include 1 concise forward_exits entry leading deeper into the zone."
    )

    target_npcs = int(scene_plan["target_npcs"])
    target_objects = int(scene_plan["target_objects"])
    allowed_item_types = ", ".join(scene_plan["allowed_item_types"])

    npc_rule = (
        "- Do NOT spawn any NPCs in this scene (set npcs to an empty list [])."
        if target_npcs <= 0
        else f"- Spawn EXACTLY {target_npcs} NPC(s) matching the zone theme."
    )
    object_rule = (
        "\n- Do NOT spawn any interactable objects in this scene (set objects to an empty list [])."
        if target_objects <= 0
        else (
            f"\n- Spawn 1 to {target_objects} object(s) using ONLY these item_type values: {allowed_item_types}. "
            "Do NOT spawn a CONTAINER or SWITCH unless listed there, and at most 1 CONTAINER or SWITCH per scene."
        )
    )
    peaceful_rule = (
        "\n- PEACEFUL SCENE: Do NOT spawn hostile NPCs. Every NPC must have attitude 'friendly' or 'neutral' and combat_role 'none'."
        if effective_danger == "peaceful"
        else ""
    )
    speech_rule = (
        f"\n- NPC SPEECH RULE: Set npc_type to 'HUMANOID', 'BEING', 'ANIMAL', or 'MONSTER'. "
        f"Every HUMANOID or BEING NPC MUST speak normal, intelligible full sentences in {language} so the player can converse with them freely "
        f"(even if the main adventure features a mute, gesture-only, or fictional-dialect faction — make dynamic humanoids outsiders, travelers, or speakers who use plain {language}). "
        "Never give humanoid NPCs a dialogue_style of grunts, single syllables, or non-verbal sounds."
    )

    system_prompt = (
        "You are TaleWeaver's procedural location generator.\n"
        f"Generate ONE cohesive, self-contained scene matching the adventure tone, written strictly in {language}.\n"
        "STRICT LORE & QUEST ISOLATION RULES:\n"
        "- NEVER invent or spawn main-quest key items or break existing adventure puzzles.\n"
        "- NEVER spawn, duplicate, or kill named core story NPCs.\n"
        "- Keep visual_description and music_prompt in concise English (comma-separated visual/audio descriptors) even when narration text is in another language.\n"
        "- Keep entity IDs short uppercase alphanumeric slugs (e.g. RUSTY_PICKAXE, CAVE_SPIDER).\n"
        f"{npc_rule}{object_rule}{peaceful_rule}{speech_rule}"
    )
    user_prompt = (
        f"Adventure Title: {adventure_title}\n"
        f"Adventure Tone: {adventure_tone or 'Atmospheric'}\n"
        f"Setting Context: {adventure_setting[:500]}\n"
        f"Origin Scene: {origin_scene_name} — {origin_scene_description[:280]}\n"
        f"Traversed Passage: {exit_label}\n"
        f"Zone ID: {zone['zone_id']}\n"
        f"Zone Theme: {zone['theme']}\n"
        f"Danger Level: {effective_danger}\n"
        f"Max NPCs Cap: {max_npcs} (Rolled target: {target_npcs})\n"
        f"Allowed Entity Types: {allowed}\n"
        f"{depth_rule}"
    )
    return system_prompt, user_prompt


def _build_fallback_scene_payload(
    exit_label: str,
    zone: dict[str, Any],
) -> DynamicGeneratedScenePayload:
    """Deterministic atmospheric fallback when no LLM is configured or generation fails."""
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    clean_zone = re.sub(r"[_-]+", " ", str(zone.get("zone_id") or "uncharted")).title()
    passage_hint = exit_label.strip() or "a weathered passage"
    forward = (
        []
        if depth >= max_depth and cul_de_sac
        else [
            {
                "label": f"A deeper trail into {clean_zone}",
                "theme_hint": str(zone.get("theme") or clean_zone),
            }
        ]
    )
    return DynamicGeneratedScenePayload.model_validate(
        {
            "name": f"{clean_zone} (Depth {depth})",
            "description": (
                f"Beyond {passage_hint}, the air shifts as you enter an uncharted reach shaped by {zone['theme']}. "
                "Shadows cling to weathered surfaces, and every footstep echoes into the unknown."
            ),
            "visual_description": f"{zone['theme']}, moody atmospheric lighting, detailed environment",
            "music_prompt": f"Atmospheric ambient underscore for {zone['theme']}, subtle tension, seamless loop",
            "npcs": [],
            "objects": [],
            "forward_exits": forward,
        }
    )


async def generate_dynamic_scene_payload(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    origin_scene_description: str,
    exit_label: str,
    dynamic_zone: dict[str, Any],
    user: Any,
    db: AsyncSession,
    adventure_id: Optional[str] = None,
    game_id: Optional[str] = None,
    language: str = "English",
    max_npcs_default: int = 2,
) -> DynamicGeneratedScenePayload:
    """Generate a structured DynamicGeneratedScenePayload via LLM with deterministic fallback."""
    del db
    zone = normalize_dynamic_zone(dynamic_zone)
    if not zone:
        raise ValueError("Cannot generate a dynamic scene without a valid dynamic_zone config.")

    raw_danger = str(zone.get("danger_level") or "medium")
    effective_danger = (
        random.choice(_RANDOM_DANGER_CHOICES) if raw_danger == "random" else raw_danger
    )
    raw_max_npcs = dynamic_zone.get("max_npcs") if isinstance(dynamic_zone, dict) else None
    max_npcs = int(zone["max_npcs"] if raw_max_npcs is not None else max_npcs_default)
    max_npcs = max(0, min(5, max_npcs))

    llm_settings = dict(getattr(user, "llm_settings", None) or {})
    resolved = resolve_model_settings(llm_settings)
    provider = str(resolved["small_model_provider"])
    model = str(resolved["small_model"])

    if not _has_provider_credentials(user, provider):
        logger.info("No LLM credentials for provider %s; using fallback dynamic scene.", provider)
        return _build_fallback_scene_payload(exit_label, zone)

    scene_plan = _roll_scene_plan(zone, max_npcs)
    system_prompt, user_prompt = _build_scene_prompts(
        adventure_title=adventure_title,
        adventure_setting=adventure_setting,
        adventure_tone=adventure_tone,
        origin_scene_name=origin_scene_name,
        origin_scene_description=origin_scene_description,
        exit_label=exit_label,
        zone=zone,
        language=language or "English",
        effective_danger=effective_danger,
        max_npcs=max_npcs,
        scene_plan=scene_plan,
    )

    try:
        llm = GameMasterLLM(user, provider=provider, model_category="small")
        payload = await llm.aexecute_complex_task(
            system_prompt,
            user_prompt,
            DynamicGeneratedScenePayload,
            model,
            adventure_id=adventure_id,
            game_id=game_id,
            operation="dynamic_scene.generate",
            phase="expansion",
        )
        _apply_scene_plan_to_payload(payload, scene_plan)
        payload.npcs = payload.npcs[:max_npcs]
        if effective_danger == "peaceful":
            for npc in payload.npcs:
                npc.combat_role = "none"
                if npc.attitude == "hostile":
                    npc.attitude = "neutral"
        if int(zone["depth"]) >= int(zone["max_depth"]) and zone.get("cul_de_sac_on_max_depth"):
            payload.forward_exits = []
        return payload
    except Exception as exc:
        logger.warning("Dynamic scene generation failed (%s); using fallback scene.", exc)
        return _build_fallback_scene_payload(exit_label, zone)
