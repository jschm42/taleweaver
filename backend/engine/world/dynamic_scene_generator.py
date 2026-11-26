"""Scoped LLM generators for procedural Dynamic Scenes and interlude quotes.

The room plan lives in ``dynamic_scene_plan``, the prompt in ``dynamic_scene_prompt`` and
the fallback room in ``dynamic_scene_fallback``.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.turn_context_helpers import resolve_model_settings
from backend.core.api_keys import has_api_key
from backend.core.llm_router import GameMasterLLM
from backend.engine.world.dynamic_cluster_architect import resolve_dynamic_llm_model
from backend.engine.world.dynamic_interlude_quote import (
    _build_interlude_prompts,
    _pick_interlude_npc,
    _strip_outer_quotes,
)
from backend.engine.world.dynamic_required_entities import cap_npcs
from backend.engine.world.dynamic_scene_fallback import (
    finalize_fallback_scene,
    sync_forward_exits_with_blueprint,
)
from backend.engine.world.dynamic_scene_plan import (
    apply_peaceful_filter,
    apply_scene_plan_to_payload,
    roll_scene_plan,
)
from backend.engine.world.dynamic_scene_prompt import build_scene_prompts
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedScenePayload,
    DynamicInterludeQuotePayload,
    normalize_dynamic_zone,
)

logger = logging.getLogger(__name__)

_LOCAL_LLM_PROVIDERS = {"ollama", "lmstudio"}
_RANDOM_DANGER_CHOICES: tuple[str, ...] = ("peaceful", "low", "medium", "high", "deadly")


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
    generation_config: Optional[dict[str, Any]] = None,
    cluster_context: Optional[list[dict[str, Any]]] = None,
    existing_scene_hint: Optional[dict[str, Any]] = None,
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

    provider, model, model_category = resolve_dynamic_llm_model(user, zone, generation_config)

    if not _has_provider_credentials(user, provider):
        logger.info("No LLM credentials for provider %s; using fallback dynamic scene.", provider)
        return finalize_fallback_scene(
            exit_label, zone, existing_scene_hint, cluster_context, backfill=True
        )

    scene_plan = roll_scene_plan(
        zone,
        max_npcs,
        effective_danger=effective_danger,
        generation_config=generation_config,
        cluster_context=cluster_context,
    )
    system_prompt, user_prompt = build_scene_prompts(
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
        cluster_context=cluster_context,
        existing_scene_hint=existing_scene_hint,
    )

    try:
        llm = GameMasterLLM(user, provider=provider, model_category=model_category)
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
        protected = apply_scene_plan_to_payload(payload, scene_plan, zone, cluster_context)
        payload.npcs = cap_npcs(payload.npcs, max_npcs, protected)
        if effective_danger == "peaceful":
            apply_peaceful_filter(payload.npcs)
        is_cul_de_sac = int(zone["depth"]) >= int(zone["max_depth"]) and zone.get(
            "cul_de_sac_on_max_depth"
        )
        if existing_scene_hint or is_cul_de_sac:
            payload.forward_exits = []
        else:
            sync_forward_exits_with_blueprint(payload, zone, existing_scene_hint)
        return payload
    except Exception as exc:
        logger.warning("Dynamic scene generation failed (%s); using fallback scene.", exc)
        return finalize_fallback_scene(exit_label, zone, existing_scene_hint, cluster_context)
