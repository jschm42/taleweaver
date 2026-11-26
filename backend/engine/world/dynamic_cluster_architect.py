"""LLM architect that plans a dynamic cluster as one small in-game adventure.

Called once when the player enters a dynamic cluster; the resulting blueprint gives
every room its own theme and generation instructions (see ``dynamic_cluster_node_zone``).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.api.routes.adventures.turn_context_helpers import resolve_model_settings
from backend.core.api_keys import has_api_key
from backend.core.llm_router import GameMasterLLM
from backend.engine.world.dynamic_cluster_blueprint import (
    DynamicClusterBlueprint,
    build_canonical_cluster_skeleton,
    build_fallback_cluster_blueprint,
    zone_root_theme,
)
from backend.engine.world.dynamic_cluster_node_zone import (
    describe_author_scope,
    root_instructions_scope,
    root_instructions_text,
)
from backend.engine.world.dynamic_required_entities import required_entities_summary
from backend.engine.world.dynamic_scene_schemas import (
    normalize_generation_model,
    resolve_effective_dynamic_rules,
)

logger = logging.getLogger(__name__)

_LOCAL_LLM_PROVIDERS = {"ollama", "lmstudio"}
_DYNAMIC_MODEL_CATEGORY_MAP: dict[str, tuple[str, str, str]] = {
    "mechanics": ("small_model_provider", "small_model", "small"),
    "narration": ("complex_model_provider", "complex_model", "complex"),
    "world_builder": ("generator_model_provider", "generator_model", "generator"),
}


def resolve_dynamic_llm_model(
    user: Any,
    zone: Optional[dict[str, Any]] = None,
    generation_config: Optional[dict[str, Any]] = None,
) -> tuple[str, str, str]:
    """Resolve (provider, model, category) for dynamic cluster and scene generation."""
    llm_settings = dict(getattr(user, "llm_settings", None) or {})
    resolved = resolve_model_settings(llm_settings)
    raw_choice = (zone or {}).get("generation_model") or (generation_config or {}).get(
        "generation_model"
    )
    tier = normalize_generation_model(raw_choice) or "mechanics"
    prov_key, model_key, category = _DYNAMIC_MODEL_CATEGORY_MAP[tier]
    return str(resolved[prov_key]), str(resolved[model_key]), category


def _build_architect_system_prompt(zone: dict[str, Any], language: str) -> str:
    """System prompt that plans the whole cluster like a small in-game adventure."""
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    skel_nodes, skel_edges = build_canonical_cluster_skeleton(max_depth, cul_de_sac)
    nodes_spec = ", ".join(f"{nid} (depth={d}, role={r})" for nid, d, r in skel_nodes)
    edges_spec = ", ".join(f"{src}->{dst}" for src, dst, _ in skel_edges) or "none"
    return (
        "You are TaleWeaver's mini-adventure cluster architect.\n"
        "The player just entered a procedurally generated area. Plan it NOW as one small, "
        "self-contained in-game adventure: every room is generated later from your plan, so "
        "the plan alone must carry the red thread from the first room to the last.\n"
        f"Write all text strictly in {language}.\n"
        "- NEVER reference or alter main-quest core story items or major main-plot NPCs.\n"
        f"- Populate EXACTLY these skeleton nodes using the exact node_id values: {nodes_spec}.\n"
        f"- Populate EXACTLY these edges (from_node_id -> to_node_id): {edges_spec}.\n"
        "- story_arc: hook, escalation and resolution of this mini-adventure. antagonist: the "
        "named main opponent or mystery met at the climax. key_item_concept: the named key item, "
        "which room holds it (and who carries it) and what it opens later.\n"
        "- Per node: label (room name), theme_hint (the room's OWN sub-theme: look, mood, hazards; "
        "a variation of the zone theme, never a copy of it), story_beat (what happens here and how "
        "it moves the arc on), npc_hint and object_hint (concrete, named).\n"
        "- Per node generation_instructions: 2-5 imperative sentences for the scene generator that "
        "builds this one room. Name the concrete NPCs/enemies (with attitude), items, containers, "
        "switches or puzzles to place here, which clue points to the next room, and where the key "
        "item is found or used. Keep names identical across rooms so the rooms reference each "
        "other consistently. Do not repeat the same instructions in every room.\n"
        "- CLUSTER PREMISE (if given) is what this mini-adventure is about: build cluster_title, "
        "story_arc, antagonist, key_item_concept, climax_goal and every room around it. The "
        "characters and goals it names (e.g. a prisoner to free, the captors, a relic) anchor the "
        "arc: earlier rooms foreshadow them, the climax room resolves them. Keep exact names, "
        "numbers and damage dice. Its spawn scope only limits where entities or loot it explicitly "
        "asks for are placed; the story itself always spans the whole cluster.\n"
        "- Respect the Spawn Chances: plan NPCs, enemies, loot, containers and switches in roughly "
        "that share of rooms (a switch at 15 appears in about one room in seven)."
    )


def _spawn_chance_text(zone: dict[str, Any], generation_config: Optional[dict[str, Any]]) -> str:
    _caps, chances = resolve_effective_dynamic_rules(zone, generation_config)
    keys = ("npc", "enemy", "item", "container", "switch")
    return ", ".join(f"{key} {chances[key]}" for key in keys)


def _build_architect_user_prompt(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    origin_scene_description: str,
    exit_label: str,
    zone: dict[str, Any],
    generation_config: Optional[dict[str, Any]] = None,
) -> str:
    """User prompt with the adventure frame, zone settings and author instructions."""
    instructions = root_instructions_text(zone)[:1500]
    scope_note = describe_author_scope(root_instructions_scope(zone))
    author_block = (
        f"\nCLUSTER PREMISE: {instructions}\n"
        f"(Spawn scope for entities or loot the premise explicitly requests: {scope_note}.)"
        if instructions
        else ""
    )
    placed = required_entities_summary(zone)
    if placed:
        author_block += f"\n{placed}"
    return (
        f"Adventure Title: {adventure_title}\n"
        f"Adventure Tone: {adventure_tone or 'Atmospheric'}\n"
        f"Setting Context: {adventure_setting[:450]}\n"
        f"Origin Scene: {origin_scene_name} — {origin_scene_description[:240]}\n"
        f"Entry Exit Label: {exit_label}\n"
        f"Zone Theme: {zone_root_theme(zone)}\n"
        f"Danger Level: {zone.get('danger_level') or 'medium'}\n"
        f"Max NPCs Per Scene: {zone.get('max_npcs', 2)}\n"
        f"Spawn Chances (percent of rooms): {_spawn_chance_text(zone, generation_config)}"
        f"{author_block}"
    )


async def generate_dynamic_cluster_blueprint(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    origin_scene_description: str,
    exit_label: str,
    zone: dict[str, Any],
    user: Any,
    adventure_id: Optional[str] = None,
    game_id: Optional[str] = None,
    language: str = "English",
    generation_config: Optional[dict[str, Any]] = None,
) -> DynamicClusterBlueprint:
    """Generate a cohesive mini-adventure blueprint for a dynamic cluster via LLM or fallback."""
    provider, model, model_category = resolve_dynamic_llm_model(user, zone, generation_config)

    has_creds = provider in _LOCAL_LLM_PROVIDERS or has_api_key(
        getattr(user, "encrypted_api_keys", None) or {},
        provider,
    )
    if not has_creds:
        return build_fallback_cluster_blueprint(exit_label, zone)

    system_prompt = _build_architect_system_prompt(zone, language)
    user_prompt = _build_architect_user_prompt(
        adventure_title=adventure_title,
        adventure_setting=adventure_setting,
        adventure_tone=adventure_tone,
        origin_scene_name=origin_scene_name,
        origin_scene_description=origin_scene_description,
        exit_label=exit_label,
        zone=zone,
        generation_config=generation_config,
    )
    try:
        llm = GameMasterLLM(user, provider=provider, model_category=model_category)
        return await llm.aexecute_complex_task(
            system_prompt,
            user_prompt,
            DynamicClusterBlueprint,
            model,
            adventure_id=adventure_id,
            game_id=game_id,
            operation="dynamic_cluster.blueprint",
            phase="expansion",
        )
    except Exception as exc:
        logger.warning("Cluster blueprint generation failed (%s); using fallback.", exc)
        return build_fallback_cluster_blueprint(exit_label, zone)
