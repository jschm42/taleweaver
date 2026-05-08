from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from typing import List, Optional, Literal

from backend.models.avatar import Avatar

class GameOverException(Exception):
    """Thrown when the Avatar's HP falls to 0 or below during a rule evaluation."""
    pass


class InventoryItem(BaseModel):
    """
    A typed item acquired during gameplay.
    """
    id: Optional[str] = Field(None, validation_alias=AliasChoices("id", "item_id", "entity_id")) # WorldEntity ID (if linked)
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

    # Consumable Effects (on-the-fly definition)
    hp_change: Optional[int] = None
    mana_change: Optional[int] = None
    stamina_change: Optional[int] = None

    # For spawned items
    spatial_position: Optional[str] = None

class EntityMovement(BaseModel):
    entity_id: str = Field(..., validation_alias=AliasChoices("entity_id", "id"))
    to_scene_id: Optional[str] = None
    to_spatial_position: Optional[str] = None

class ExitUpdate(BaseModel):
    from_scene_id: str
    to_scene_id: str
    is_locked: bool

class WorldEntityUpdate(BaseModel):
    """Used for changing an entity's name, description or visibility at runtime."""
    entity_id: str = Field(..., validation_alias=AliasChoices("entity_id", "id"))
    name: Optional[str] = None
    description: Optional[str] = None
    spatial_position: Optional[str] = None
    is_hidden: Optional[bool] = None
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    mana: Optional[int] = None
    stamina: Optional[int] = None
    stat_modifier_armor_class: Optional[int] = None
    is_attackable: Optional[bool] = None
    inventory: Optional[List[InventoryItem]] = None

class AttackRequest(BaseModel):
    """Requested by the GM to perform a combat action."""
    attacker_id: str # Usually "PLAYER" or NPC ID
    target_id: str # NPC ID or "PLAYER"
    hit_stat: str = "dexterity" # The stat used for the hit roll
    damage_dice: str = "1d6" # e.g. "1d8+2"
    reason: str

class AttackResult(BaseModel):
    """Detailed result of an attack."""
    attacker_id: str
    target_id: str
    hit_roll: int
    hit_modifier: int
    hit_total: int
    target_ac: int
    is_hit: bool
    damage_dice_str: str = "1d6"
    damage_rolls: List[int] = []
    damage_dice_total: int = 0
    damage_bonus: int = 0
    damage_total: int
    reason: str

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


class AdventureGenerationRequest(BaseModel):
    """
    Requested by the GM (NPC) to create a brand new adventure.
    """
    title: str
    prompt: str
    min_scenes: int = 1
    max_scenes: int = 5
    generate_scene_images: bool = False
    selected_image_styles: Optional[List[str]] = None
    selected_tone: Optional[str] = None
    min_awards: int = 3
    max_awards: int = 8
    award_generation_enabled: bool = False


class ToolResults(BaseModel):
    """Structured backend-filled tool outputs for adventure-generator interactions."""
    model_config = ConfigDict(extra="forbid")

    available_image_styles: Optional[List[str]] = None
    available_tones: Optional[List[str]] = None
    generation_success: Optional[bool] = None
    new_adventure_id: Optional[str] = None
    generation_error: Optional[str] = None


class AdventureGeneratorToolIntent(BaseModel):
    """Lightweight intent payload for adventure-generator tools in chat mode."""
    model_config = ConfigDict(extra="forbid")

    request_available_image_styles: bool = False
    request_available_tones: bool = False
    requested_adventure_generation: Optional[AdventureGenerationRequest] = None

    # Chat-mode progression intent (lightweight technical signals)
    hp_change: int = 0
    stamina_change: int = 0
    mana_change: int = 0
    new_inventory_items: List[InventoryItem] = []
    removed_inventory_item_ids: Optional[List[str]] = None
    updated_inventory_items: List[InventoryItem] = []
    spawned_items: Optional[List[InventoryItem]] = None
    completed_quest_ids: Optional[List[str]] = None
    earned_award_keys: Optional[List[str]] = None
    remember_notes: Optional[List[str]] = None
    forget_notes: Optional[List[str]] = None
    clear_notes: bool = False
    game_over: bool = False
    game_completed: bool = False
    status_note: Optional[str] = None

    tool_results: Optional[ToolResults] = None
    narrative_description: str = ""




class GameEvent(BaseModel):
    """
    Structured Output Schema for the LLM when in `strict_rules` mode.
    The LLM responds utilizing this strict schema.
    """
    narrative_description: str = ""
    hp_change: int = 0
    stamina_change: int = 0
    mana_change: int = 0
    new_status_effects: List[str] = []
    new_inventory_items: List[InventoryItem] = []
    removed_inventory_item_ids: Optional[List[str]] = Field(None, validation_alias=AliasChoices("removed_inventory_item_ids", "removed_item_ids", "removed_items"))
    updated_inventory_items: List[InventoryItem] = []
    spawned_items: Optional[List[InventoryItem]] = None
    
    # Mapping & Navigation
    new_scene_id: Optional[str] = Field(None, validation_alias=AliasChoices("new_scene_id", "scene_id")) # Unique ID for the new location (e.g. "FOREST_CLIFF")
    scene_label: Optional[str] = None  # Human readable name (e.g. "The Whispering Woods")
    exit_label: Optional[str] = None   # How the player got here (e.g. "ventured north")
    
    # Media
    image_prompt: Optional[str] = None # Short prompt for AI image generation of this scene
    
    # World State Updates
    moved_entities: Optional[List[EntityMovement]] = None
    updated_exits: Optional[List[ExitUpdate]] = None
    updated_entities: Optional[List[WorldEntityUpdate]] = None
    deleted_entities: Optional[List[str]] = None # List of IDs to remove
    
    # Skill Checks & Combat
    requested_skill_checks: Optional[List[SkillCheckRequest]] = None
    skill_check_results: Optional[List[SkillCheckResult]] = None
    
    requested_attacks: Optional[List[AttackRequest]] = None
    attack_results: Optional[List[AttackResult]] = None
    
    # Time Management
    extra_time_minutes: int = 0 # Extra time this action takes (added to turn base)
    time_override_minutes: Optional[int] = None # Absolute override for in_game_time (minutes since start)
    start_datetime_override: Optional[str] = None # ISO string for start_datetime (shifts the entire calendar)
    
    # Quest System
    completed_quest_ids: Optional[List[str]] = None
    
    # Award System
    earned_award_keys: Optional[List[str]] = None

    # Notes Tool
    remember_notes: Optional[List[str]] = None
    forget_notes: Optional[List[str]] = None
    clear_notes: bool = False

    # Status Updates
    game_over: bool = False
    game_completed: bool = False
    status_note: Optional[str] = None
    # Adventure Generator Tools
    request_available_image_styles: bool = False
    request_available_tones: bool = False
    requested_adventure_generation: Optional[AdventureGenerationRequest] = None
    tool_results: Optional[ToolResults] = None



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
            
        if event.updated_inventory_items:
            new_inv = list(avatar.inventory)
            modified = False
            for update in event.updated_inventory_items:
                if not update.id: continue
                for i, item in enumerate(new_inv):
                    if item.get("id") == update.id:
                        # Update fields
                        update_dict = update.model_dump(exclude_none=True)
                        new_inv[i] = {**item, **update_dict}
                        modified = True
                        break
            if modified:
                avatar.inventory = new_inv

        if event.removed_inventory_item_ids:
            new_inv = [item for item in list(avatar.inventory) if item.get("id") not in event.removed_inventory_item_ids]
            avatar.inventory = new_inv

        if event.new_inventory_items:
            # Reassign for SQLAlchemy state tracking; serialize Pydantic models to dicts
            new_inv = list(avatar.inventory)
            for item in event.new_inventory_items:
                item_dict = item.model_dump(exclude_none=True)
                
                # Check for existing ID to perform replacement/update
                found = False
                if item.id:
                    for i, existing in enumerate(new_inv):
                        if existing.get("id") == item.id:
                            new_inv[i] = item_dict
                            found = True
                            break
                
                if not found:
                    new_inv.append(item_dict)
            
            avatar.inventory = new_inv

        if event.spawned_items:
            new_inv = list(avatar.inventory)
            for item in event.spawned_items:
                item_dict = item.model_dump(exclude_none=True)
                
                # Check for existing ID to perform replacement/update
                found = False
                if item.id:
                    for i, existing in enumerate(new_inv):
                        if existing.get("id") == item.id:
                            new_inv[i] = item_dict
                            found = True
                            break
                
                if not found:
                    new_inv.append(item_dict)
            
            avatar.inventory = new_inv

        return event.narrative_description
