import logging
from typing import Any, Optional

from backend.engine.hard_rule_evaluator import HardRuleEvaluator
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState

logger = logging.getLogger(__name__)


class QuestManager:
    """
    Deterministic quest evaluation engine that complements the LLM-driven mechanics pass.
    Evaluates both structured hard rules (required item, required scene, required defeated NPC,
    scripting guards) and heuristic keyword goals.
    """

    @classmethod
    def evaluate_quests(
        cls,
        avatar: Avatar,
        state: SessionState,
        new_inventory_items: Optional[list[Any]] = None,
        new_scene_id: Optional[str] = None,
        updated_entities: Optional[list[Any]] = None,
        script_context: Optional[Any] = None,
    ) -> list[str]:
        """
        Evaluates current unresolved quests against the current game state.
        Returns a list of quest IDs that have just been completed.
        """
        if not state.quests:
            return []

        completed_ids = []
        terminal_statuses = {"completed", "failed", "cancelled", "abandoned"}
        open_quests = [
            q
            for q in state.quests
            if str(q.get("status") or "").lower() not in terminal_statuses
        ]

        for quest in open_quests:
            qid = quest.get("id")
            if not qid:
                continue

            # 1. Deterministic Hard Rules with Scripting Guard
            if HardRuleEvaluator.has_hard_rules(quest):
                is_met, _ = HardRuleEvaluator.evaluate_hard_rules(
                    quest,
                    avatar,
                    state,
                    new_inventory_items=new_inventory_items,
                    new_scene_id=new_scene_id,
                    updated_entities=updated_entities,
                    script_context=script_context,
                )
                if is_met:
                    completed_ids.append(qid)
                continue

            # 2. Heuristic Soft Goal Evaluation Fallback
            goal = quest.get("goal", "").lower()
            description = quest.get("description", "").lower()

            # Equipment Checks
            if "equip" in goal or "equip" in description:
                if cls._check_equipment_goal(avatar, goal) or cls._check_equipment_goal(
                    avatar, description
                ):
                    completed_ids.append(qid)
                    continue

            # Inventory Checks (Collect X)
            if "collect" in goal or "find" in goal or "get" in goal:
                if cls._check_inventory_goal(avatar, goal):
                    completed_ids.append(qid)
                    continue

            # Location Checks (Reach X)
            if "reach" in goal or "go to" in goal or "travel to" in goal:
                if cls._check_location_goal(state, goal):
                    completed_ids.append(qid)
                    continue

        return completed_ids

    @staticmethod
    def _check_equipment_goal(avatar: Avatar, text: str) -> bool:
        """
        Checks if specific equipment slots are filled based on keywords in text.
        Example: "Equip items in the Head, Chest, and Hands slots"
        """
        slots_to_check = []
        if "head" in text: slots_to_check.append("head")
        if "chest" in text: slots_to_check.append("chest")
        if "hands" in text: slots_to_check.append("hands")
        if "feet" in text: slots_to_check.append("feet")
        if "legs" in text: slots_to_check.append("legs")
        if "mainhand" in text or "main hand" in text or "weapon" in text: slots_to_check.append("mainhand")
        if "offhand" in text or "off hand" in text or "shield" in text: slots_to_check.append("offhand")
        if "neck" in text or "amulet" in text or "necklace" in text: slots_to_check.append("neck")
        
        if not slots_to_check:
            return False
            
        equipment = avatar.equipment or {}
        equipment_lower = {str(key).lower(): value for key, value in equipment.items()}
        for slot in slots_to_check:
            if not equipment_lower.get(slot):
                return False
        
        return True

    @staticmethod
    def _check_inventory_goal(avatar: Avatar, text: str) -> bool:
        """
        Checks if specific items are in inventory.
        """
        inventory = avatar.inventory or []
        # Simple heuristic: extract nouns or specific item names
        # For now, we look for matches of item names in the text
        for item in inventory:
            iname = item.get("name", "").lower()
            if iname and iname in text:
                return True
        return False

    @staticmethod
    def _check_location_goal(_state: SessionState, _text: str) -> bool:
        """
        Checks if the current scene matches a target mentioned in the text.
        """
        # This requires knowing the scene label/name
        # current_scene_id is what we have. 
        # We'd need to fetch the scene label to compare.
        # For now, return False until we have a better way to map ID to Name here.
        return False

