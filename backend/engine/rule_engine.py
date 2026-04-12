from pydantic import BaseModel
from typing import List
from backend.models.avatar import Avatar

class GameOverException(Exception):
    """Thrown when the Avatar's HP falls to 0 or below during a rule evaluation."""
    pass

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
    new_inventory_items: List[dict] # dicts containing 'name', 'stat_modifiers', etc.

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
            # Reassign for SQLAlchemy state tracking
            new_inv = list(avatar.inventory)
            new_inv.extend(event.new_inventory_items)
            avatar.inventory = new_inv
            
        return event.narrative_description
