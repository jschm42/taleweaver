"""Interlude quote selection and prompt helpers for dynamic scene transitions."""

from __future__ import annotations

import random
from typing import Any, Optional

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
    """Strip matching outer quotation marks around a generated quote."""
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
    """Build system and user prompts for dynamic scene interlude quotes."""
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
