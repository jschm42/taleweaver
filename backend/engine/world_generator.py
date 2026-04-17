import logging
import asyncio
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.core.llm_router import GameMasterLLM
from backend.core.llm_logger import log_structured_event
from backend.models.user import User
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.models.adventure import Adventure
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

    provider = (t2i_settings.get("provider") or "").strip().lower()
    if not provider:
        raise ValueError("Image generation is enabled, but no image provider is configured.")

    needs_advanced_model = need_scene_images
    needs_simple_model = need_npc_images or need_item_images or need_protagonist_image

    if needs_advanced_model and not (t2i_settings.get("advanced_model") or "").strip():
        raise ValueError("Image generation is enabled for scenes, but advanced_model is missing.")

    if needs_simple_model and not (t2i_settings.get("simple_model") or "").strip():
        raise ValueError(
            "Image generation is enabled for portraits/items, but simple_model is missing."
        )

    if provider != "ollama":
        encrypted_api_keys = user.encrypted_api_keys or {}
        if provider not in encrypted_api_keys:
            raise ValueError(
                f"Image generation provider '{provider}' is configured, but its API key is missing."
            )


async def _publish_generation_status(db: AsyncSession, adventure: Optional[Adventure], status: str) -> None:
    """Publish live status text via the active session without committing mid-generation."""
    if not adventure:
        return
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
    scenes: List[WorldSceneSchema]
    exits: List[WorldExitSchema]
    npcs: List[WorldEntitySchema]
    objects: List[WorldEntitySchema]

class WorldGenerator:
    @staticmethod
    async def generate_world(
        db: AsyncSession, 
        user: User, 
        adventure_id: str, 
        title: str, 
        context: str,
        model: str = "gpt-4o", # default to a complex model
        provider: Optional[str] = None,
        generate_scene_images: bool = False,
        generate_npc_images: bool = False,
        generate_item_images: bool = False
    ) -> None:
        """
        Calls the complex LLM to generate a coherent world structure based on the adventure theme.
        Persists the result to the WorldScene, WorldExit, and WorldEntity tables.
        """
        # If no provider is given, use the one from user settings
        if not provider:
            llm_settings = user.llm_settings or {}
            provider = llm_settings.get("preferred_provider", "openai")

        llm = GameMasterLLM(user, provider=provider)

        log_structured_event(
            "adventure.generation.start",
            adventure_id=adventure_id,
            title=title,
            provider=provider,
            model=model,
            generate_scene_images=generate_scene_images,
            generate_npc_images=generate_npc_images,
            generate_item_images=generate_item_images,
            context_length=len(context or ""),
        )
        
        system_prompt = prompts.WORLD_GENERATION_SYSTEM_PROMPT
        
        user_prompt = prompts.WORLD_GENERATION_USER_PROMPT_TEMPLATE.format(
            title=title, context=context
        )
        
        # 1. Update Status
        adventure = await db.get(Adventure, adventure_id)
        if adventure:
            adventure.creation_status = "Analyzing Story Idea..."
            log_structured_event(
                "adventure.generation.status",
                adventure_id=adventure_id,
                status=adventure.creation_status,
                phase="analysis",
            )
            await db.commit()

        manifesto: WorldManifesto = llm.execute_complex_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=WorldManifesto,
            model=model,
            adventure_id=adventure_id,
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
            adventure_id=adventure_id,
            scene_count=len(manifesto.scenes),
            exit_count=len(manifesto.exits),
            npc_count=len(manifesto.npcs),
            object_count=len(manifesto.objects),
        )
        
        # 2. Update Status
        if adventure:
            adventure.creation_status = "Building Scenes & Plot..."
            log_structured_event(
                "adventure.generation.status",
                adventure_id=adventure_id,
                status=adventure.creation_status,
                phase="apply_manifest",
            )
            # Keep imported/source manifest intact for reproducible resets.
            if not adventure.original_manifest:
                adventure.original_manifest = manifesto.model_dump()
            await db.commit()
            
        await WorldGenerator.apply_manifest(
            db, 
            adventure_id, 
            manifesto.model_dump(), 
            user=user if (generate_npc_images or generate_item_images or generate_scene_images) else None,
            gen_npc=generate_npc_images,
            gen_items=generate_item_images,
            gen_scenes=generate_scene_images,
            gen_protagonist_image=True # Always generate protagonist image
        )
        log_structured_event(
            "adventure.generation.world_applied",
            adventure_id=adventure_id,
            scene_count=len(manifesto.scenes),
            exit_count=len(manifesto.exits),
            npc_count=len(manifesto.npcs),
            object_count=len(manifesto.objects),
        )
        await db.flush()

    @staticmethod
    async def apply_manifest(
        db: AsyncSession, 
        adventure_id: str, 
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
        adventure = await db.get(Adventure, adventure_id)

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
            adventure_id=adventure_id,
            scene_count=len(manifest_dict.get("scenes", [])),
            exit_count=len(manifest_dict.get("exits", [])),
            npc_count=len(manifest_dict.get("npcs", [])),
            object_count=len(manifest_dict.get("objects", [])),
        )
        
        # Preserve any existing images if caller didn't provide them
        if existing_images is None:
            existing_images = {}
            ent_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
            for e in ent_res.scalars().all():
                if e.image_url: existing_images[e.id] = e.image_url
            
            scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
            for s in scene_res.scalars().all():
                if s.image_url: existing_images[s.id] = s.image_url

        # Ensure idempotency: clear prior world objects for this adventure so re-runs don't attempt duplicate inserts
        await db.execute(delete(WorldScene).where(WorldScene.adventure_id == adventure_id))
        await db.execute(delete(WorldExit).where(WorldExit.adventure_id == adventure_id))
        await db.execute(delete(WorldEntity).where(WorldEntity.adventure_id == adventure_id))

        # Deduplication caches
        seen_scene_ids = set()
        seen_entity_ids = set()
        starting_equipped_ids: dict[str, str] = {}
        starting_inv_ids: set[str] = set()
        
        # 0. Sync Protagonist to Avatar
        prot = manifest_dict.get("protagonist", {})
        if prot and adventure:
            from backend.models.avatar import Avatar
            av_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id))
            avatar = av_res.scalars().first()
            
            # Map of ID -> Slot for starting equipment
            starting_equipped_ids = {v: k for k, v in (prot.get("starting_equipment") or {}).items()}
            starting_inv_ids = set(prot.get("starting_inventory") or [])

            if avatar:
                avatar.name = prot["name"]
                avatar.role = prot["role"]
                avatar.description = prot["description"]
                
                # Generate Portrait for Protagonist if requested
                image_url = (existing_images or {}).get("PROTAGONIST")
                if not image_url and user and gen_protagonist_image:
                    await _publish_generation_status(db, adventure, f"Envisioning You: {prot['name']}...")
                    prompt = prompts.PROTAGONIST_IMAGE_PROMPT_TEMPLATE.format(
                        name=prot['name'], role=prot['role'], description=prot['description']
                    )
                    image_attempts += 1
                    try:
                        image_url = await asyncio.wait_for(
                            MediaEngine.generate_entity_image(
                                prompt,
                                adventure_id,
                                "PROTAGONIST",
                                "NPC",
                                {"t2i_settings": user.t2i_settings},
                                user.encrypted_api_keys,
                            ),
                            timeout=_image_generation_timeout_seconds(),
                        )
                    except asyncio.TimeoutError as exc:
                        if _uses_ollama_t2i(user):
                            raise RuntimeError(
                                f"Ollama protagonist image generation timed out for adventure {adventure_id}."
                            ) from exc
                        logger.warning("Protagonist image generation timed out for %s", adventure_id)
                        image_url = None
                    except Exception as exc:
                        if _uses_ollama_t2i(user):
                            raise RuntimeError(
                                f"Ollama protagonist image generation failed for adventure {adventure_id}: {exc}"
                            ) from exc
                        # Visual failures (e.g. provider moderation) must not abort world creation
                        logger.warning("Protagonist image generation failed for %s: %s", adventure_id, exc)
                        image_url = None
                    if image_url:
                        image_successes += 1
                    avatar.profile_image = image_url
            
        # Persist Scenes
        scenes = manifest_dict.get("scenes", [])
        total_scenes = len(scenes)
        for scene_index, s in enumerate(scenes, start=1):
            if s["id"] in seen_scene_ids:
                continue
            seen_scene_ids.add(s["id"])
            
            image_url = (existing_images or {}).get(s["id"])
            if not image_url and user and gen_scenes:
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
                        MediaEngine.generate_scene_image(
                            prompt,
                            adventure_id,
                            {"t2i_settings": user.t2i_settings},
                            user.encrypted_api_keys,
                        ),
                        timeout=_image_generation_timeout_seconds(),
                    )
                except asyncio.TimeoutError as exc:
                    if _uses_ollama_t2i(user):
                        raise RuntimeError(
                            f"Ollama scene image generation timed out for adventure {adventure_id}/{s['id']}."
                        ) from exc
                    logger.warning("Scene image generation timed out for %s/%s", adventure_id, s['id'])
                    image_url = None
                except Exception as exc:
                    if _uses_ollama_t2i(user):
                        raise RuntimeError(
                            f"Ollama scene image generation failed for adventure {adventure_id}/{s['id']}: {exc}"
                        ) from exc
                    logger.warning("Scene image generation failed for %s/%s: %s", adventure_id, s['id'], exc)
                    image_url = None
                if image_url:
                    image_successes += 1

            db.add(WorldScene(
                id=s["id"],
                adventure_id=adventure_id,
                label=s["name"],
                description=s["description"],
                image_url=image_url
            ))
            
        # Persist Exits
        for e in manifest_dict.get("exits", []):
            db.add(WorldExit(
                adventure_id=adventure_id,
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
            
            image_url = (existing_images or {}).get(n["id"])
            if not image_url and user and gen_npc:
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
                            adventure_id,
                            n['id'],
                            "NPC",
                            {"t2i_settings": user.t2i_settings},
                            user.encrypted_api_keys,
                        ),
                        timeout=_image_generation_timeout_seconds(),
                    )
                except asyncio.TimeoutError as exc:
                    if _uses_ollama_t2i(user):
                        raise RuntimeError(
                            f"Ollama NPC image generation timed out for adventure {adventure_id}/{n['id']}."
                        ) from exc
                    logger.warning("NPC image generation timed out for %s/%s", adventure_id, n['id'])
                    image_url = None
                except Exception as exc:
                    if _uses_ollama_t2i(user):
                        raise RuntimeError(
                            f"Ollama NPC image generation failed for adventure {adventure_id}/{n['id']}: {exc}"
                        ) from exc
                    logger.warning("NPC image generation failed for %s/%s: %s", adventure_id, n['id'], exc)
                    image_url = None
                if image_url:
                    image_successes += 1

            db.add(WorldEntity(
                id=n["id"],
                adventure_id=adventure_id,
                entity_type="NPC",
                name=n["name"],
                description=n["description"],
                current_scene_id=n["start_scene_id"],
                spatial_position=n.get("spatial_position"),
                image_url=image_url
            ))
            
        # Persist Objects
        objects = manifest_dict.get("objects", [])
        total_objects = len(objects)
        for object_index, o in enumerate(objects, start=1):
            if o["id"] in seen_entity_ids:
                continue
            seen_entity_ids.add(o["id"])
            
            image_url = (existing_images or {}).get(o["id"])
            if not image_url and user and gen_items:
                await _publish_generation_status(
                    db,
                    adventure,
                    f"Envisioning Item {object_index}/{total_objects}: {o['name']}...",
                )
                prompt = prompts.ITEM_IMAGE_PROMPT_TEMPLATE.format(
                    name=o['name'], description=o['description']
                )
                image_attempts += 1
                try:
                    image_url = await asyncio.wait_for(
                        MediaEngine.generate_entity_image(
                            prompt,
                            adventure_id,
                            o['id'],
                            "OBJECT",
                            {"t2i_settings": user.t2i_settings},
                            user.encrypted_api_keys,
                        ),
                        timeout=_image_generation_timeout_seconds(),
                    )
                except asyncio.TimeoutError as exc:
                    if _uses_ollama_t2i(user):
                        raise RuntimeError(
                            f"Ollama object image generation timed out for adventure {adventure_id}/{o['id']}."
                        ) from exc
                    logger.warning("Object image generation timed out for %s/%s", adventure_id, o['id'])
                    image_url = None
                except Exception as exc:
                    if _uses_ollama_t2i(user):
                        raise RuntimeError(
                            f"Ollama object image generation failed for adventure {adventure_id}/{o['id']}: {exc}"
                        ) from exc
                    logger.warning("Object image generation failed for %s/%s: %s", adventure_id, o['id'], exc)
                    image_url = None
                if image_url:
                    image_successes += 1

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
                    adventure_id=adventure_id,
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
            adventure_id=adventure_id,
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
