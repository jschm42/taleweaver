import json
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.llm_router import GameMasterLLM
from backend.models.user import User
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.models.adventure import Adventure

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

class WorldManifesto(BaseModel):
    """
    The complete blueprint of the generated world.
    """
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
        model: str = "gpt-4o" # default to a complex model
    ) -> None:
        """
        Calls the complex LLM to generate a coherent world structure based on the adventure theme.
        Persists the result to the WorldScene, WorldExit, and WorldEntity tables.
        """
        llm = GameMasterLLM(user)
        
        system_prompt = (
            "You are a master world-builder for a dark RPG. Your task is to generate a coherent, "
            "interconnected game world based on a provided Story Idea. "
            "The world must consist of unique scenes, connections (exits), NPCs, and interactable objects. "
            "IMPORTANT: Every NPC and Object must have a specific 'spatial_position' relative to items in the room "
            "(e.g., 'behind the bar counter', 'in the locked drawer'). "
            "Ensure the logic of the world is consistent: if a door is locked, mention why. "
            "Provide rich, atmospheric descriptions."
        )
        
        user_prompt = f"Adventure Title: {title}\nStory Idea: {context}\n\nGenerate at least 5 scenes with a complex network of exits and interesting entities."
        
        manifesto: WorldManifesto = llm.execute_complex_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=WorldManifesto,
            model=model
        )
        
        # Save manifest to Adventure for reset support
        adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
        adventure = adv_res.scalars().first()
        if adventure:
            adventure.original_manifest = manifesto.model_dump()
            
        await WorldGenerator.apply_manifest(db, adventure_id, manifesto.model_dump())
        await db.flush()

    @staticmethod
    async def apply_manifest(db: AsyncSession, adventure_id: str, manifest_dict: dict) -> None:
        """
        Populates (or re-populates) the world entities based on a manifest dictionary.
        Does NOT clear existing data; that should be handled by the caller.
        """
        # Persist Scenes
        for s in manifest_dict.get("scenes", []):
            db.add(WorldScene(
                id=s["id"],
                adventure_id=adventure_id,
                label=s["name"],
                description=s["description"]
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
            db.add(WorldEntity(
                id=n["id"],
                adventure_id=adventure_id,
                entity_type="NPC",
                name=n["name"],
                description=n["description"],
                current_scene_id=n["start_scene_id"],
                spatial_position=n.get("spatial_position")
            ))
            
        # Persist Objects
        for o in manifest_dict.get("objects", []):
            db.add(WorldEntity(
                id=o["id"],
                adventure_id=adventure_id,
                entity_type="OBJECT",
                name=o["name"],
                description=o["description"],
                current_scene_id=o["start_scene_id"],
                spatial_position=o.get("spatial_position")
            ))
