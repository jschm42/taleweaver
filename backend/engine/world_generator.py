import json
import logging
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.core.llm_router import GameMasterLLM
from backend.models.user import User
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.models.adventure import Adventure

logger = logging.getLogger(__name__)

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
            settings = user.llm_settings or {}
            provider = settings.get("preferred_provider", "openai")

        llm = GameMasterLLM(user, provider=provider)
        
        system_prompt = (
            "You are a master world-builder for a dark RPG. Your task is to generate a coherent, "
            "interconnected game world based on a provided Story Idea. "
            "The world must consist of unique scenes, connections (exits), NPCs, and interactable objects. "
            "IMPORTANT: Every NPC and Object must have a specific 'spatial_position' relative to items in the room "
            "(e.g., 'behind the bar counter', 'in the locked drawer'). "
            "Ensure the logic of the world is consistent: if a door is locked, mention why. "
            "For OBJECTS, assign a specific 'item_type':\n"
            "- CONSUMABLE: Food, potions, herbs.\n"
            "- WEARABLE: Armor, clothes, jewelry.\n"
            "- STATIC: Fountains, heavy alters, attached machines (set is_portable: false).\n"
            "- COMBINABLE: Parts of a machine, ingredients for a recipe.\n"
            "- PICKABLE: Standard items without special traits.\n"
            "- WEAPON / TOOL / KEY / READABLE: Self-explanatory.\n"
            "Use 'is_hidden: true' for objects revealed by combinations or searching.\n"
            "COMBINATIONS:\n"
            "- Use 'combination_ingredients: [item_id1, item_id2]' on a hidden result item to create a crafting recipe.\n"
            "- Use 'reveals_item_id: result_id' on a room object (e.g. a generator) and 'combination_ingredients: [fuel_id]' to allow using an item on it to reveal a new state.\n\n"
            "PROTAGONIST GENERATION:\n"
            "Generate a specialized player character (Protagonist). "
            "Define 'starting_inventory' and 'starting_equipment' using IDs from your objects list for items they already possess (e.g. a coin or their boots)."
        )
        
        user_prompt = f"Adventure Title: {title}\nStory Idea: {context}\n\nGenerate at least 5 scenes with a complex network of exits and interesting entities."
        
        # 1. Update Status
        adventure = await db.get(Adventure, adventure_id)
        if adventure:
            adventure.creation_status = "Analyzing Story Idea..."
            await db.commit()

        manifesto: WorldManifesto = llm.execute_complex_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=WorldManifesto,
            model=model
        )
        
        # 2. Update Status
        if adventure:
            adventure.creation_status = "Building Scenes & Plot..."
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
                    adventure.creation_status = f"Envisioning You: {prot['name']}..."
                    await db.commit()
                    prompt = f"Portrait of character {prot['name']}, {prot['role']}. {prot['description']}. Game attribute art style."
                    try:
                        image_url = await MediaEngine.generate_entity_image(
                            prompt,
                            adventure_id,
                            "PROTAGONIST",
                            "NPC",
                            {"t2i_settings": user.t2i_settings},
                            user.encrypted_api_keys,
                        )
                    except Exception as exc:
                        # Visual failures (e.g. provider moderation) must not abort world creation
                        logger.warning("Protagonist image generation failed for %s: %s", adventure_id, exc)
                        image_url = None
                    avatar.profile_image = image_url
            
        # Persist Scenes
        for s in manifest_dict.get("scenes", []):
            if s["id"] in seen_scene_ids:
                continue
            seen_scene_ids.add(s["id"])
            
            image_url = (existing_images or {}).get(s["id"])
            if not image_url and user and gen_scenes:
                if adventure:
                    adventure.creation_status = f"Envisioning Scene: {s['name']}..."
                    await db.commit()
                prompt = f"Atmospheric background: {s['name']}. {s['description']}. RPG visual novel style, high detail."
                try:
                    image_url = await MediaEngine.generate_scene_image(
                        prompt,
                        adventure_id,
                        {"t2i_settings": user.t2i_settings},
                        user.encrypted_api_keys,
                    )
                except Exception as exc:
                    logger.warning("Scene image generation failed for %s/%s: %s", adventure_id, s['id'], exc)
                    image_url = None

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
        for n in manifest_dict.get("npcs", []):
            if n["id"] in seen_entity_ids:
                continue
            seen_entity_ids.add(n["id"])
            
            image_url = (existing_images or {}).get(n["id"])
            if not image_url and user and gen_npc:
                if adventure:
                    adventure.creation_status = f"Envisioning Portrait: {n['name']}..."
                    await db.commit()
                prompt = f"Portrait of NPC {n['name']}. {n['description']}. Game attribute art style."
                try:
                    image_url = await MediaEngine.generate_entity_image(
                        prompt,
                        adventure_id,
                        n['id'],
                        "NPC",
                        {"t2i_settings": user.t2i_settings},
                        user.encrypted_api_keys,
                    )
                except Exception as exc:
                    logger.warning("NPC image generation failed for %s/%s: %s", adventure_id, n['id'], exc)
                    image_url = None

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
        for o in manifest_dict.get("objects", []):
            if o["id"] in seen_entity_ids:
                continue
            seen_entity_ids.add(o["id"])
            
            image_url = (existing_images or {}).get(o["id"])
            if not image_url and user and gen_items:
                if adventure:
                    adventure.creation_status = f"Envisioning Item: {o['name']}..."
                    await db.commit()
                prompt = f"Highly detailed item: {o['name']}. {o['description']}. Isolated on simple background, RPG asset style."
                try:
                    image_url = await MediaEngine.generate_entity_image(
                        prompt,
                        adventure_id,
                        o['id'],
                        "OBJECT",
                        {"t2i_settings": user.t2i_settings},
                        user.encrypted_api_keys,
                    )
                except Exception as exc:
                    logger.warning("Object image generation failed for %s/%s: %s", adventure_id, o['id'], exc)
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

            db.add(WorldEntity(
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
                # NEW FIELDS
                is_portable=o.get("is_portable", o.get("item_type") != "STATIC"),
                combination_ingredients=o.get("combination_ingredients"),
                reveals_item_id=o.get("reveals_item_id"),
                state_comment=o.get("state_comment")
            ))
