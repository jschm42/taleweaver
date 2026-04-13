from pydantic import BaseModel
from typing import List, Optional
from backend.models.avatar import Avatar

class GameOverException(Exception):
    """Thrown when the Avatar's HP falls to 0 or below during a rule evaluation."""
    pass


class InventoryItem(BaseModel):
    """
    A typed item acquired during gameplay.
    Using a strict Pydantic model instead of raw dict ensures OpenAI structured
    output accepts the schema (requires additionalProperties: false on all objects).
    """
    name: str
    description: Optional[str] = None
    stat_modifier_strength: Optional[int] = None
    stat_modifier_endurance: Optional[int] = None
    stat_modifier_agility: Optional[int] = None
    stat_modifier_intelligence: Optional[int] = None
    stat_modifier_charisma: Optional[int] = None


class GameEvent(BaseModel):
    """
    Structured Output Schema for the LLM when in `strict_rules` mode.
    The LLM responds utilizing this strict schema.
    """
    narrative_description: str
    hp_change: int
    stamina_change: int
    mana_change: int
    new_status_effects: List[str]
    new_inventory_items: List[InventoryItem]
    
    # Mapping & Navigation
    new_scene_id: Optional[str] = None # Unique ID for the new location (e.g. "FOREST_CLIFF")
    scene_label: Optional[str] = None  # Human readable name (e.g. "The Whispering Woods")
    exit_label: Optional[str] = None   # How the player got here (e.g. "ventured north")
    
    # Media
    image_prompt: Optional[str] = None # Short prompt for AI image generation of this scene

class RuleEngine:
    @staticmethod
    def apply_event(avatar: Avatar, event: GameEvent) -> str:
        """
        Applies a validated GameEvent struct to an Avatar model.
        Throws GameOverException if HP drops below or to 0.
        """
        avatar.hp += event.hp_change
        avatar.stamina += event.stamina_change
        avatar.mana += event.mana_change
        
        if avatar.hp <= 0:
            avatar.hp = 0
            raise GameOverException(f"{avatar.name} has died! Game Over.")
            
        if avatar.stamina < 0: avatar.stamina = 0
        if avatar.mana < 0: avatar.mana = 0
        
        if event.new_status_effects:
            # Prevent duplicates
            current_effects = set(avatar.status_effects)
            current_effects.update(event.new_status_effects)
            avatar.status_effects = list(current_effects)
            
        if event.new_inventory_items:
            # Reassign for SQLAlchemy state tracking; serialize Pydantic models to dicts
            new_inv = list(avatar.inventory)
            new_inv.extend([item.model_dump(exclude_none=True) for item in event.new_inventory_items])
            avatar.inventory = new_inv
            
        return event.narrative_description
