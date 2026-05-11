import logging

from backend.models.avatar import Avatar
from backend.models.session_state import SessionState

logger = logging.getLogger(__name__)

class QuestManager:
    """
    Deterministic quest evaluation engine that complements the LLM-driven mechanics pass.
    Ensures that technical achievements (e.g. equipping items) are correctly registered
    even if the LLM skips them in its structured response.
    """

    @staticmethod
    def evaluate_quests(avatar: Avatar, state: SessionState) -> list[str]:
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
            goal = quest.get("goal", "").lower()
            description = quest.get("description", "").lower()
            
            # 1. Equipment Checks
            if "equip" in goal or "equip" in description:
                if QuestManager._check_equipment_goal(avatar, goal) or QuestManager._check_equipment_goal(avatar, description):
                    completed_ids.append(qid)
                    continue

            # 2. Inventory Checks (Collect X)
            if "collect" in goal or "find" in goal or "get" in goal:
                if QuestManager._check_inventory_goal(avatar, goal):
                    completed_ids.append(qid)
                    continue
            
            # 3. Location Checks (Reach X)
            if "reach" in goal or "go to" in goal or "travel to" in goal:
                if QuestManager._check_location_goal(state, goal):
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
