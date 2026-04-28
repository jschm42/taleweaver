import logging
import asyncio
import os
from typing import List, Optional, Dict, Literal
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

class WorldExitSchema(BaseModel):
    from_scene_id: str
    to_scene_id: str
    label: str = Field(..., description="How to describe the transition, e.g., 'a narrow stone staircase'")
    is_locked: bool = False
    lock_description: Optional[str] = None

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

class QuestSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the quest, e.g., FIND_GOLDEN_KEY")
    title: str = Field(..., description="Short, descriptive title")
    description: str = Field(..., description="Narrative description of what needs to be done")
    goal: str = Field(..., description="Technical condition for completion (for GM reference)")
    impact: str = Field(..., description="How this affects the world when completed")
    exp_reward: int = Field(..., description="EXP awarded for completion (e.g., 50, 100, 250)")
    is_main: bool = Field(..., description="True if this quest is required to finish the adventure")
    status: str = Field("open", description="Current state: open, completed, failed")

class AwardTemplateSchema(BaseModel):
    key: str = Field(..., description="Unique identifier for the award, e.g., SLAYER_OF_RATS")
    title: str = Field(..., description="Visual name of the award")
    description: str = Field(..., description="Short description shown to the player")
    tier: Literal["bronze", "silver", "gold"] = Field(..., description="The rarity/tier of the award")
    requirement: str = Field(..., description="The specific rule/condition when the GM should grant this award")

class ProtagonistSchema(BaseModel):
    name: str = Field(..., description="The name of the player character.")
    role: str = Field(..., description="The professional or narrative role of the player, e.g. 'Royal Chef', 'Exiled Alchemist'.")
    description: str = Field(..., description="A detailed narrative description of the character's appearance and backstory.")
    starting_inventory: Optional[List[str]] = Field(None, description="List of object IDs to start in the player's pocket.")
    starting_equipment: Optional[Dict[str, str]] = Field(None, description="Mapping of slots (e.g. 'Hands', 'Head') to object IDs.")

class WorldManifesto(BaseModel):
    """
    The complete blueprint of the generated world.
    """
    protagonist: ProtagonistSchema
    teaser: str = Field(..., description="A short, atmospheric teaser text for the adventure, max 100 characters.")
    scenes: List[WorldSceneSchema]
    exits: List[WorldExitSchema]
    npcs: List[WorldEntitySchema]
    objects: List[WorldEntitySchema]
    quests: List[QuestSchema] = Field(default_factory=list)
    awards: List[AwardTemplateSchema] = Field(default_factory=list)
    
    # Optional Time Initialization
    start_date: Optional[str] = Field(None, description="Initial in-game date, e.g. '2026-04-17'")
    start_time: Optional[str] = Field(None, description="Initial in-game time, e.g. '08:00'")

class WorldGenerator:
    @staticmethod
    async def generate_world(
        db: AsyncSession, 
        user: User, 
        template_id: str, 
        title: str, 
        context: str,
        model: str = "gpt-4o", # default to a complex model
        provider: Optional[str] = None,
        generate_scene_images: bool = False,
        generate_npc_images: bool = False,
        generate_item_images: bool = False,
        min_scenes: int = 1,
        max_scenes: int = 5,
        award_generation_enabled: bool = True,
        min_awards: int = 3,
        max_awards: int = 5
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
            context_length=len(context or ""),
        )
        
        system_prompt = prompts.WORLD_GENERATION_SYSTEM_PROMPT
        
        award_requirement = ""
        if award_generation_enabled:
            award_requirement = f"\n\nAWARD SYSTEM:\n- Generate between {min_awards} and {max_awards} unique Awards that players can earn."
        else:
            award_requirement = "\n\nAWARD SYSTEM:\n- Do not generate any awards for this adventure."

        user_prompt = prompts.WORLD_GENERATION_USER_PROMPT_TEMPLATE.format(
            title=title, 
            context=context, 
            min_scenes=min_scenes, 
            max_scenes=max_scenes,
            award_requirement=award_requirement
        )
        
        # 1. Update Status
        adventure = await db.get(AdventureTemplate, template_id)
        if adventure:
            if adventure.creation_status == "Cancelled":
                raise GenerationCancelled("Generation stopped due to user cancellation.")
            adventure.creation_status = "Analyzing Story Idea..."
            log_structured_event(
                "adventure.generation.status",
                template_id=template_id,
                status=adventure.creation_status,
                phase="analysis",
            )
            await db.commit()

        manifesto: WorldManifesto = llm.execute_complex_task(
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
            if adventure.creation_status == "Cancelled":
                raise GenerationCancelled("Generation stopped due to user cancellation.")
            adventure.creation_status = "Building Scenes & Plot..."
            log_structured_event(
                "adventure.generation.status",
                template_id=template_id,
                status=adventure.creation_status,
                phase="apply_manifest",
            )
            # Keep imported/source manifest intact for reproducible resets.
            adventure.teaser = manifesto.teaser
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
            gen_protagonist_image=True # Always generate protagonist image
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
        existing_images: Optional[dict] = None
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
        
        # 0. Sync Quests
        if adventure:
            quests = manifest_dict.get("quests") or []
            for q in quests:
                if "status" not in q:
                    q["status"] = "open"
            adventure.quests = quests
            
            teaser = manifest_dict.get("teaser")
            if teaser:
                adventure.teaser = teaser
            
            awards = manifest_dict.get("awards") or []
            for a in awards:
                if "is_earned" not in a:
                    a["is_earned"] = False
            adventure.awards = awards
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

            raw_inv = prot.get("starting_inventory") or []
            starting_inv_ids = set()
            for item in raw_inv:
                item_id = item.get("id") if isinstance(item, dict) else item
                if item_id:
                    starting_inv_ids.add(item_id)

            if avatar:
                avatar.name = prot["name"]
                avatar.role = prot["role"]
                avatar.description = prot["description"]
                
                # Generate Portrait for Protagonist if requested
                image_url = (existing_images or {}).get("PROTAGONIST") or prot.get("profile_image")
                if not image_url:
                    if user and gen_protagonist_image:
                        await _publish_generation_status(
                            db,
                            adventure,
                            f"Envisioning Portrait for {prot['name']}...",
                        )
                        prompt = prompts.NPC_IMAGE_PROMPT_TEMPLATE.format(
                            name=prot['name'], description=prot['description']
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
                                ),
                                timeout=_image_generation_timeout_seconds(),
                            )
                        except asyncio.TimeoutError as exc:
                            logger.warning("Protagonist image generation timed out for %s: %s", template_id, exc)
                            image_url = None
                        except Exception as exc:
                            # Visual failures (e.g. provider moderation) must not abort world creation
                            logger.warning("Protagonist image generation failed for %s: %s", template_id, exc)
                            image_url = None
                        if image_url:
                            image_successes += 1
                    
                    if not image_url:
                        # Fallback to procedural SVG
                        image_url = await MediaEngine.generate_svg_placeholder(
                            template_id, "PROTAGONIST", os.path.join(settings.DATA_DIR, "adventures", template_id)
                        )
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
                    await _publish_generation_status(
                        db,
                        adventure,
                        f"Envisioning Scene {scene_index}/{total_scenes}: {s['name']}...",
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
                    # Fallback to procedural SVG
                    image_url = await MediaEngine.generate_svg_placeholder(
                        template_id, s["id"], os.path.join(settings.DATA_DIR, "adventures", template_id, "scenes")
                    )

            db.add(WorldScene(
                id=s["id"],
                template_id=template_id,
                label=s["name"],
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
        for npc_index, n in enumerate(npcs, start=1):
            if n["id"] in seen_entity_ids:
                continue
            seen_entity_ids.add(n["id"])
            
            image_url = (existing_images or {}).get(n["id"]) or n.get("image_url")
            if not image_url:
                if user and gen_npc:
                    await _publish_generation_status(
                        db,
                        adventure,
                        f"Envisioning Portrait {npc_index}/{total_npcs}: {n['name']}...",
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
                    # Fallback to mage silhouette for NPCs
                    image_url = await MediaEngine.generate_svg_placeholder(
                        template_id, n["id"], os.path.join(settings.DATA_DIR, "adventures", template_id, "entities"),
                        category="NPC"
                    )

            db.add(WorldEntity(
                id=n["id"],
                template_id=template_id,
                entity_type="NPC",
                name=n["name"],
                description=n["description"],
                current_scene_id=n["start_scene_id"],
                spatial_position=n.get("spatial_position"),
                image_url=image_url,
                npc_type=n.get("npc_type"),
                movement_type=n.get("movement_type"),
                hp=n.get("hp"),
                mana=n.get("mana"),
                stamina=n.get("stamina"),
                is_hidden=n.get("is_hidden", False),
            ))
            
        # Persist Objects
        objects = manifest_dict.get("objects", [])
        total_objects = len(objects)
        for object_index, o in enumerate(objects, start=1):
            if o["id"] in seen_entity_ids:
                continue
            seen_entity_ids.add(o["id"])
            
            image_url = (existing_images or {}).get(o["id"]) or o.get("image_url")
            if not image_url:
                if user and gen_items:
                    await _publish_generation_status(
                        db,
                        adventure,
                        f"Reifying Artifact {object_index}/{total_objects}: {o['name']}...",
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
                            ),
                            timeout=_image_generation_timeout_seconds(),
                        )
                    except asyncio.TimeoutError as exc:
                        logger.warning("Object image generation timed out for %s/%s: %s", template_id, o['id'], exc)
                        image_url = None
                    except Exception as exc:
                        logger.warning("Object image generation failed for %s/%s: %s", template_id, o['id'], exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                
                if not image_url:
                    # Items use RPG Awesome fallbacks in the frontend; set to None here.
                    image_url = None

            is_starting_inv = o["id"] in starting_inv_ids
            starting_slot = starting_equipped_ids.get(o["id"])
            is_in_inv = is_starting_inv or (starting_slot is not None)

            # Construct the Item Dict for Avatar storage
            item_data = {
                "id": o["id"],
                "name": o["name"],
                "description": o["description"],
                "image_url": image_url,
                "item_type": o.get("item_type", "PICKABLE"),
                "slot": (o.get("wearable_slots") or ["Hands"])[0] if o.get("item_type") == "WEARABLE" else "Hands"
            }

            if avatar and is_in_inv:
                if is_starting_inv:
                    new_inv = list(avatar.inventory)
                    new_inv.append(item_data)
                    avatar.inventory = new_inv
                if starting_slot:
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
                    current_scene_id="INVENTORY" if is_in_inv else o["start_scene_id"],
                    spatial_position=o.get("spatial_position"),
                    image_url=image_url,
                    item_type=o.get("item_type", "PICKABLE"),
                    wearable_slots=o.get("wearable_slots"),
                    is_hidden=o.get("is_hidden", False),
                    is_in_inventory=is_in_inv,
                    is_portable=o.get("is_portable", o.get("item_type") != "STATIC"),
                    combination_ingredients=o.get("combination_ingredients"),
                    reveals_item_id=o.get("reveals_item_id"),
                    state_comment=o.get("state_comment"),
                )
            )

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
