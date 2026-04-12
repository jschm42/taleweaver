import json
from backend.models.avatar import Avatar
from backend.engine.stat_aggregator import calculate_total_stats

class MemoryManager:
    """
    Responsible for generating the contextual prompt that is sent to the LLM.
    Implements a sliding window memory algorithm to limit tokens.
    """
    
    MAX_HISTORY_LENGTH = 20 # Can be adjusted based on token limits

    @staticmethod
    def build_system_prompt(avatar: Avatar, world_context: str) -> str:
        """
        Builds the foundational system prompt, injecting the character's live sheet.
        """
        total_stats = calculate_total_stats(avatar)
        
        character_sheet = {
            "name": avatar.name,
            "hp": avatar.hp,
            "stamina": avatar.stamina,
            "mana": avatar.mana,
            "stats": total_stats,
            "equipment": avatar.equipment,
            "inventory": avatar.inventory,
            "status_effects": avatar.status_effects
        }
        
        sheet_json = json.dumps(character_sheet, indent=2)
        
        system_instruction = (
            "You are the Gamemaster (GM) of an AI Text Adventure RPG. "
            "You dynamically generate world narratives, resolve choices, and act as NPCs. "
            f"The world context/setting is:\n{world_context}\n\n"
            "Below is the REAL-TIME character sheet of the player. "
            "You MUST consider these stats, equipent, and HP in all your narratives:\n"
            f"{sheet_json}\n\n"
            "Respond organically. If a player attempts an impossible or extremely risky action, define a challenge rating."
        )
        return system_instruction

    @staticmethod
    def build_context(avatar: Avatar, world_context: str, recent_history: list[dict]) -> list[dict]:
        """
        Combines the System Prompt with the sliding window of conversational history.
        `recent_history` should be a list of litellm compatible dicts: {"role": "user"/"assistant", "content": ...}
        """
        messages = [
            {"role": "system", "content": MemoryManager.build_system_prompt(avatar, world_context)}
        ]
        
        # Sliding window logic
        # Slice only the last MAX_HISTORY_LENGTH messages to prevent max token errors
        history_window = recent_history[-MemoryManager.MAX_HISTORY_LENGTH:]
        messages.extend(history_window)
        
        return messages
