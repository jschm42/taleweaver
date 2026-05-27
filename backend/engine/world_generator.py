import asyncio
import json
import logging
import os
import shutil
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import prompts
from backend.core.config import settings
from backend.core.llm_logger import log_structured_event
from backend.core.llm_router import GameMasterLLM
from backend.core.style_catalog import resolve_style_instruction
from backend.core.tts_voices import GOOGLE_TTS_VOICE_NAMES
from backend.models.adventure_template import AdventureTemplate, GenerationCancelled
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.utils.text_utils import slugify

logger = logging.getLogger(__name__)

IMAGE_MODERATION_MARKERS = (
    "safety filter",
    "content moderated",
    "moderated",
    "content policy",
    "policy violation",
    "blocked by safety",
    "responsible ai",
    "prompt blocked",
)


def is_image_moderation_error(error: Union[Exception, str, None]) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return any(marker in message for marker in IMAGE_MODERATION_MARKERS)


def _build_voice_assignment_requirement(
    enabled: bool,
    available_voice_list: Optional[list[str]] = None,
) -> str:
    return ""


def _image_generation_timeout_seconds() -> float:
    raw_timeout = getattr(settings, "IMAGE_GENERATION_TIMEOUT_SECONDS", 600)
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError):
        timeout = 120.0
    return max(10.0, timeout)


def _validate_t2i_prerequisites(
    user: Optional[User],
    *,
    need_scene_images: bool,
    need_npc_images: bool,
    need_item_images: bool,
    need_protagonist_image: bool,
) -> None:
    if not user:
        return

    needs_any_images = need_scene_images or need_npc_images or need_item_images or need_protagonist_image
    if not needs_any_images:
        return

    t2i_settings = user.t2i_settings or {}
    if not t2i_settings:
        raise ValueError(
            "Image generation is enabled, but no image settings are configured. "
            "Open Settings and configure Text-to-Image provider and models."
        )

    # Note: We don't check for a global 'provider' anymore as each model path can have its own.
    # However, we'll validate the specific ones needed.

    if need_scene_images:
        model = (t2i_settings.get("advanced_model") or "").strip()
        if not model:
            raise ValueError("Image generation is enabled for scenes, but advanced_model is missing.")
        provider = (t2i_settings.get("advanced_model_provider") or t2i_settings.get("provider", "openai")).lower()
        if provider not in ("ollama", "stable_diffusion"):
            # Check environment and then DB
            if not settings.get_env_api_key(provider):
                encrypted_api_keys = user.encrypted_api_keys or {}
                if provider not in encrypted_api_keys:
                    raise ValueError(f"API key missing for advanced image provider '{provider}'.")

    if need_npc_images or need_item_images or need_protagonist_image:
        model = (t2i_settings.get("simple_model") or "").strip()
        if not model:
            raise ValueError("Image generation is enabled for portraits/items, but simple_model is missing.")
        provider = (t2i_settings.get("simple_model_provider") or t2i_settings.get("provider", "openai")).lower()
        if provider not in ("ollama", "stable_diffusion"):
            # Check environment and then DB
            if not settings.get_env_api_key(provider):
                encrypted_api_keys = user.encrypted_api_keys or {}
                if provider not in encrypted_api_keys:
                    raise ValueError(f"API key missing for simple image provider '{provider}'.")


async def _publish_generation_status(db: AsyncSession, adventure: Optional[AdventureTemplate], status: str) -> None:
    """Publish live status text via the active session without committing mid-generation."""
    if not adventure:
        return
        
    # Check for cancellation before updating status
    await db.refresh(adventure)
    if adventure.creation_status == "Cancelled":
        raise GenerationCancelled("Generation was cancelled by the user.")
        
    adventure.creation_status = status  # type: ignore
    await db.flush()


async def _publish_generation_status_with_callback(
    db: AsyncSession,
    adventure: Optional[AdventureTemplate],
    status: str,
    status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
) -> None:
    """Persist generation status and optionally forward it to an external observer (e.g., in-game chat)."""
    await _publish_generation_status(db, adventure, status)
    if status_callback:
        try:
            await status_callback(status)
        except Exception as exc:
            logger.warning("Generation status callback failed for %s: %s", status, exc)


def _uses_ollama_t2i(user: Optional[User]) -> bool:
    if not user:
        return False
    t2i_settings = user.t2i_settings or {}
    return (t2i_settings.get("provider") or "").lower() == "ollama"


def _normalize_text_log_content(
    raw_content: Any,
    description_fallback: Any = "",
    name_fallback: Any = "",
) -> str:
    """Normalize readable text while preserving paragraph breaks and enforcing length."""
    content = str(raw_content or "")
    if not content.strip():
        content = str(description_fallback or "")

    # Keep paragraph formatting stable across platforms and trim trailing spaces.
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    normalized_lines = [line.rstrip() for line in content.split("\n")]
    normalized = "\n".join(normalized_lines).strip()
    if not normalized:
        safe_name = str(name_fallback or "This note").strip() or "This note"
        normalized = f"{safe_name} contains faded but readable notes."
    return normalized[:500]


def _normalize_container_unlock_requirements(
    raw_code: Any,
    raw_item: Any,
) -> tuple[str, str]:
    """Normalize container unlock requirement fields without forcing locks."""
    code_to_unlock = str(raw_code or "").strip()
    item_to_unlock = str(raw_item or "").strip().upper()

    if code_to_unlock:
        code_to_unlock = code_to_unlock[:32]
    if item_to_unlock:
        item_to_unlock = slugify(item_to_unlock).upper().replace("-", "_")[:64]

    return code_to_unlock, item_to_unlock


# --- Schemas for Structured LLM Output ---

class WorldSceneSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the scene, e.g., CASTLE_GATES")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Atmospheric and detailed description of the location.")
    source_asset_id: Optional[str] = Field(None, description="Optional source scene ID to reuse an old cover asset image.")
    
    model_config = {"extra": "forbid"}

class WorldExitSchema(BaseModel):
    from_scene_id: str = Field(..., description="The ID of the source scene.")
    to_scene_id: str = Field(..., description="The ID of the destination scene.")
    label: str = Field(..., description="How to describe the transition, e.g., 'a narrow stone staircase'")
    is_locked: bool = Field(..., description="Whether the path is initially blocked.")
    lock_description: str = Field(..., description="If locked, why? e.g. 'a heavy iron padlock'. Use empty string if not locked.")
    
    model_config = {"extra": "forbid"}

class WorldNPCSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the NPC, e.g., MAD_ALCHEMIST")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Appearance and demeanor or physical characteristics, max 400 characters.")
    goal: str = Field(..., description="Concise description of the NPC's primary motivation or intention, max 200 characters.")
    character: str = Field(..., description="Concise description of the NPC's personality, demeanor, or character traits, max 200 characters.")
    start_scene_id: str = Field(..., description="The ID of the scene where the NPC starts.")
    spatial_position: str = Field(..., description="Precise micro-location in the scene, e.g., 'sitting in the armchair', 'hidden in a drawer'")
    
    npc_type: str = Field(..., description="One of: HUMANOID, ANIMAL, MONSTER, BEING")
    movement_type: str = Field(..., description="One of: STATIONARY, MOVABLE")
    hp: int = Field(..., description="Hitpoints (range 10-100)")
    mana: int = Field(..., description="Mana (range 0-999)")
    stamina: int = Field(..., description="Stamina (range 50-100)")
    is_attackable: bool = Field(..., description="If False, the player cannot start a fight with this NPC.")
    is_killable: bool = Field(..., description="If False, this NPC can be defeated but cannot be permanently killed.")
    is_hidden: bool = Field(..., description="If True, the NPC is initially concealed.")
    source_asset_id: Optional[str] = Field(None, description="Optional source NPC ID to reuse an old portrait image.")
    reveal_rule: str = Field(
        ...,
        description=(
            "If is_hidden=True: the condition that reveals this NPC. "
            "E.g. 'If the prot searches under the table', 'If the prot picks up BRASS_KEY', or 'If the NPC speaks'. "
            "Use empty string if not hidden."
        )
    )
    inventory: list[str] = Field(..., description="List of object IDs in this NPC's inventory. Use [] if empty.")
    
    model_config = {"extra": "forbid"}

class WorldObjectSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the object, e.g., GOLDEN_KEY")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Physical characteristics and details.")
    start_scene_id: str = Field(..., description="The ID of the scene where the object starts.")
    spatial_position: str = Field(..., description="Precise micro-location in the scene, e.g., 'on the dusty shelf', 'under the rug'")
    
    item_type: str = Field(..., description="One of: CONSUMABLE, WEARABLE, STATIC, COMBINABLE, PICKABLE, WEAPON, TOOL, KEY, READABLE, CONTAINER")
    wearable_slots: list[str] = Field(..., description="If WEARABLE, which slots? e.g. ['Head'], ['MainHand']. Use [] if none.")
    is_hidden: bool = Field(..., description="If True, the player must SEARCH or trigger an event to see this.")
    reveal_rule: str = Field(
        ...,
        description=(
            "If is_hidden=True: the condition that reveals this object. "
            "E.g. 'If the prot searches the desk', 'If the prot picks up IRON_KEY'. "
            "Use empty string if not hidden."
        )
    )
    is_portable: bool = Field(..., description="Whether the item can be picked up. False for STATIC objects.")
    code_to_unlock: str = Field("", description="Deterministic access code for locked containers, e.g. ALPHA or 4711. May be empty for open containers.")
    item_to_unlock: str = Field("", description="Deterministic item ID required to unlock this container. May be empty for open containers.")
    combination_ingredients: list[str] = Field(..., description="Item IDs required to trigger a combination. Use [] if none.")
    reveals_item_id: str = Field(..., description="Item slug revealed when combination occurs. Use empty string if none.")
    
    # Stat Modifiers
    stat_modifier_strength: int = Field(..., description="Strength bonus. Use 0 if none.")
    stat_modifier_dexterity: int = Field(..., description="Dexterity bonus. Use 0 if none.")
    stat_modifier_intelligence: int = Field(..., description="Intelligence bonus. Use 0 if none.")
    stat_modifier_wisdom: int = Field(..., description="Wisdom bonus. Use 0 if none.")
    stat_modifier_charisma: int = Field(..., description="Charisma bonus. Use 0 if none.")
    stat_modifier_armor_class: int = Field(..., description="Armor class bonus. Use 0 if none.")
    hp_change: int = Field(..., description="HP restoration or damage when consumed. Use 0 if none.")
    stamina_change: int = Field(..., description="Stamina restoration when consumed. Use 0 if none.")
    mana_change: int = Field(..., description="Mana restoration when consumed. Use 0 if none.")
    
    inventory: list[str] = Field(..., description="List of object IDs inside this container object. Use [] if empty.")
    text_log_content: str = Field("", description="Only for READABLE objects: visible text content, max 500 characters. Must be non-empty for READABLE objects. Paragraphs are allowed (use blank lines). Use empty string for non-readable items.")
    text_log_format: str = Field("", description="Only for READABLE objects: one of DOCUMENT, SCROLL, BOOK, SIGN. Use empty string for non-readable items.")
    source_asset_id: Optional[str] = Field(None, description="Optional source object ID to reuse an old item image.")
    
    model_config = {"extra": "forbid"}

class QuestSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the quest, e.g., FIND_GOLDEN_KEY")
    title: str = Field(..., description="Short, descriptive title")
    description: str = Field(..., description="Narrative description of what needs to be done")
    goal: str = Field(..., description="Technical condition for completion (for GM reference)")
    impact: str = Field(..., description="How this affects the world when completed. Use empty string for standard quests.")
    exp_reward: int = Field(..., description="EXP awarded for completion (e.g., 50, 100, 250)")
    is_main: bool = Field(..., description="True if this quest is required to finish the adventure")
    status: str = Field(..., description="Current state: open, completed, failed")
    
    model_config = {"extra": "forbid"}

class AwardTemplateSchema(BaseModel):
    key: str = Field(..., description="Unique identifier for the award, e.g., SLAYER_OF_RATS")
    title: str = Field(..., description="Visual name of the award")
    description: str = Field(..., description="Short description shown to the player")
    tier: Literal["bronze", "silver", "gold"] = Field(..., description="The rarity/tier of the award: bronze, silver, or gold")
    requirement: str = Field(..., description="The specific rule/condition when the GM should grant this award")
    
    model_config = {"extra": "forbid"}

class EquipmentSchema(BaseModel):
    Head: str = Field(..., description="Item ID for head slot or empty string")
    Chest: str = Field(..., description="Item ID for chest slot or empty string")
    Hands: str = Field(..., description="Item ID for hands slot or empty string")
    Legs: str = Field(..., description="Item ID for legs slot or empty string")
    Feet: str = Field(..., description="Item ID for feet slot or empty string")
    Neck: str = Field(..., description="Item ID for neck slot or empty string")
    Ring_1: str = Field(..., description="Item ID for ring 1 slot or empty string")
    Ring_2: str = Field(..., description="Item ID for ring 2 slot or empty string")
    MainHand: str = Field(..., description="Item ID for main hand slot or empty string")
    OffHand: str = Field(..., description="Item ID for off hand slot or empty string")
    
    model_config = {"extra": "forbid"}

class ProtagonistSchema(BaseModel):
    name: str = Field(..., description="The name of the player character.")
    role: str = Field(..., description="The professional or narrative role of the player.")
    description: str = Field(..., description="Narrative description of appearance and backstory.")
    goal: str = Field(..., description="The protagonist's primary motivation or personal driving goal, max 200 characters.")
    character: str = Field(..., description="Concise description of the protagonist's personality, quirks, and character traits, max 200 characters.")
    strength: int = Field(..., description="Base strength stat (1-99)")
    dexterity: int = Field(..., description="Base dexterity stat (1-99)")
    intelligence: int = Field(..., description="Base intelligence stat (1-99)")
    wisdom: int = Field(..., description="Base wisdom stat (1-99)")
    charisma: int = Field(..., description="Base charisma stat (1-99)")
    armor_class: int = Field(..., description="Base armor class stat (1-99)")
    starting_inventory: list[str] = Field(..., description="List of object IDs in player's pocket. Use [] if none.")
    starting_equipment: EquipmentSchema = Field(..., description="Initial equipment setup.")
    hp: int = Field(..., description="Base health points (60-120)")
    mana: int = Field(..., description="Base mana points (0-300)")
    stamina: int = Field(..., description="Base stamina points (60-100)")
    source_asset_id: Optional[str] = Field(None, description="Optional source protagonist ID to reuse an old portrait image.")
    
    model_config = {"extra": "forbid"}

class WorldManifesto(BaseModel):
    """
    The complete blueprint of the generated world.
    """
    protagonist: ProtagonistSchema
    teaser: str = Field(..., description="A short, atmospheric teaser text for the adventure, max 100 characters.")
    language: str = Field(..., description="The target language for all generated content, e.g. 'English'.")
    origin_id: str = Field(..., description="Stable ID for the adventure. Use empty string if not provided.")
    plot: str = Field(..., description="The main plotline, goals, and narrative arc of the adventure.")
    rules: str = Field(..., description="Special rules or mechanics specific to this adventure world.")
    intro_text: str = Field(..., description="Optional intro text shown once when a new session starts. Use empty string if none.")
    walkthrough: str = Field(..., description="A secret GM walkthrough/solution for the adventure.")
    completed_condition: str = Field(..., description="Technical or narrative condition for winning the adventure.")
    gameover_condition: str = Field(..., description="Technical or narrative condition for losing the adventure.")
    tts_director_notes: str = Field(..., description="Style instructions for the Text-to-Speech engine (tone, pacing, emphasis).")
    can_damage_npcs: bool = Field(True, description="Global flag: whether the protagonist can damage NPCs.")
    npcs_can_damage_protagonist: bool = Field(True, description="Global flag: whether NPCs can damage the protagonist.")
    scenes: list[WorldSceneSchema]
    exits: list[WorldExitSchema]
    npcs: list[WorldNPCSchema]
    objects: list[WorldObjectSchema]
    quests: list[QuestSchema] = Field(..., description="List of 3-5 quests. Use [] if none.")
    awards: list[AwardTemplateSchema] = Field(..., description="List of 3-5 awards. Use [] if none.")
    cover_source_adventure_id: Optional[str] = None
    cover_source_adventure_name: Optional[str] = None
    cover_similarity_percent: int = 50
    allow_reuse_source_assets: bool = True
    cover_source_asset_id: Optional[str] = None
    
    model_config = {"extra": "forbid"}

class WorldGenerator:
    @staticmethod
    async def generate_world(
        db: AsyncSession, 
        user: User, 
        template_id: str, 
        title: str, 
        original_prompt: str,
        model: Optional[str] = None, # Resolve from user settings if not provided
        provider: Optional[str] = None,
        generate_scene_images: bool = False,
        generate_npc_images: bool = False,
        generate_item_images: bool = False,
        automatic_npc_voice_assignment: bool = True,
        min_scenes: Optional[int] = None,
        max_scenes: Optional[int] = None,
        container_generation_enabled: bool = True,
        min_containers: Optional[int] = None,
        max_containers: Optional[int] = None,
        text_log_generation_enabled: bool = True,
        min_text_logs: Optional[int] = None,
        max_text_logs: Optional[int] = None,
        quest_generation_enabled: bool = True,
        min_quests: Optional[int] = None,
        max_quests: Optional[int] = None,
        min_items: Optional[int] = None,
        max_items: Optional[int] = None,
        award_generation_enabled: bool = True,
        min_awards: Optional[int] = None,
        max_awards: Optional[int] = None,
        can_damage_npcs: bool = True,
        npcs_can_damage_protagonist: bool = True,
        selected_image_styles: Optional[list[str]] = None,
        selected_tone: Optional[str] = None,
        language: Optional[str] = None,
        cover_source_manifest: Optional[dict[str, Any]] = None,
        cover_source_adventure_id: Optional[str] = None,
        cover_source_adventure_name: Optional[str] = None,
        cover_similarity_percent: int = 50,
        allow_reuse_source_assets: bool = True,
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None,

    ) -> None:
        """
        Calls the complex LLM to generate a coherent world structure based on the adventure theme.
        Persists the result to the WorldScene, WorldExit, and WorldEntity tables.
        """
        # If no provider is given, use the one from user settings
        llm_settings = user.llm_settings or {}
        if not provider:
            provider = (
                llm_settings.get("generator_model_provider")
                or llm_settings.get("complex_model_provider")
                or llm_settings.get("small_model_provider")
                or llm_settings.get("preferred_provider")
            )
        
        if not model:
            model = (
                llm_settings.get("generator_model") 
                or llm_settings.get("complex_model") 
                or llm_settings.get("small_model") 
                or "gpt-4o"
            )

        tts_settings = user.tts_settings or {}
        available_voice_list = tts_settings.get("voice_list") if isinstance(tts_settings, dict) else None

        if not provider:
            raise ValueError(
                "No adventure generator LLM provider configured for this user. "
                "Open Settings -> Intelligence and set Generator Model Provider."
            )

        llm = GameMasterLLM(user, provider=provider, model_category="generator")

        log_structured_event(
            "adventure.generation.start",
            template_id=template_id,
            title=title,
            provider=provider,
            model=model,
            generate_scene_images=generate_scene_images,
            generate_npc_images=generate_npc_images,
            generate_item_images=generate_item_images,
            context_length=len(original_prompt or ""),
            has_cover_source=bool(cover_source_adventure_id),
            cover_similarity_percent=max(0, min(100, int(cover_similarity_percent or 0))),
            allow_reuse_source_assets=bool(allow_reuse_source_assets),
        )
        
        system_prompt = prompts.WORLD_GENERATION_SYSTEM_PROMPT
        if language:
            system_prompt += f"\n\nCRITICAL: You MUST generate all content (names, descriptions, teaser, plot, intro_text, walkthrough, quests) in {language}. Do not use any other language."

        if not quest_generation_enabled:
            system_prompt += "\n\nQUEST GENERATION OVERRIDE: Do not generate any quests for this adventure."

        # Scene requirement
        if min_scenes is None and max_scenes is None:
            scene_requirement = "- Generate a suitable number of unique scenes (typically between 3 and 10) based on the story complexity."
        elif min_scenes is not None and max_scenes is None:
            scene_requirement = f"- Generate at least {max(1, min_scenes)} unique scenes."
        elif min_scenes is None and max_scenes is not None:
            scene_requirement = f"- Generate no more than {max(1, max_scenes)} unique scenes."
        else:
            scene_requirement = f"- Generate between {max(1, min_scenes)} and {max(1, max_scenes)} unique scenes."

        quest_requirement = ""
        if quest_generation_enabled:
            if min_quests is None and max_quests is None:
                quest_requirement = "\n- Generate a suitable number of total quests (typically between 2 and 6) that fit the narrative context. Mix main and side quests naturally."
            elif min_quests is not None and max_quests is None:
                quest_requirement = f"\n- Generate at least {max(1, min_quests)} total quests. Mix main and side quests naturally."
            elif min_quests is None and max_quests is not None:
                quest_requirement = f"\n- Generate no more than {max(1, max_quests)} total quests. Mix main and side quests naturally."
            else:
                clamped_min_quests = max(1, min(30, int(min_quests)))
                clamped_max_quests = max(clamped_min_quests, min(30, int(max_quests)))
                quest_requirement = (
                    f"\n- Generate between {clamped_min_quests} and {clamped_max_quests} total quests that fit the narrative context."
                    " Mix main and side quests naturally."
                )
        else:
            quest_requirement = "\n- Do not generate any quests for this adventure."
        
        award_requirement = ""
        if award_generation_enabled:
            if min_awards is None and max_awards is None:
                award_requirement = "\n\nAWARD SYSTEM:\n- Generate a suitable number of unique Awards (typically between 3 and 8) that players can earn."
            elif min_awards is not None and max_awards is None:
                award_requirement = f"\n\nAWARD SYSTEM:\n- Generate at least {max(1, min_awards)} unique Awards that players can earn."
            elif min_awards is None and max_awards is not None:
                award_requirement = f"\n\nAWARD SYSTEM:\n- Generate no more than {max(1, max_awards)} unique Awards that players can earn."
            else:
                clamped_min_awards = max(1, min(30, int(min_awards)))
                clamped_max_awards = max(clamped_min_awards, min(30, int(max_awards)))
                award_requirement = f"\n\nAWARD SYSTEM:\n- Generate between {clamped_min_awards} and {clamped_max_awards} unique Awards that players can earn."
        else:
            award_requirement = "\n\nAWARD SYSTEM:\n- Do not generate any awards for this adventure."

        # Container requirement
        if not container_generation_enabled:
            container_requirement = (
                "\n\nCONTAINER ITEMS:\n"
                "- Do not generate any objects with item_type CONTAINER."
            )
        else:
            if min_containers is None and max_containers is None:
                container_requirement = (
                    "\n\nCONTAINER ITEMS:\n"
                    "- Generate a suitable number of container items (typically between 2 and 6) if the scenes require them.\n"
                    "- CONTAINER objects may be open or locked depending on story needs.\n"
                    "- Use lock mechanics frequently for containers that imply security/value (e.g. safe, strongbox, lockbox, vault, sealed crate, lootbox with lock).\n"
                    "- For locked containers, provide deterministic `code_to_unlock` and/or `item_to_unlock`; for open containers, keep both empty.\n"
                    "- Every locked container must have at least one discoverable hint or riddle somewhere in scenes, readables, NPC dialogue context, or object descriptions that points to the unlock method."
                )
            elif min_containers is not None and max_containers is None:
                container_requirement = (
                    "\n\nCONTAINER ITEMS:\n"
                    f"- Generate at least {max(0, min_containers)} container items.\n"
                    "- CONTAINER objects may be open or locked depending on story needs.\n"
                    "- Use lock mechanics frequently for containers that imply security/value (e.g. safe, strongbox, lockbox, vault, sealed crate, lootbox with lock).\n"
                    "- For locked containers, provide deterministic `code_to_unlock` and/or `item_to_unlock`; for open containers, keep both empty.\n"
                    "- Every locked container must have at least one discoverable hint or riddle somewhere in scenes, readables, NPC dialogue context, or object descriptions that points to the unlock method."
                )
            elif min_containers is None and max_containers is not None:
                container_requirement = (
                    "\n\nCONTAINER ITEMS:\n"
                    f"- You may generate CONTAINER objects, but never more than {max(0, max_containers)}.\n"
                    "- CONTAINER objects may be open or locked depending on story needs.\n"
                    "- Use lock mechanics frequently for containers that imply security/value (e.g. safe, strongbox, lockbox, vault, sealed crate, lootbox with lock).\n"
                    "- For locked containers, provide deterministic `code_to_unlock` and/or `item_to_unlock`; for open containers, keep both empty.\n"
                    "- Every locked container must have at least one discoverable hint or riddle somewhere in scenes, readables, NPC dialogue context, or object descriptions that points to the unlock method."
                )
            else:
                container_requirement = (
                    "\n\nCONTAINER ITEMS:\n"
                    f"- Generate between {max(0, min_containers)} and {max(0, max_containers)} container items.\n"
                    "- CONTAINER objects may be open or locked depending on story needs.\n"
                    "- Use lock mechanics frequently for containers that imply security/value (e.g. safe, strongbox, lockbox, vault, sealed crate, lootbox with lock).\n"
                    "- For locked containers, provide deterministic `code_to_unlock` and/or `item_to_unlock`; for open containers, keep both empty.\n"
                    "- Every locked container must have at least one discoverable hint or riddle somewhere in scenes, readables, NPC dialogue context, or object descriptions that points to the unlock method."
                )

        # Text log requirement
        if not text_log_generation_enabled:
            text_log_requirement = (
                "\n\nTEXT LOGS (READABLE OBJECTS):\n"
                "- Do not generate any READABLE objects."
            )
        else:
            base_text_log_instruction = (
                "- For every READABLE object, provide `text_log_content` with at most 500 characters and `text_log_format` as DOCUMENT, SCROLL, BOOK, or SIGN.\n"
                "- `text_log_content` for READABLE objects MUST be non-empty (never \"\" and never omitted).\n"
                "- Keep text_log_content practical: hints, story fragments, warnings, clues. Paragraph formatting is allowed; use blank lines between paragraphs when useful."
            )
            if min_text_logs is None and max_text_logs is None:
                text_log_requirement = (
                    "\n\nTEXT LOGS (READABLE OBJECTS):\n"
                    "- Generate a suitable number of readable text logs (typically between 1 and 5) containing clues or lore.\n"
                    f"{base_text_log_instruction}"
                )
            elif min_text_logs is not None and max_text_logs is None:
                text_log_requirement = (
                    "\n\nTEXT LOGS (READABLE OBJECTS):\n"
                    f"- Generate at least {max(0, min_text_logs)} readable text logs.\n"
                    f"{base_text_log_instruction}"
                )
            elif min_text_logs is None and max_text_logs is not None:
                text_log_requirement = (
                    "\n\nTEXT LOGS (READABLE OBJECTS):\n"
                    f"- You may generate READABLE objects, but never more than {max(0, max_text_logs)}.\n"
                    f"{base_text_log_instruction}"
                )
            else:
                text_log_requirement = (
                    "\n\nTEXT LOGS (READABLE OBJECTS):\n"
                    f"- Generate between {max(0, min_text_logs)} and {max(0, max_text_logs)} readable text logs.\n"
                    f"{base_text_log_instruction}"
                )

        # Item requirement
        if min_items is None and max_items is None:
            item_requirement = (
                "\n\nITEM COUNT LIMIT:\n"
                "- Generate a suitable number of total objects/items in `objects` (typically between 5 and 25) that fit the scenes."
            )
        elif min_items is not None and max_items is None:
            item_requirement = (
                "\n\nITEM COUNT LIMIT:\n"
                f"- Generate at least {max(1, min_items)} total objects/items in `objects`."
            )
        elif min_items is None and max_items is not None:
            item_requirement = (
                "\n\nITEM COUNT LIMIT:\n"
                f"- Generate no more than {max(1, max_items)} total objects/items in `objects`."
            )
        else:
            item_requirement = (
                "\n\nITEM COUNT LIMIT:\n"
                f"- Generate between {max(1, min_items)} and {max(1, max_items)} total objects/items in `objects`."
            )

        cover_guidance = ""
        if cover_source_manifest:
            source_title = cover_source_adventure_name or cover_source_manifest.get("title") or "Unknown Source Adventure"
            source_description = (
                cover_source_manifest.get("teaser")
                or cover_source_manifest.get("original_prompt")
                or cover_source_manifest.get("plot")
                or ""
            )
            similarity = max(0, min(100, int(cover_similarity_percent or 0)))
            source_scene_ids = [
                s.get("id")
                for s in (cover_source_manifest.get("scenes") or [])
                if isinstance(s, dict) and s.get("id")
            ][:12]
            source_npc_ids = [
                n.get("id")
                for n in (cover_source_manifest.get("npcs") or [])
                if isinstance(n, dict) and n.get("id")
            ][:12]
            source_object_ids = [
                o.get("id")
                for o in (cover_source_manifest.get("objects") or [])
                if isinstance(o, dict) and o.get("id")
            ][:24]
            cover_guidance = (
                "\n\nCOVER MODE:\n"
                f"- Create this as a cover of '{source_title}'.\n"
                f"- Requested similarity: {similarity}% (0 = freely inspired, 100 = very close).\n"
                f"- Source summary: {source_description[:800]}\n"
                f"- Old asset reuse allowed: {'yes' if allow_reuse_source_assets else 'no'}.\n"
                "- Use the source IDs below to preserve motifs and mapping where useful.\n"
                "- If you intentionally want to reuse old visual assets, set `source_asset_id` on protagonist/scenes/npcs/objects entries to the chosen source IDs.\n"
                "- If you want to reuse the old cover image, set `cover_source_asset_id` to `COVER`.\n"
                f"- Source scene IDs (sample): {source_scene_ids}\n"
                f"- Source NPC IDs (sample): {source_npc_ids}\n"
                f"- Source object IDs (sample): {source_object_ids}\n"
            )

        user_prompt = prompts.WORLD_GENERATION_USER_PROMPT_TEMPLATE.format(
            title=title, 
            original_prompt=original_prompt, 
            selected_tone=selected_tone or "Standard RPG",
            scene_requirement=scene_requirement,
            can_damage_npcs="true" if can_damage_npcs else "false",
            npcs_can_damage_protagonist="true" if npcs_can_damage_protagonist else "false",
            voice_assignment_requirement=_build_voice_assignment_requirement(
                automatic_npc_voice_assignment,
                available_voice_list,
            ),
            cover_guidance=cover_guidance,
            quest_requirement=quest_requirement,
            award_requirement=award_requirement,
            text_log_requirement=text_log_requirement,
        )
        user_prompt += container_requirement
        user_prompt += item_requirement

        
        # 1. Update Status
        adventure = await db.get(AdventureTemplate, template_id)
        if adventure:
            await _publish_generation_status_with_callback(
                db,
                adventure,
                "Analyzing Story Idea...",
                status_callback=status_callback,
            )
            log_structured_event(
                "adventure.generation.status",
                template_id=template_id,
                status=adventure.creation_status,
                phase="analysis",
            )
            await db.commit()

        manifesto: WorldManifesto = await llm.aexecute_complex_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=WorldManifesto,
            model=model,
            adventure_id=template_id,
            operation="generate_world",
            phase="analysis",
            metadata={
                "generate_scene_images": generate_scene_images,
                "generate_npc_images": generate_npc_images,
                "generate_item_images": generate_item_images,
                "automatic_npc_voice_assignment": automatic_npc_voice_assignment,
                "min_scenes": min_scenes,
                "max_scenes": max_scenes,
                "min_items": min_items,
                "max_items": max_items,
                "container_generation_enabled": container_generation_enabled,
                "min_containers": min_containers,
                "max_containers": max_containers,
                "text_log_generation_enabled": text_log_generation_enabled,
                "min_text_logs": min_text_logs,
                "max_text_logs": max_text_logs,
                "quest_generation_enabled": quest_generation_enabled,
                "min_quests": min_quests,
                "max_quests": max_quests,
            },
        )

        log_structured_event(
            "adventure.generation.manifest_received",
            template_id=template_id,
            scene_count=len(manifesto.scenes),
            exit_count=len(manifesto.exits),
            npc_count=len(manifesto.npcs),
            object_count=len(manifesto.objects),
        )
        
        # 2. Update Status
        if adventure:
            await db.refresh(adventure)
            await _publish_generation_status_with_callback(
                db,
                adventure,
                "Building Scenes & Plot...",
                status_callback=status_callback,
            )
            log_structured_event(
                "adventure.generation.status",
                template_id=template_id,
                status=adventure.creation_status,
                phase="apply_manifest",
            )
            if adventure:
                # Keep imported/source manifest intact for reproducible resets.
                adventure.teaser = manifesto.teaser  # type: ignore
                adventure.original_prompt = original_prompt  # type: ignore
                if language:
                    adventure.language = language  # type: ignore
                if not adventure.origin_id:
                    adventure.origin_id = manifesto.origin_id or template_id  # type: ignore
                if not adventure.original_manifest:
                    adventure.original_manifest = manifesto.model_dump()  # type: ignore
            await db.commit()
            
        cover_source_assets = None
        if allow_reuse_source_assets and cover_source_adventure_id:
            from backend.models.avatar import Avatar

            src_adv = await db.get(AdventureTemplate, cover_source_adventure_id)
            if src_adv:
                src_avatar_res = await db.execute(select(Avatar).where(Avatar.template_id == cover_source_adventure_id))
                src_avatar = src_avatar_res.scalars().first()

                src_scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == cover_source_adventure_id))
                src_scenes = src_scene_res.scalars().all()

                src_entity_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == cover_source_adventure_id))
                src_entities = src_entity_res.scalars().all()
                src_scenes = [scene for scene in src_scenes if getattr(scene, "session_id", None) is None]
                src_entities = [ent for ent in src_entities if getattr(ent, "session_id", None) is None]

                cover_source_assets = {
                    "cover": src_adv.image_url,
                    "protagonist": {
                        "id": "PROTAGONIST",
                        "name": (src_avatar.name if src_avatar else ""),
                        "image_url": (src_avatar.profile_image if src_avatar else None),
                    },
                    "scenes": [
                        {"id": scene.id, "name": scene.label, "image_url": scene.image_url}
                        for scene in src_scenes
                    ],
                    "npcs": [
                        {"id": ent.id, "name": ent.name, "image_url": ent.image_url}
                        for ent in src_entities
                        if ent.entity_type == "NPC"
                    ],
                    "objects": [
                        {"id": ent.id, "name": ent.name, "image_url": ent.image_url}
                        for ent in src_entities
                        if ent.entity_type == "OBJECT"
                    ],
                }

        manifest_dict = manifesto.model_dump()

        # Post-processing clamp limits for Auto Mode vs Manual constraints
        clamped_max_containers = max(0, min(30, int(max_containers))) if max_containers is not None else 9999
        clamped_max_text_logs = max(0, min(30, int(max_text_logs))) if max_text_logs is not None else 9999

        objects = manifest_dict.get("objects") or []
        container_indices = [
            idx for idx, obj in enumerate(objects)
            if isinstance(obj, dict) and str(obj.get("item_type", "")).upper() == "CONTAINER"
        ]
        if not container_generation_enabled:
            for idx in container_indices:
                obj = objects[idx]
                obj["item_type"] = "PICKABLE"
                obj["inventory"] = []
                obj["code_to_unlock"] = ""
                obj["item_to_unlock"] = ""
        elif len(container_indices) > clamped_max_containers:
            for idx in container_indices[clamped_max_containers:]:
                obj = objects[idx]
                obj["item_type"] = "PICKABLE"
                obj["inventory"] = []
                obj["code_to_unlock"] = ""
                obj["item_to_unlock"] = ""

        for idx in container_indices[:clamped_max_containers]:
            obj = objects[idx]
            code_to_unlock, item_to_unlock = _normalize_container_unlock_requirements(
                obj.get("code_to_unlock"),
                obj.get("item_to_unlock"),
            )
            obj["code_to_unlock"] = code_to_unlock
            obj["item_to_unlock"] = item_to_unlock

        readable_indices = [
            idx for idx, obj in enumerate(objects)
            if isinstance(obj, dict) and str(obj.get("item_type", "")).upper() == "READABLE"
        ]
        if not text_log_generation_enabled:
            for idx in readable_indices:
                obj = objects[idx]
                obj["item_type"] = "PICKABLE"
                obj["text_log_content"] = ""
                obj["text_log_format"] = ""
        else:
            if len(readable_indices) > clamped_max_text_logs:
                for idx in readable_indices[clamped_max_text_logs:]:
                    obj = objects[idx]
                    obj["item_type"] = "PICKABLE"
                    obj["text_log_content"] = ""
                    obj["text_log_format"] = ""

            for idx in readable_indices[:clamped_max_text_logs]:
                obj = objects[idx]
                obj["text_log_content"] = _normalize_text_log_content(
                    obj.get("text_log_content"),
                    obj.get("description"),
                    obj.get("name"),
                )
                text_log_format = str(obj.get("text_log_format") or "DOCUMENT").strip().upper()
                if text_log_format not in {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}:
                    text_log_format = "DOCUMENT"
                obj["text_log_format"] = text_log_format

        manifest_dict["cover_source_adventure_id"] = cover_source_adventure_id
        manifest_dict["cover_source_adventure_name"] = cover_source_adventure_name
        manifest_dict["cover_similarity_percent"] = max(0, min(100, int(cover_similarity_percent or 0)))
        manifest_dict["allow_reuse_source_assets"] = bool(allow_reuse_source_assets)

        await WorldGenerator.apply_manifest(
            db, 
            template_id, 
            manifest_dict,
            user=user if (generate_npc_images or generate_item_images or generate_scene_images) else None,
            gen_npc=generate_npc_images,
            gen_items=generate_item_images,
            gen_scenes=generate_scene_images,
            gen_protagonist_image=generate_scene_images,
            selected_image_styles=selected_image_styles,
            source_assets=cover_source_assets,
            status_callback=status_callback,
        )
        log_structured_event(
            "adventure.generation.world_applied",
            template_id=template_id,
            scene_count=len(manifesto.scenes),
            exit_count=len(manifesto.exits),
            npc_count=len(manifesto.npcs),
            object_count=len(manifesto.objects),
        )
        await db.flush()

    @staticmethod
    async def apply_manifest(
        db: AsyncSession, 
        template_id: str, 
        manifest_dict: dict, 
        user: Optional[User] = None,
        gen_npc: bool = False,
        gen_items: bool = False,
        gen_scenes: bool = False,
        gen_protagonist_image: bool = False,
        existing_images: Optional[dict] = None,
        source_assets: Optional[dict[str, Any]] = None,
        selected_image_styles: Optional[list[str]] = None,
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> None:
        """
        Populates (or re-populates) the world entities based on a manifest dictionary.
        If user is provided, attempts to generate entity images based on flags.
        If existing_images is provided, uses them to restore entity visual states.
        """
        from backend.engine.media_engine import MediaEngine
        adventure = await db.get(AdventureTemplate, template_id)

        image_attempts = 0
        image_successes = 0
        moderation_count = 0

        # Resolve Style Instructions
        if selected_image_styles is None and adventure:
            selected_image_styles = adventure.selected_image_styles

        def _get_base_slug(entity_id: str) -> str:
            import re
            return re.sub(r'(_COPY)?(_\d+)?$', '', entity_id, flags=re.IGNORECASE)

        def _public_data_url_to_local_path(url: Optional[str]) -> Optional[str]:
            raw = str(url or "").strip()
            if not raw.startswith("/data/"):
                return None
            rel = raw[len("/data/"):].lstrip("/").replace("/", os.sep)
            local_path = os.path.abspath(os.path.join(settings.DATA_DIR, rel))
            data_root = os.path.abspath(settings.DATA_DIR)
            try:
                if os.path.commonpath([local_path, data_root]) != data_root:
                    return None
            except ValueError:
                return None
            return local_path

        def _local_path_to_public_data_url(local_path: str) -> Optional[str]:
            data_root = os.path.abspath(settings.DATA_DIR)
            resolved = os.path.abspath(local_path)
            try:
                if os.path.commonpath([resolved, data_root]) != data_root:
                    return None
            except ValueError:
                return None
            rel = os.path.relpath(resolved, data_root).replace("\\", "/")
            return f"/data/{rel}"

        def _copy_source_asset_to_current_adventure(
            source_url: Optional[str],
            *,
            entity_type: str,
            source_asset_id: Optional[str],
        ) -> Optional[str]:
            source_local = _public_data_url_to_local_path(source_url)
            if not source_local or not os.path.isfile(source_local):
                return None

            target_root = os.path.abspath(
                os.path.join(settings.DATA_DIR, "adventures", "library", template_id)
            )
            try:
                if os.path.commonpath([source_local, target_root]) == target_root:
                    return source_url
            except ValueError:
                return None

            safe_prefix = slugify(str(source_asset_id or entity_type)) or "source"
            source_basename = os.path.basename(source_local)
            target_dir = os.path.abspath(
                os.path.join(target_root, "visuals", "reused", entity_type)
            )
            try:
                if os.path.commonpath([target_dir, target_root]) != target_root:
                    return None
            except ValueError:
                return None

            os.makedirs(target_dir, exist_ok=True)
            target_local = os.path.abspath(os.path.join(target_dir, f"{safe_prefix}_{source_basename}"))
            try:
                if os.path.commonpath([target_local, target_root]) != target_root:
                    return None
            except ValueError:
                return None

            if not os.path.isfile(target_local):
                try:
                    shutil.copy2(source_local, target_local)
                except Exception as exc:
                    logger.warning(
                        "Failed to localize reused source asset for %s/%s from %s: %s",
                        template_id,
                        entity_type,
                        source_url,
                        exc,
                    )
                    return None

            return _local_path_to_public_data_url(target_local)

        def _resolve_source_asset_image(
            entity_type: str,
            source_asset_id: Optional[str] = None,
        ) -> Optional[str]:
            if not source_assets:
                return None

            # Reuse must be explicit. Do not infer by matching IDs/names,
            # otherwise cover generations can become accidental 1:1 duplicates.
            if not source_asset_id:
                return None

            if entity_type == "cover":
                return _copy_source_asset_to_current_adventure(
                    source_assets.get("cover"),
                    entity_type=entity_type,
                    source_asset_id=source_asset_id,
                )

            if entity_type == "protagonist":
                protagonist_asset = source_assets.get("protagonist") or {}
                if source_asset_id == "PROTAGONIST" and protagonist_asset.get("image_url"):
                    return _copy_source_asset_to_current_adventure(
                        protagonist_asset.get("image_url"),
                        entity_type=entity_type,
                        source_asset_id=source_asset_id,
                    )
                return None

            bucket_key = {"scene": "scenes", "npc": "npcs", "object": "objects"}.get(entity_type)
            if not bucket_key:
                return None

            bucket = source_assets.get(bucket_key) or []
            if not isinstance(bucket, list):
                return None

            for asset in bucket:
                if asset.get("id") == source_asset_id and asset.get("image_url"):
                    return _copy_source_asset_to_current_adventure(
                        asset.get("image_url"),
                        entity_type=entity_type,
                        source_asset_id=source_asset_id,
                    )

            return None

        style_instruction = resolve_style_instruction(
            selected_image_styles,
            (user.image_styles_catalog if user else None),
        )
        
        logger.info(f"Applying manifest with style instruction: '{style_instruction}'")

        _validate_t2i_prerequisites(
            user,
            need_scene_images=gen_scenes,
            need_npc_images=gen_npc,
            need_item_images=gen_items,
            need_protagonist_image=gen_protagonist_image,
        )

        log_structured_event(
            "adventure.generation.apply_manifest.start",
            template_id=template_id,
            scene_count=len(manifest_dict.get("scenes", [])),
            exit_count=len(manifest_dict.get("exits", [])),
            npc_count=len(manifest_dict.get("npcs", [])),
            object_count=len(manifest_dict.get("objects", [])),
        )
        
        # Preserve any existing images if caller didn't provide them
        if existing_images is None:
            existing_images = {}
            ent_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id))
            for e in ent_res.scalars().all():
                if e.image_url: existing_images[e.id] = e.image_url
            
            scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
            for s in scene_res.scalars().all():
                if s.image_url: existing_images[s.id] = s.image_url

        # Ensure idempotency: clear prior world objects for this adventure so re-runs don't attempt duplicate inserts
        await db.execute(delete(WorldScene).where(WorldScene.template_id == template_id))
        await db.execute(delete(WorldExit).where(WorldExit.template_id == template_id))
        await db.execute(delete(WorldEntity).where(WorldEntity.template_id == template_id))

        # Deduplication caches
        seen_scene_ids = set()
        seen_entity_ids = set()
        starting_equipped_ids: dict[str, str] = {}
        starting_inv_ids: set[str] = set()
        protagonist_item_defs: dict[str, dict[str, Any]] = {}
        avatar = None

        # Duplication media caches for current run
        processed_npcs: list[dict] = []
        npc_image_cache: dict[str, str] = {}
        processed_objects: list[dict] = []
        object_image_cache: dict[str, str] = {}
        
        # 0. Sync Quests and Narrative Meta
        if adventure:
            quests = manifest_dict.get("quests") or []
            awards = manifest_dict.get("awards") or []

            if adventure.rule_enforcement_mode == "chat":
                quests = []
                awards = []

            for q in quests:
                if "status" not in q:
                    q["status"] = "open"
            if adventure:
                adventure.quests = quests  # type: ignore
                
                teaser = manifest_dict.get("teaser")
                if teaser:
                    adventure.teaser = teaser  # type: ignore
                
                # Narrative Meta
                adventure.plot = manifest_dict.get("plot") or adventure.plot  # type: ignore
                adventure.rules = manifest_dict.get("rules") or adventure.rules  # type: ignore
                adventure.intro_text = manifest_dict.get("intro_text") or adventure.intro_text  # type: ignore
                adventure.walkthrough = manifest_dict.get("walkthrough") or adventure.walkthrough  # type: ignore
                adventure.completed_condition = manifest_dict.get("completed_condition") or adventure.completed_condition  # type: ignore
                adventure.gameover_condition = manifest_dict.get("gameover_condition") or adventure.gameover_condition  # type: ignore
                adventure.tts_director_notes = manifest_dict.get("tts_director_notes") or adventure.tts_director_notes  # type: ignore
                
                # Flexible Time System
                if manifest_dict.get("time_system"):
                    adventure.time_system = manifest_dict["time_system"]  # type: ignore
                if manifest_dict.get("time_config"):
                    adventure.time_config = manifest_dict["time_config"]  # type: ignore
                
                if manifest_dict.get("starting_timestamp") is not None:
                    adventure.starting_timestamp = manifest_dict["starting_timestamp"]  # type: ignore
                
                if manifest_dict.get("allow_dynamic_items") is not None:
                    adventure.allow_dynamic_items = manifest_dict["allow_dynamic_items"]  # type: ignore

                if manifest_dict.get("can_damage_npcs") is not None:
                    adventure.can_damage_npcs = manifest_dict["can_damage_npcs"]  # type: ignore

                if manifest_dict.get("npcs_can_damage_protagonist") is not None:
                    adventure.npcs_can_damage_protagonist = manifest_dict["npcs_can_damage_protagonist"]  # type: ignore

                if manifest_dict.get("game_over_rules") is not None:
                    adventure.game_over_rules = manifest_dict["game_over_rules"]  # type: ignore
                
                if manifest_dict.get("awards") is not None:
                    adventure.awards = manifest_dict["awards"]  # type: ignore
            
            # Optional Time Initialization (Convert to minutes since start if possible)
            # For now we just check if it's there; future logic can normalize this.
            if manifest_dict.get("start_time"):
                # Very simple heuristic: 08:00 -> 480 mins
                try:
                    h, m = map(int, manifest_dict["start_time"].split(':'))
                    adventure.starting_timestamp = h * 60 + m
                except:
                    pass
            
            for a in awards:
                if "is_earned" not in a:
                    a["is_earned"] = False
            adventure.awards = awards
            
            # Sync to active sessions if they don't have quests yet (e.g. during first generation)
            from backend.models.session_state import SessionState
            state_res = await db.execute(select(SessionState).where(SessionState.template_id == template_id))
            for state in state_res.scalars().all():
                if not state.quests:
                    state.quests = quests
                # Always sync narrative meta during generation/rebuild to keep sessions in sync with the new world logic
                state.plot = adventure.plot
                state.rules = adventure.rules
                state.walkthrough = adventure.walkthrough
                state.completed_condition = adventure.completed_condition
                state.gameover_condition = adventure.gameover_condition
                state.tts_director_notes = adventure.tts_director_notes
                state.time_system = adventure.time_system
                state.time_config = adventure.time_config
            
            # Commit metadata and structural changes first to release locks before starting long generations
            await db.commit()
            # Re-fetch adventure and user to ensure they are in the current session after commit
            adventure = await db.get(AdventureTemplate, template_id)
            if user:
                user = await db.get(User, user.id)
            
            # Generate Adventure Cover if missing
            any_image_generation_enabled = bool(gen_scenes or gen_npc or gen_items or gen_protagonist_image)
            if adventure and user and not adventure.image_url and any_image_generation_enabled:
                await _publish_generation_status_with_callback(
                    db,
                    adventure,
                    "Painting Adventure Cover...",
                    status_callback=status_callback,
                )
                try:
                    requested_cover_source_id = manifest_dict.get("cover_source_asset_id")
                    reused_cover_url = None
                    if requested_cover_source_id == "COVER":
                        reused_cover_url = _resolve_source_asset_image("cover", requested_cover_source_id)
                    if reused_cover_url:
                        cover_url = reused_cover_url
                    else:
                        image_attempts += 1
                        cover_url = await MediaEngine.generate_adventure_cover(
                            title=adventure.title,
                            original_prompt=adventure.teaser or adventure.original_prompt,
                            adventure_id=template_id,
                            user_config={"t2i_settings": user.t2i_settings},
                            api_keys=dict(user.encrypted_api_keys or {}),  # type: ignore
                            style_instruction=style_instruction
                        )
                    if cover_url:
                        image_successes += 1
                        adventure.image_url = cover_url  # type: ignore
                        await db.commit() # Save cover immediately
                        adventure = await db.get(AdventureTemplate, template_id)
                except Exception as e:
                    if is_image_moderation_error(e):
                        moderation_count += 1
                    logger.warning(f"Failed to generate adventure cover for {template_id}: {e}")

            await db.flush()

        # 0. Sync Protagonist to Avatar
        prot = manifest_dict.get("protagonist", {})
        if prot and adventure:
            from backend.models.avatar import Avatar
            av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
            avatar = av_res.scalars().first()
            
            # Map of ID -> Slot for starting equipment
            raw_equip = prot.get("starting_equipment") or {}
            starting_equipped_ids = {}
            for slot, val in raw_equip.items():
                item_id = val.get("id") if isinstance(val, dict) else val
                if item_id:
                    starting_equipped_ids[item_id] = slot
                    if isinstance(val, dict):
                        protagonist_item_defs[item_id] = val

            raw_inv = prot.get("starting_inventory") or []
            starting_inv_ids = set()
            for item in raw_inv:
                item_id = item.get("id") if isinstance(item, dict) else item
                if item_id:
                    starting_inv_ids.add(item_id)
                    if isinstance(item, dict):
                        protagonist_item_defs[item_id] = item

            if not avatar:
                # Create new Avatar for this adventure
                s = prot.get("stats", {})
                avatar = Avatar(
                    template_id=template_id,
                    user_id=adventure.owner_id,
                    name=prot.get("name", "Hero"),
                    role=prot.get("role", "Protagonist"),
                    description=prot.get("description", ""),
                    goal=prot.get("goal", ""),
                    character=prot.get("character", ""),
                    hp=prot.get("hp", 200),
                    max_hp=prot.get("hp", 200),
                    stamina=prot.get("stamina", 200),
                    max_stamina=prot.get("stamina", 200),
                    mana=prot.get("mana", 200),
                    max_mana=prot.get("mana", 200),
                    strength=prot.get("strength", 10),
                    dexterity=prot.get("dexterity", 10),
                    intelligence=prot.get("intelligence", 10),
                    wisdom=prot.get("wisdom", 10),
                    charisma=prot.get("charisma", 10),
                    armor_class=prot.get("armor_class", 10),
                    exp=prot.get("exp", 0),
                    status_effects=prot.get("status_effects", []),
                    stats=prot.get("stats", {}),
                    inventory=[],
                    equipment={
                        "Head": None, "Chest": None, "Arms": None, "Legs": None,
                        "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None, 
                        "Neck": None, "MainHand": None, "OffHand": None
                    }
                )
                db.add(avatar)
            else:
                # Update existing Avatar
                avatar.name = prot.get("name", avatar.name)
                avatar.role = prot.get("role", avatar.role)
                avatar.description = prot.get("description", avatar.description)
                avatar.goal = prot.get("goal", avatar.goal)
                avatar.character = prot.get("character", avatar.character)
                avatar.hp = prot.get("hp", avatar.hp)
                avatar.max_hp = prot.get("hp", avatar.max_hp)
                avatar.stamina = prot.get("stamina", avatar.stamina)
                avatar.max_stamina = prot.get("stamina", avatar.max_stamina)
                avatar.mana = prot.get("mana", avatar.mana)
                avatar.max_mana = prot.get("mana", avatar.max_mana)
                
                # Sync Core Stats from manifest (flattened in Schema)
                avatar.strength = prot.get("strength", avatar.strength)
                avatar.dexterity = prot.get("dexterity", avatar.dexterity)
                avatar.intelligence = prot.get("intelligence", avatar.intelligence)
                avatar.wisdom = prot.get("wisdom", avatar.wisdom)
                avatar.charisma = prot.get("charisma", avatar.charisma)
                avatar.armor_class = prot.get("armor_class", avatar.armor_class)
                avatar.exp = prot.get("exp", avatar.exp)
                avatar.status_effects = prot.get("status_effects") or avatar.status_effects
                
                avatar.stats = prot.get("stats") or avatar.stats
                
                # We do NOT assign inventory/equipment directly here anymore, 
                # because they are populated during the object resolution loop below.
                # However, we clear them to ensure a fresh state if we are re-applying.
                avatar.inventory = []  # type: ignore
                avatar.equipment = {  # type: ignore
                    "head": None, "neck": None, "chest": None, "back": None,
                    "arms": None, "hands": None, "waist": None, "legs": None, "feet": None,
                    "main_hand": None, "off_hand": None, "ring_1": None, "ring_2": None
                }

            # Unified Portrait Logic
            image_url = (
                (existing_images or {}).get("PROTAGONIST")
                or _resolve_source_asset_image("protagonist", prot.get("source_asset_id"))
                or prot.get("profile_image")
            )
            if not image_url or image_url.startswith("assets/"): # If it's a relative path from manifest, it should have been in existing_images
                if user and gen_protagonist_image:
                    await _publish_generation_status_with_callback(
                        db,
                        adventure,
                        f"Envisioning Portrait for {avatar.name}...",
                        status_callback=status_callback,
                    )
                    prompt = prompts.PROTAGONIST_IMAGE_PROMPT_TEMPLATE.format(
                        name=avatar.name,
                        role=avatar.role,
                        description=avatar.description
                    )
                    generated_plot = (manifest_dict.get("plot") or "").strip()
                    if generated_plot:
                        prompt = f"{prompt} Narrative context: {generated_plot[:1200]}"
                    image_attempts += 1
                    try:
                        image_url = await asyncio.wait_for(
                            MediaEngine.generate_entity_image(
                                prompt,
                                template_id,
                                "PROTAGONIST",
                                "NPC",
                                {"t2i_settings": user.t2i_settings},
                                dict(user.encrypted_api_keys or {}),  # type: ignore
                                style_instruction=style_instruction,
                                use_advanced_model=((user.t2i_settings or {}).get("protagonist_model_quality", "advanced") == "advanced"),
                            ),
                            timeout=_image_generation_timeout_seconds(),
                        )
                    except Exception as exc:
                        if is_image_moderation_error(exc):
                            moderation_count += 1
                        logger.warning("Protagonist image generation failed for %s: %s", template_id, exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                
                if not image_url or image_url.startswith("assets/"):
                    # Fallback to high-quality placeholder
                    if not avatar.profile_image or not avatar.profile_image.startswith("/data/"):
                        image_url = await MediaEngine.generate_placeholder(
                            template_id, "PROTAGONIST", os.path.join(settings.DATA_DIR, "adventures", "library", template_id),
                            category="SCENE"
                        )
                    else:
                        image_url = avatar.profile_image
            
            avatar.profile_image = image_url
            await db.commit() # Save avatar
            adventure = await db.get(AdventureTemplate, template_id)
            
        # Persist Scenes
        scenes = manifest_dict.get("scenes", [])
        total_scenes = len(scenes)
        for scene_index, s in enumerate(scenes, start=1):
            if s["id"] in seen_scene_ids:
                continue
            seen_scene_ids.add(s["id"])
            
            image_url = (
                (existing_images or {}).get(s["id"])
                or _resolve_source_asset_image("scene", s.get("source_asset_id"))
                or s.get("image_url")
            )
            if not image_url or image_url.startswith("assets/"):
                if user and gen_scenes:
                    await _publish_generation_status_with_callback(
                        db,
                        adventure,
                        f"Envisioning Scene {scene_index}/{total_scenes}: {s['name']}...",
                        status_callback=status_callback,
                    )
                    prompt = prompts.SCENE_IMAGE_PROMPT_TEMPLATE.format(
                        name=s['name'], description=s['description']
                    )
                    image_attempts += 1
                    try:
                        # FIX: Use generate_scene_image for SCENES (Advanced Model)
                        image_url = await asyncio.wait_for(
                            MediaEngine.generate_scene_image(
                                prompt,
                                template_id,
                                {"t2i_settings": user.t2i_settings},
                                dict(user.encrypted_api_keys or {}),  # type: ignore
                                style_instruction=style_instruction,
                            ),
                            timeout=_image_generation_timeout_seconds(),
                        )
                    except asyncio.TimeoutError as exc:
                        logger.warning("Scene image generation timed out for %s/%s: %s", template_id, s['id'], exc)
                        image_url = None
                    except Exception as exc:
                        if is_image_moderation_error(exc):
                            moderation_count += 1
                        logger.warning("Scene image generation failed for %s/%s: %s", template_id, s['id'], exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                
                if not image_url or image_url.startswith("assets/"):
                    # Fallback to high-quality placeholder
                    image_url = await MediaEngine.generate_placeholder(
                        template_id, s["id"], os.path.join(settings.DATA_DIR, "adventures", "library", template_id, "scenes"),
                        category="SCENE"
                    )
 
            db.add(WorldScene(
                id=s["id"],
                template_id=template_id,
                label=s.get("name") or s.get("label") or "Unknown Scene",
                description=s["description"],
                image_url=image_url
            ))
            
        # Persist Exits
        for e in manifest_dict.get("exits", []):
            db.add(WorldExit(
                template_id=template_id,
                from_scene_id=e["from_scene_id"],
                to_scene_id=e["to_scene_id"],
                label=e["label"],
                is_locked=e["is_locked"],
                lock_description=e.get("lock_description")
            ))
        
        await db.commit() # Save scenes and exits
        adventure = await db.get(AdventureTemplate, template_id)
            
        # Persist NPCs
        npcs = manifest_dict.get("npcs", [])
        total_npcs = len(npcs)
        default_scene_id = scenes[0]["id"] if scenes else "START"
        for npc_index, n in enumerate(npcs, start=1):
            if n["id"] in seen_entity_ids:
                continue
            seen_entity_ids.add(n["id"])
            
            # Check if this NPC is a duplicate of a previously processed NPC
            duplicate_image_url = None
            for prev in processed_npcs:
                # 1. Compare base slugs
                if _get_base_slug(prev["id"]) == _get_base_slug(n["id"]):
                    duplicate_image_url = npc_image_cache.get(prev["id"])
                    break
                # 2. Compare name and description
                if (prev["name"].lower().strip(), prev["description"].lower().strip()) == (n["name"].lower().strip(), n["description"].lower().strip()):
                    duplicate_image_url = npc_image_cache.get(prev["id"])
                    break
                # 3. Compare source_asset_id
                if n.get("source_asset_id") and prev.get("source_asset_id") == n.get("source_asset_id"):
                    duplicate_image_url = npc_image_cache.get(prev["id"])
                    break
            
            image_url = (
                duplicate_image_url
                or (existing_images or {}).get(n["id"])
                or _resolve_source_asset_image("npc", n.get("source_asset_id"))
                or n.get("image_url")
            )
            if not image_url or image_url.startswith("assets/"):
                if user and gen_npc:
                    await _publish_generation_status_with_callback(
                        db,
                        adventure,
                        f"Envisioning Portrait {npc_index}/{total_npcs}: {n['name']}...",
                        status_callback=status_callback,
                    )
                    prompt = prompts.NPC_IMAGE_PROMPT_TEMPLATE.format(
                        name=n['name'], description=n['description']
                    )
                    image_attempts += 1
                    try:
                        image_url = await asyncio.wait_for(
                            MediaEngine.generate_entity_image(
                                prompt,
                                template_id,
                                n['id'],
                                "NPC",
                                {"t2i_settings": user.t2i_settings},
                                dict(user.encrypted_api_keys or {}),  # type: ignore
                                style_instruction=style_instruction,
                                use_advanced_model=((user.t2i_settings or {}).get("profile_model_quality", "advanced") == "advanced"),
                            ),
                            timeout=_image_generation_timeout_seconds(),
                        )
                    except asyncio.TimeoutError as exc:
                        logger.warning("NPC image generation timed out for %s/%s: %s", template_id, n['id'], exc)
                        image_url = None
                    except Exception as exc:
                        if is_image_moderation_error(exc):
                            moderation_count += 1
                        logger.warning("NPC image generation failed for %s/%s: %s", template_id, n['id'], exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                
                if not image_url or image_url.startswith("assets/"):
                    # Fallback to high-quality placeholder for NPCs
                    image_url = await MediaEngine.generate_placeholder(
                        template_id, n["id"], os.path.join(settings.DATA_DIR, "adventures", "library", template_id, "entities"),
                        category="NPC"
                    )

            if image_url:
                npc_image_cache[n["id"]] = image_url
            processed_npcs.append(n)

            db.add(WorldEntity(
                id=n["id"],
                template_id=template_id,
                entity_type="NPC",
                name=n["name"],
                description=n["description"],
                goal=n.get("goal"),
                character=n.get("character"),
                current_scene_id=n.get("start_scene_id") or n.get("current_scene_id") or default_scene_id,
                spatial_position=n.get("spatial_position"),
                image_url=image_url,
                npc_type=n.get("npc_type"),
                movement_type=n.get("movement_type"),
                hp=n.get("hp"),
                max_hp=n.get("hp"),
                mana=n.get("mana"),
                max_mana=n.get("mana"),
                stamina=n.get("stamina"),
                max_stamina=n.get("stamina"),
                is_hidden=n.get("is_hidden", False),
                reveal_rule=n.get("reveal_rule") or None,
                is_attackable=n.get("is_attackable", True),
                is_killable=n.get("is_killable", True),
            ))
            
            # Commit after each NPC to save progress and release locks during long generations
            await db.commit()
            adventure = await db.get(AdventureTemplate, template_id)
            if user:
                user = await db.get(User, user.id)
            
        await db.commit() # Save NPCs
        adventure = await db.get(AdventureTemplate, template_id)
            
        # Persist Objects & Collect for NPC Inventories
        if adventure:
            adventure.teaser = manifest_dict.get("teaser", "")  # type: ignore
            adventure.original_prompt = manifest_dict.get("plot", "")  # type: ignore
            adventure.rules = manifest_dict.get("rules", "")  # type: ignore
            adventure.language = manifest_dict.get("language", "")  # type: ignore
            adventure.is_ready = False  # type: ignore
            adventure.origin_id = manifest_dict.get("origin_id", "")  # type: ignore
            adventure.is_adventure_generator = manifest_dict.get("is_adventure_generator", False)  # type: ignore
            adventure.can_damage_npcs = manifest_dict.get("can_damage_npcs", True)  # type: ignore
            adventure.npcs_can_damage_protagonist = manifest_dict.get("npcs_can_damage_protagonist", True)  # type: ignore
            adventure.original_manifest = manifest_dict  # type: ignore
        # Merge starting inventory & equipment definitions into the objects list if defined inline.
        objects = list(manifest_dict.get("objects", []))
        seen_object_ids = {o.get("id") for o in objects if isinstance(o, dict) and "id" in o}
        
        prot = manifest_dict.get("protagonist", {})
        if prot:
            for item in (prot.get("starting_inventory") or []):
                if isinstance(item, dict) and "id" in item:
                    if item["id"] not in seen_object_ids:
                        objects.append(item)
                        seen_object_ids.add(item["id"])
            for slot, item in (prot.get("starting_equipment") or {}).items():
                if isinstance(item, dict) and "id" in item:
                    if item["id"] not in seen_object_ids:
                        objects.append(item)
                        seen_object_ids.add(item["id"])

        total_objects = len(objects)
        
        def _inventory_item_id(entry: Any) -> Optional[str]:
            if isinstance(entry, str):
                return entry
            if isinstance(entry, dict):
                for key in ("id", "item_id", "object_id"):
                    value = entry.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
            return None

        # Build mapping of NPC inventories: npc_id -> list of item_ids
        npc_inventories = {
            n["id"]: [item_id for item_id in (_inventory_item_id(e) for e in (n.get("inventory") or [])) if item_id]
            for n in npcs
        }
        all_npc_inventory_item_ids = set()
        for inv in npc_inventories.values():
            all_npc_inventory_item_ids.update(inv)

        def _extract_numeric_stat(obj: dict[str, Any], source_item: dict[str, Any], *keys: str) -> Optional[int]:
            for key in keys:
                value = obj.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

            for key in keys:
                value = source_item.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

            metadata = obj.get("metadata_json") if isinstance(obj.get("metadata_json"), dict) else {}
            for key in keys:
                value = metadata.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

            stat_modifiers = metadata.get("stat_modifiers") if isinstance(metadata.get("stat_modifiers"), dict) else {}
            for key in keys:
                value = stat_modifiers.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

            return None

        def _extract_numeric_effect(obj: dict[str, Any], source_item: dict[str, Any], *keys: str) -> Optional[int]:
            for key in keys:
                value = obj.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

            for key in keys:
                value = source_item.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

            metadata = obj.get("metadata_json") if isinstance(obj.get("metadata_json"), dict) else {}
            for key in keys:
                value = metadata.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

            effects = metadata.get("effects") if isinstance(metadata.get("effects"), dict) else {}
            for key in keys:
                value = effects.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

            source_effects = source_item.get("effects") if isinstance(source_item.get("effects"), dict) else {}
            for key in keys:
                value = source_effects.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

            return None
            
        # Mapping for full item data resolution
        resolved_items = {}

        for object_index, o in enumerate(objects, start=1):
            if o["id"] in seen_entity_ids:
                continue
            seen_entity_ids.add(o["id"])

            source_item = protagonist_item_defs.get(o["id"], {})
            stat_strength = _extract_numeric_stat(o, source_item, "stat_modifier_strength", "strength")
            stat_dexterity = _extract_numeric_stat(o, source_item, "stat_modifier_dexterity", "stat_modifier_agility", "dexterity", "agility")
            stat_intelligence = _extract_numeric_stat(o, source_item, "stat_modifier_intelligence", "intelligence")
            stat_wisdom = _extract_numeric_stat(o, source_item, "stat_modifier_wisdom", "wisdom")
            stat_charisma = _extract_numeric_stat(o, source_item, "stat_modifier_charisma", "charisma")
            stat_armor_class = _extract_numeric_stat(o, source_item, "stat_modifier_armor_class", "armor_class", "ac")
            hp_change = _extract_numeric_effect(o, source_item, "hp_change", "health_change", "heal", "heal_amount", "restore_hp", "restore_health", "hp")
            stamina_change = _extract_numeric_effect(o, source_item, "stamina_change", "restore_stamina", "stamina_restore", "stamina", "energy")
            mana_change = _extract_numeric_effect(o, source_item, "mana_change", "restore_mana", "mana_restore", "mana")
            
            # Check if this object is a duplicate of a previously processed object
            duplicate_image_url = None
            for prev in processed_objects:
                # 1. Compare base slugs
                if _get_base_slug(prev["id"]) == _get_base_slug(o["id"]):
                    duplicate_image_url = object_image_cache.get(prev["id"])
                    break
                # 2. Compare name and description
                if (prev["name"].lower().strip(), prev["description"].lower().strip()) == (o["name"].lower().strip(), o["description"].lower().strip()):
                    duplicate_image_url = object_image_cache.get(prev["id"])
                    break
                # 3. Compare source_asset_id
                if o.get("source_asset_id") and prev.get("source_asset_id") == o.get("source_asset_id"):
                    duplicate_image_url = object_image_cache.get(prev["id"])
                    break

            image_url = (
                duplicate_image_url
                or (existing_images or {}).get(o["id"])
                or _resolve_source_asset_image("object", o.get("source_asset_id"))
                or o.get("image_url")
            )
            if not image_url or image_url.startswith("assets/"):
                if user and gen_items:
                    await _publish_generation_status_with_callback(
                        db,
                        adventure,
                        f"Reifying Artifact {object_index}/{total_objects}: {o['name']}...",
                        status_callback=status_callback,
                    )
                    prompt = prompts.OBJECT_IMAGE_PROMPT_TEMPLATE.format(
                        name=o['name'], description=o['description']
                    )
                    image_attempts += 1
                    try:
                        image_url = await asyncio.wait_for(
                            MediaEngine.generate_entity_image(
                                prompt,
                                template_id,
                                o['id'],
                                "OBJECT",
                                {"t2i_settings": user.t2i_settings},
                                dict(user.encrypted_api_keys or {}),  # type: ignore
                                style_instruction=style_instruction,
                                use_advanced_model=((user.t2i_settings or {}).get("asset_model_quality", "simple") == "advanced"),
                            ),
                            timeout=float(settings.VISUAL_TIMEOUT),
                        )
                    except Exception as exc:
                        if is_image_moderation_error(exc):
                            moderation_count += 1
                        logger.warning("Object image generation failed for %s/%s: %s", template_id, o['id'], exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                
                if not image_url or image_url.startswith("assets/"):
                    # Fallback to high-quality placeholder for Items
                    item_type = str(o.get("item_type") or "PICKABLE").upper()
                    safe_entity_id = slugify(str(o.get("id") or "")) or "entity"
                    image_url = await MediaEngine.generate_placeholder(
                        template_id, safe_entity_id, os.path.join(settings.DATA_DIR, "adventures", "library", template_id, "entities"),
                        category=f"ITEM_{item_type}"
                    )

            is_starting_inv = o["id"] in starting_inv_ids
            starting_slot = starting_equipped_ids.get(o["id"])
            is_in_avatar_inv = is_starting_inv or (starting_slot is not None)
            is_in_npc_inv = o["id"] in all_npc_inventory_item_ids

            from backend.engine.item_logic import get_item_slot
            guessed_slot = get_item_slot(o["name"], o.get("item_type", "PICKABLE"))
            item_slot = o.get("wearable_slots")[0] if (o.get("wearable_slots") and len(o.get("wearable_slots")) > 0) else guessed_slot

            item_data = {
                "id": o["id"],
                "name": o["name"],
                "description": o["description"],
                "image_url": image_url,
                "item_type": o.get("item_type", "PICKABLE"),
                "slot": item_slot,
                "text_log_content": _normalize_text_log_content(
                    o.get("text_log_content"),
                    o.get("description"),
                    o.get("name"),
                ),
                "text_log_format": str(o.get("text_log_format") or "").strip().upper() or None,
                "stat_modifier_strength": stat_strength,
                "stat_modifier_dexterity": stat_dexterity,
                "stat_modifier_intelligence": stat_intelligence,
                "stat_modifier_wisdom": stat_wisdom,
                "stat_modifier_charisma": stat_charisma,
                "stat_modifier_armor_class": stat_armor_class,
                "hp_change": hp_change,
                "stamina_change": stamina_change,
                "mana_change": mana_change,
            }
            resolved_items[o["id"]] = item_data

            metadata_json = dict(o.get("metadata_json") or {})
            if hp_change is not None:
                metadata_json["hp_change"] = hp_change
            if stamina_change is not None:
                metadata_json["stamina_change"] = stamina_change
            if mana_change is not None:
                metadata_json["mana_change"] = mana_change

            if str(o.get("item_type") or "").upper() == "READABLE":
                text_log_content = _normalize_text_log_content(
                    o.get("text_log_content"),
                    o.get("description"),
                    o.get("name"),
                )
                text_log_format = str(o.get("text_log_format") or "DOCUMENT").strip().upper()
                if text_log_format not in {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}:
                    text_log_format = "DOCUMENT"
                metadata_json["text_log_content"] = text_log_content
                metadata_json["text_log_format"] = text_log_format

            if str(o.get("item_type") or "").upper() == "CONTAINER":
                code_to_unlock, item_to_unlock = _normalize_container_unlock_requirements(
                    o.get("code_to_unlock"),
                    o.get("item_to_unlock"),
                )
                metadata_json["code_to_unlock"] = code_to_unlock
                metadata_json["item_to_unlock"] = item_to_unlock
                metadata_json["locked"] = bool(code_to_unlock or item_to_unlock)

            if avatar and is_in_avatar_inv:
                if is_starting_inv:
                    # SQLAlchemy mutability: re-assign the list
                    avatar.inventory = list(avatar.inventory) + [o["id"]]  # type: ignore
                if starting_slot:
                    # SQLAlchemy mutability: re-assign the dict
                    new_equip = dict(avatar.equipment)
                    new_equip[starting_slot] = o["id"]
                    avatar.equipment = new_equip  # type: ignore

            if image_url:
                object_image_cache[o["id"]] = image_url
            processed_objects.append(o)

            db.add(
                WorldEntity(
                    id=o["id"],
                    template_id=template_id,
                    entity_type="OBJECT",
                    name=o["name"],
                    description=o["description"],
                    current_scene_id="INVENTORY" if (is_in_avatar_inv or is_in_npc_inv) else (o.get("start_scene_id") or o.get("current_scene_id") or default_scene_id),
                    spatial_position=o.get("spatial_position"),
                    image_url=image_url,
                    item_type=o.get("item_type", "PICKABLE"),
                    wearable_slots=o.get("wearable_slots"),
                    is_hidden=o.get("is_hidden", False),
                    reveal_rule=o.get("reveal_rule") or None,
                    unlock_rule=None,
                    is_in_inventory=is_in_avatar_inv or is_in_npc_inv,
                    is_portable=o.get("is_portable", o.get("item_type") != "STATIC"),
                    combination_ingredients=o.get("combination_ingredients"),
                    reveals_item_id=o.get("reveals_item_id"),
                    inventory=o.get("inventory") or [],
                    state_comment=o.get("state_comment"),
                    stat_modifier_strength=stat_strength,
                    stat_modifier_dexterity=stat_dexterity,
                    stat_modifier_intelligence=stat_intelligence,
                    stat_modifier_wisdom=stat_wisdom,
                    stat_modifier_charisma=stat_charisma,
                    stat_modifier_armor_class=stat_armor_class,
                    metadata_json=metadata_json,
                )
            )
            
            # Commit after each Object to save progress and release locks
            await db.commit()
            adventure = await db.get(AdventureTemplate, template_id)
            if user:
                user = await db.get(User, user.id)

        # Final Pass: Update NPC Inventories with resolved item data
        # Fetch all NPCs for this template to update their inventories
        npc_objs_res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == template_id,
                WorldEntity.entity_type == "NPC"
            )
        )
        all_npcs = {n.id: n for n in npc_objs_res.scalars().all()}

        for npc_id, item_ids in npc_inventories.items():
            if not item_ids or npc_id not in all_npcs:
                continue
            
            npc_obj = all_npcs[npc_id]
            npc_inv = []
            for iid in item_ids:
                if iid in resolved_items:
                    npc_inv.append(resolved_items[iid])
            npc_obj.inventory = npc_inv  # type: ignore

        await db.commit() # Save everything finally

        log_structured_event(
            "adventure.generation.apply_manifest.complete",
            template_id=template_id,
            scene_count=len(manifest_dict.get("scenes", [])),
            exit_count=len(manifest_dict.get("exits", [])),
            npc_count=len(manifest_dict.get("npcs", [])),
            object_count=len(manifest_dict.get("objects", [])),
            image_attempts=image_attempts,
            image_successes=image_successes,
        )

        requested_image_generation = bool(user and (gen_scenes or gen_npc or gen_items or gen_protagonist_image))
        warning_messages: list[str] = []

        if moderation_count > 0:
            warning_messages.append(
                f"Notice: {moderation_count} images were blocked by safety filters and replaced with placeholders. "
                "You can regenerate them in the editor with adjusted descriptions."
            )

        if requested_image_generation and image_attempts > 0 and image_successes == 0 and moderation_count == 0:
            warning_messages.append(
                "Notice: Image generation did not return usable images, so placeholders were used. "
                "You can regenerate visuals later in the editor."
            )

        if warning_messages and adventure:
            adventure.creation_error = " ".join(warning_messages)  # type: ignore
            await db.commit()

