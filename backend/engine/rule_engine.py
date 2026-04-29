from pydantic import BaseModel
from typing import List, Optional
from backend.models.avatar import Avatar

class GameOverException(Exception):
    """Thrown when the Avatar's HP falls to 0 or below during a rule evaluation."""
    pass


class InventoryItem(BaseModel):
    """
    A typed item acquired during gameplay.
    """
    id: Optional[str] = None # WorldEntity ID (if linked)
    name: str
    description: Optional[str] = None
    item_type: Optional[str] = None
    wearable_slots: Optional[List[str]] = None
    image_url: Optional[str] = None
    stat_modifier_strength: Optional[int] = None
    stat_modifier_dexterity: Optional[int] = None
    stat_modifier_intelligence: Optional[int] = None
    stat_modifier_wisdom: Optional[int] = None
    stat_modifier_charisma: Optional[int] = None
    stat_modifier_armor_class: Optional[int] = None

class EntityMovement(BaseModel):
    entity_id: str
    to_scene_id: Optional[str] = None
    to_spatial_position: Optional[str] = None

class ExitUpdate(BaseModel):
    from_scene_id: str
    to_scene_id: str
    is_locked: bool

class WorldEntityUpdate(BaseModel):
    """Used for changing an entity's name, description or visibility at runtime."""
    entity_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    spatial_position: Optional[str] = None
    is_hidden: Optional[bool] = None
    hp: Optional[int] = None
    mana: Optional[int] = None
    stamina: Optional[int] = None

class SkillCheckRequest(BaseModel):
    """Requested by the GM during the mechanics pass."""
    stat: str  # strength, dexterity, intelligence, wisdom, charisma, armor_class
    dc: int
    reason: str

class SkillCheckResult(BaseModel):
    """Filled by the backend after performing the roll."""
    stat: str
    dc: int
    roll: int
    modifier: int
    total: int
    success: bool
    reason: str


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
    
    # World State Updates
    moved_entities: Optional[List[EntityMovement]] = None
    updated_exits: Optional[List[ExitUpdate]] = None
    updated_entities: Optional[List[WorldEntityUpdate]] = None
    deleted_entities: Optional[List[str]] = None # List of IDs to remove
    
    # Skill Checks
    requested_skill_checks: Optional[List[SkillCheckRequest]] = None
    skill_check_results: Optional[List[SkillCheckResult]] = None
    
    # Time Management
    extra_time_minutes: int = 0 # Extra time this action takes (added to turn base)
    time_override_minutes: Optional[int] = None # Absolute override for in_game_time (minutes since start)
    start_datetime_override: Optional[str] = None # ISO string for start_datetime (shifts the entire calendar)
    
    # Quest System
    completed_quest_ids: Optional[List[str]] = None
    
    # Award System
    earned_award_keys: Optional[List[str]] = None

    # Status Updates
    game_over: bool = False
    game_completed: bool = False
    status_note: Optional[str] = None

# Maximum resource cap
RESOURCE_CAP = 200

# Maps status-effect names to per-turn resource deltas.
STATUS_EFFECT_TICKS: dict = {
    "Poisoned": {"hp": -5},
    "Burning": {"hp": -10},
    "Bleeding": {"hp": -3, "stamina": -2},
    "Regenerating": {"hp": 5},
    "Resting": {"stamina": 3, "mana": 3},
}

class RuleEngine:
    @staticmethod
    def apply_ticks(avatar: Avatar) -> list[str]:
        """
        Applies per-turn resource changes for all active status effects.
        Returns a list of messages describing what happened.
        """
        messages: list[str] = []
        for effect in list(avatar.status_effects or []):
            if effect not in STATUS_EFFECT_TICKS:
                continue

            deltas = STATUS_EFFECT_TICKS[effect]
            parts: list[str] = []

            if "hp" in deltas:
                avatar.hp = max(0, min(RESOURCE_CAP, avatar.hp + deltas["hp"]))
                parts.append(f"HP {deltas['hp']:+d}")

            if "stamina" in deltas:
                avatar.stamina = max(0, min(RESOURCE_CAP, avatar.stamina + deltas["stamina"]))
                parts.append(f"Stamina {deltas['stamina']:+d}")

            if "mana" in deltas:
                avatar.mana = max(0, min(RESOURCE_CAP, avatar.mana + deltas["mana"]))
                parts.append(f"Mana {deltas['mana']:+d}")

            if parts:
                messages.append(f"[{effect}] {', '.join(parts)}")

        return messages
    @staticmethod
    def apply_event(avatar: Avatar, event: GameEvent) -> str:
        """
        Applies a validated GameEvent struct to an Avatar model.
        Throws GameOverException if HP drops below or to 0.
        """
        avatar.hp += event.hp_change
        avatar.stamina += event.stamina_change
        avatar.mana += event.mana_change
        
        if event.game_over:
            avatar.hp = 0
            raise GameOverException(event.status_note or f"{avatar.name} has met their end.")

        if avatar.hp <= 0:
            avatar.hp = 0
            raise GameOverException(f"{avatar.name} has fallen! Game Over.")
            
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
            for item in event.new_inventory_items:
                item_dict = item.model_dump(exclude_none=True)
                new_inv.append(item_dict)
            avatar.inventory = new_inv
            
        return event.narrative_description
