import logging
import asyncio
import os
from typing import List, Optional, Dict, Literal, Any, Callable, Awaitable
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.core.llm_router import GameMasterLLM
from backend.core.llm_logger import log_structured_event
from backend.models.user import User
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.models.adventure_template import AdventureTemplate, GenerationCancelled
from backend.core.config import settings
from backend.core import prompts
from backend.core.style_catalog import resolve_style_instruction

logger = logging.getLogger(__name__)


def _image_generation_timeout_seconds() -> float:
    raw_timeout = getattr(settings, "IMAGE_GENERATION_TIMEOUT_SECONDS", 120)
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
        if provider != "ollama":
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
        if provider != "ollama":
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
        
    adventure.creation_status = status
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

# --- Schemas for Structured LLM Output ---

class WorldSceneSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the scene, e.g., CASTLE_GATES")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Atmospheric and detailed description of the location.")
    
    model_config = {"extra": "forbid"}

class WorldExitSchema(BaseModel):
    from_scene_id: str
    to_scene_id: str
    label: str = Field(..., description="How to describe the transition, e.g., 'a narrow stone staircase'")
    is_locked: bool = False
    lock_description: Optional[str] = None
    
    model_config = {"extra": "forbid"}

class WorldEntitySchema(BaseModel):
    id: str = Field(..., description="Unique slug for the entity, e.g., MAD_ALCHEMIST")
    type: str = Field(..., pattern="^(NPC|OBJECT)$")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Appearance and demeanor or physical characteristics.")
    start_scene_id: str
    spatial_position: str = Field(..., description="Precise micro-location in the scene, e.g., 'sitting in the armchair', 'hidden in a drawer'")
    
    # Advanced Item Fields (only for type='OBJECT')
    item_type: Optional[str] = Field(None, description="One of: CONSUMABLE, WEARABLE, STATIC, COMBINABLE, PICKABLE, WEAPON, TOOL, KEY, READABLE")
    wearable_slots: Optional[List[str]] = Field(None, description="If WEARABLE, which slots? e.g. ['Head'], ['Chest'], ['Hands'], ['Ring_1'], ['Ring_2']")
    is_hidden: bool = Field(False, description="If True, the player must SEARCH or trigger an event to see this.")
    is_portable: bool = Field(True, description="Whether the item can be picked up. False for STATIC objects.")
    combination_ingredients: Optional[List[str]] = Field(None, description="Item IDs required to trigger a combination.")
    reveals_item_id: Optional[str] = Field(None, description="Item slug revealed when combination occurs.")
    
    # NPC Specific Fields (only for type='NPC')
    npc_type: Optional[str] = Field(None, description="One of: HUMANOID, ANIMAL, MONSTER, BEING")
    movement_type: Optional[str] = Field(None, description="One of: STATIONARY, MOVABLE")
    hp: Optional[int] = Field(None, description="Optional hitpoints")
    mana: Optional[int] = Field(None, description="Optional mana")
    stamina: Optional[int] = Field(None, description="Optional stamina")

    # Stat Modifiers (for OBJECTS)
    stat_modifier_strength: Optional[int] = None
    stat_modifier_dexterity: Optional[int] = None
    stat_modifier_intelligence: Optional[int] = None
    stat_modifier_wisdom: Optional[int] = None
    stat_modifier_charisma: Optional[int] = None
    stat_modifier_armor_class: Optional[int] = None
    hp_change: Optional[int] = Field(None, description="For CONSUMABLE objects: HP delta when consumed (positive or negative).")
    stamina_change: Optional[int] = Field(None, description="For CONSUMABLE objects: Stamina delta when consumed (positive or negative).")
    mana_change: Optional[int] = Field(None, description="For CONSUMABLE objects: Mana delta when consumed (positive or negative).")
    
    inventory: Optional[List[str]] = Field(None, description="List of object IDs to start in this NPC's or Object's inventory.")
    
    model_config = {"extra": "forbid"}

class QuestSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the quest, e.g., FIND_GOLDEN_KEY")
    title: str = Field(..., description="Short, descriptive title")
    description: str = Field(..., description="Narrative description of what needs to be done")
    goal: str = Field(..., description="Technical condition for completion (for GM reference)")
    impact: Optional[str] = Field(None, description="How this affects the world when completed")
    exp_reward: int = Field(250, description="EXP awarded for completion (e.g., 50, 100, 250)")
    is_main: bool = Field(True, description="True if this quest is required to finish the adventure")
    status: str = Field("open", description="Current state: open, completed, failed")
    
    model_config = {"extra": "forbid"}

class AwardTemplateSchema(BaseModel):
    key: str = Field(..., description="Unique identifier for the award, e.g., SLAYER_OF_RATS")
    title: str = Field(..., description="Visual name of the award")
    description: str = Field(..., description="Short description shown to the player")
    tier: Literal["bronze", "silver", "gold"] = Field("bronze", description="The rarity/tier of the award")
    requirement: str = Field(..., description="The specific rule/condition when the GM should grant this award")
    
    model_config = {"extra": "forbid"}

class EquipmentSchema(BaseModel):
    Head: Optional[str] = None
    Chest: Optional[str] = None
    Hands: Optional[str] = None
    Legs: Optional[str] = None
    Feet: Optional[str] = None
    Neck: Optional[str] = None
    Ring_1: Optional[str] = None
    Ring_2: Optional[str] = None
    MainHand: Optional[str] = None
    OffHand: Optional[str] = None
    
    model_config = {"extra": "forbid"}

class ProtagonistSchema(BaseModel):
    name: str = Field(..., description="The name of the player character.")
    role: str = Field(..., description="The professional or narrative role of the player, e.g. 'Royal Chef', 'Exiled Alchemist'.")
    description: str = Field(..., description="A detailed narrative description of the character's appearance and backstory.")
    strength: int = Field(10, description="Base strength stat (1-99)")
    dexterity: int = Field(10, description="Base dexterity stat (1-99)")
    intelligence: int = Field(10, description="Base intelligence stat (1-99)")
    wisdom: int = Field(10, description="Base wisdom stat (1-99)")
    charisma: int = Field(10, description="Base charisma stat (1-99)")
    armor_class: int = Field(10, description="Base armor class stat (1-99)")
    starting_inventory: Optional[List[str]] = Field(None, description="List of object IDs to start in the player's pocket.")
    starting_equipment: Optional[EquipmentSchema] = Field(None, description="Initial equipment setup.")
    hp: int = Field(200, description="Base health points")
    mana: int = Field(200, description="Base mana points")
    stamina: int = Field(200, description="Base stamina points")
    
    model_config = {"extra": "forbid"}

class TimeConfigSchema(BaseModel):
    day_label: Optional[str] = Field(None, description="Label for the day unit, e.g. 'Day', 'Sol', 'Cycle'")
    start_year_override: Optional[int] = Field(None, description="Override for the starting year in calendar mode")
    
    model_config = {"extra": "forbid"}

class WorldManifesto(BaseModel):
    """
    The complete blueprint of the generated world.
    """
    protagonist: ProtagonistSchema
    teaser: str = Field(..., description="A short, atmospheric teaser text for the adventure, max 100 characters.")
    language: str = Field("English", description="The target language for all generated content.")
    plot: str = Field(..., description="The main plotline, goals, and narrative arc of the adventure.")
    rules: str = Field(..., description="Special rules or mechanics specific to this adventure world.")
    intro_text: Optional[str] = Field(None, description="Optional intro text shown once when a new session starts.")
    walkthrough: str = Field(..., description="A secret GM walkthrough/solution for the adventure.")
    completed_condition: str = Field(..., description="Technical or narrative condition for winning the adventure.")
    gameover_condition: str = Field(..., description="Technical or narrative condition for losing the adventure.")
    scenes: List[WorldSceneSchema]
    exits: List[WorldExitSchema]
    npcs: List[WorldEntitySchema]
    objects: List[WorldEntitySchema]
    quests: List[QuestSchema] = Field(default_factory=list)
    awards: List[AwardTemplateSchema] = Field(default_factory=list)
    
    # Optional Time Initialization
    start_date: Optional[str] = Field(None, description="Initial in-game date, e.g. '2026-04-17'")
    start_time: Optional[str] = Field(None, description="Initial in-game time, e.g. '08:00'")
    time_system: Optional[str] = Field("calendar", description="One of: calendar, relative")
    time_config: Optional[TimeConfigSchema] = Field(None, description="Detailed configuration for the time system.")
    origin_id: Optional[str] = Field(None, description="A stable ID for this adventure template.")
    
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
        min_scenes: int = 1,
        max_scenes: int = 5,
        award_generation_enabled: bool = True,
        min_awards: int = 3,
        max_awards: int = 5,
        selected_image_styles: Optional[List[str]] = None,
        selected_tone: Optional[str] = None,
        language: Optional[str] = None,
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None,

    ) -> None:
        """
        Calls the complex LLM to generate a coherent world structure based on the adventure theme.
        Persists the result to the WorldScene, WorldExit, and WorldEntity tables.
        """
        # If no provider is given, use the one from user settings
        if not provider:
            llm_settings = user.llm_settings or {}
            provider = (
                llm_settings.get("complex_model_provider")
                or llm_settings.get("small_model_provider")
                or llm_settings.get("preferred_provider")
            )
        
        if not model:
            llm_settings = user.llm_settings or {}
            model = llm_settings.get("complex_model") or llm_settings.get("small_model") or "gpt-4o"

        if not provider:
            raise ValueError(
                "No complex LLM provider configured for this user. "
                "Open Settings -> LLM and set Complex Model Provider."
            )

        llm = GameMasterLLM(user, provider=provider, model_category="complex")

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
        )
        
        system_prompt = prompts.WORLD_GENERATION_SYSTEM_PROMPT
        if language:
            system_prompt += f"\n\nCRITICAL: You MUST generate all content (names, descriptions, teaser, plot, intro_text, walkthrough, quests) in {language}. Do not use any other language."
        
        award_requirement = ""
        if award_generation_enabled:
            award_requirement = f"\n\nAWARD SYSTEM:\n- Generate between {min_awards} and {max_awards} unique Awards that players can earn."
        else:
            award_requirement = "\n\nAWARD SYSTEM:\n- Do not generate any awards for this adventure."

        user_prompt = prompts.WORLD_GENERATION_USER_PROMPT_TEMPLATE.format(
            title=title, 
            original_prompt=original_prompt, 
            selected_tone=selected_tone or "Standard RPG",
            min_scenes=min_scenes, 
            max_scenes=max_scenes,
            award_requirement=award_requirement
        )

        
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
            # Keep imported/source manifest intact for reproducible resets.
            adventure.teaser = manifesto.teaser
            adventure.original_prompt = original_prompt
            if language:
                adventure.language = language
            if not adventure.origin_id:
                adventure.origin_id = manifesto.origin_id or template_id
            if not adventure.original_manifest:
                adventure.original_manifest = manifesto.model_dump()
            await db.commit()
            
        await WorldGenerator.apply_manifest(
            db, 
            template_id, 
            manifesto.model_dump(), 
            user=user if (generate_npc_images or generate_item_images or generate_scene_images) else None,
            gen_npc=generate_npc_images,
            gen_items=generate_item_images,
            gen_scenes=generate_scene_images,
            gen_protagonist_image=generate_scene_images,
            selected_image_styles=selected_image_styles,
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
        selected_image_styles: Optional[List[str]] = None,
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

        # Resolve Style Instructions
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
        
        # 0. Sync Quests and Narrative Meta
        if adventure:
            quests = manifest_dict.get("quests") or []
            for q in quests:
                if "status" not in q:
                    q["status"] = "open"
            adventure.quests = quests
            
            teaser = manifest_dict.get("teaser")
            if teaser:
                adventure.teaser = teaser
            
            # Narrative Meta
            adventure.plot = manifest_dict.get("plot") or adventure.plot
            adventure.rules = manifest_dict.get("rules") or adventure.rules
            adventure.intro_text = manifest_dict.get("intro_text") or adventure.intro_text
            adventure.walkthrough = manifest_dict.get("walkthrough") or adventure.walkthrough
            adventure.completed_condition = manifest_dict.get("completed_condition") or adventure.completed_condition
            adventure.gameover_condition = manifest_dict.get("gameover_condition") or adventure.gameover_condition
            
            # Flexible Time System
            if manifest_dict.get("time_system"):
                adventure.time_system = manifest_dict["time_system"]
            if manifest_dict.get("time_config"):
                adventure.time_config = manifest_dict["time_config"]
            
            # Optional Time Initialization (Convert to minutes since start if possible)
            # For now we just check if it's there; future logic can normalize this.
            if manifest_dict.get("start_time"):
                # Very simple heuristic: 08:00 -> 480 mins
                try:
                    h, m = map(int, manifest_dict["start_time"].split(':'))
                    adventure.starting_timestamp = h * 60 + m
                except:
                    pass
            
            awards = manifest_dict.get("awards") or []
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
                state.time_system = adventure.time_system
                state.time_config = adventure.time_config
            
            # Generate Adventure Cover if missing
            any_image_generation_enabled = bool(gen_scenes or gen_npc or gen_items or gen_protagonist_image)
            if not adventure.image_url and user and any_image_generation_enabled:
                await _publish_generation_status_with_callback(
                    db,
                    adventure,
                    "Painting Adventure Cover...",
                    status_callback=status_callback,
                )
                try:
                    cover_url = await MediaEngine.generate_adventure_cover(
                        title=adventure.title,
                        original_prompt=adventure.teaser or adventure.original_prompt,
                        adventure_id=template_id,
                        user_config={"t2i_settings": user.t2i_settings},
                        api_keys=user.encrypted_api_keys,
                        style_instruction=style_instruction
                    )
                    if cover_url:
                        adventure.image_url = cover_url
                except Exception as e:
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
                
                avatar.stats = prot.get("stats") or avatar.stats
                
                # We do NOT assign inventory/equipment directly here anymore, 
                # because they are populated during the object resolution loop below.
                # However, we clear them to ensure a fresh state if we are re-applying.
                avatar.inventory = []
                avatar.equipment = {
                    "Head": None, "Chest": None, "Arms": None, "Legs": None,
                    "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None, 
                    "Neck": None, "MainHand": None, "OffHand": None
                }

            # Unified Portrait Logic
            image_url = (existing_images or {}).get("PROTAGONIST") or prot.get("profile_image")
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
                    image_attempts += 1
                    try:
                        image_url = await asyncio.wait_for(
                            MediaEngine.generate_entity_image(
                                prompt,
                                template_id,
                                "PROTAGONIST",
                                "NPC",
                                {"t2i_settings": user.t2i_settings},
                                user.encrypted_api_keys,
                                style_instruction=style_instruction,
                            ),
                            timeout=_image_generation_timeout_seconds(),
                        )
                    except Exception as exc:
                        logger.warning("Protagonist image generation failed for %s: %s", template_id, exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                
                if not image_url:
                    # Fallback to high-quality placeholder
                    if not avatar.profile_image or not avatar.profile_image.startswith("/data/"):
                        image_url = await MediaEngine.generate_placeholder(
                            template_id, "PROTAGONIST", os.path.join(settings.DATA_DIR, "adventures", template_id),
                            category="AVATAR"
                        )
                    else:
                        image_url = avatar.profile_image
            
            avatar.profile_image = image_url
            
        # Persist Scenes
        scenes = manifest_dict.get("scenes", [])
        total_scenes = len(scenes)
        for scene_index, s in enumerate(scenes, start=1):
            if s["id"] in seen_scene_ids:
                continue
            seen_scene_ids.add(s["id"])
            
            image_url = (existing_images or {}).get(s["id"]) or s.get("image_url")
            if not image_url:
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
                        image_url = await asyncio.wait_for(
                            MediaEngine.generate_entity_image(
                                prompt,
                                template_id,
                                s['id'],
                                "SCENE",
                                {"t2i_settings": user.t2i_settings},
                                user.encrypted_api_keys,
                                style_instruction=style_instruction,
                            ),
                            timeout=_image_generation_timeout_seconds(),
                        )
                    except asyncio.TimeoutError as exc:
                        logger.warning("Scene image generation timed out for %s/%s: %s", template_id, s['id'], exc)
                        image_url = None
                    except Exception as exc:
                        logger.warning("Scene image generation failed for %s/%s: %s", template_id, s['id'], exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                
                if not image_url:
                    # Fallback to high-quality placeholder
                    image_url = await MediaEngine.generate_placeholder(
                        template_id, s["id"], os.path.join(settings.DATA_DIR, "adventures", template_id, "scenes"),
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
            
        # Persist NPCs
        npcs = manifest_dict.get("npcs", [])
        total_npcs = len(npcs)
        default_scene_id = scenes[0]["id"] if scenes else "START"
        for npc_index, n in enumerate(npcs, start=1):
            if n["id"] in seen_entity_ids:
                continue
            seen_entity_ids.add(n["id"])
            
            image_url = (existing_images or {}).get(n["id"]) or n.get("image_url")
            if not image_url:
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
                                user.encrypted_api_keys,
                                style_instruction=style_instruction,
                            ),
                            timeout=_image_generation_timeout_seconds(),
                        )
                    except asyncio.TimeoutError as exc:
                        logger.warning("NPC image generation timed out for %s/%s: %s", template_id, n['id'], exc)
                        image_url = None
                    except Exception as exc:
                        logger.warning("NPC image generation failed for %s/%s: %s", template_id, n['id'], exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                
                if not image_url:
                    # Fallback to high-quality placeholder for NPCs
                    image_url = await MediaEngine.generate_placeholder(
                        template_id, n["id"], os.path.join(settings.DATA_DIR, "adventures", template_id, "entities"),
                        category="NPC"
                    )

            db.add(WorldEntity(
                id=n["id"],
                template_id=template_id,
                entity_type="NPC",
                name=n["name"],
                description=n["description"],
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
            ))
            
        # Persist Objects & Collect for NPC Inventories
        objects = manifest_dict.get("objects", [])
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

        def _extract_numeric_stat(obj: Dict[str, Any], source_item: Dict[str, Any], *keys: str) -> Optional[int]:
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

        def _extract_numeric_effect(obj: Dict[str, Any], source_item: Dict[str, Any], *keys: str) -> Optional[int]:
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
            
            image_url = (existing_images or {}).get(o["id"]) or o.get("image_url")
            if not image_url:
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
                                user.encrypted_api_keys,
                                style_instruction=style_instruction,
                            ),
                            timeout=_image_generation_timeout_seconds(),
                        )
                    except Exception as exc:
                        logger.warning("Object image generation failed for %s/%s: %s", template_id, o['id'], exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                
                if not image_url:
                    # Fallback to high-quality placeholder for Items
                    image_url = await MediaEngine.generate_placeholder(
                        template_id, o["id"], os.path.join(settings.DATA_DIR, "adventures", template_id, "entities"),
                        category="ITEM"
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
            if stat_strength is not None:
                metadata_json["stat_modifier_strength"] = stat_strength
            if stat_dexterity is not None:
                metadata_json["stat_modifier_dexterity"] = stat_dexterity
            if stat_intelligence is not None:
                metadata_json["stat_modifier_intelligence"] = stat_intelligence
            if stat_wisdom is not None:
                metadata_json["stat_modifier_wisdom"] = stat_wisdom
            if stat_charisma is not None:
                metadata_json["stat_modifier_charisma"] = stat_charisma
            if stat_armor_class is not None:
                metadata_json["stat_modifier_armor_class"] = stat_armor_class

            if avatar and is_in_avatar_inv:
                if is_starting_inv:
                    # SQLAlchemy mutability: re-assign the list
                    avatar.inventory = list(avatar.inventory) + [item_data]
                if starting_slot:
                    # SQLAlchemy mutability: re-assign the dict
                    new_equip = dict(avatar.equipment)
                    new_equip[starting_slot] = item_data
                    avatar.equipment = new_equip

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
                    is_in_inventory=is_in_avatar_inv or is_in_npc_inv,
                    is_portable=o.get("is_portable", o.get("item_type") != "STATIC"),
                    combination_ingredients=o.get("combination_ingredients"),
                    reveals_item_id=o.get("reveals_item_id"),
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

        # Final Pass: Update NPC Inventories with resolved item data
        # We need to find the WorldEntity objects we just added to the session
        for npc_id, item_ids in npc_inventories.items():
            if not item_ids:
                continue
            
            # Find the NPC in the session's new objects
            for obj in db.new:
                if isinstance(obj, WorldEntity) and obj.id == npc_id and obj.entity_type == "NPC":
                    npc_inv = []
                    for iid in item_ids:
                        if iid in resolved_items:
                            npc_inv.append(resolved_items[iid])
                    obj.inventory = npc_inv
                    break

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
        if requested_image_generation and image_attempts > 0 and image_successes == 0:
            raise RuntimeError(
                "Image generation was enabled, but no images were produced. "
                "Check provider/model configuration, API keys, and provider availability."
            )
