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
    def build_system_prompt(avatar: Avatar, world_context: str, world_map=None) -> str:
        """
        Builds the foundational system prompt, injecting the character's live sheet
        and the discovered world map to ensure spatial consistency.
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
        
        location_context = ""
        if world_map:
            current = world_map.current_scene_id
            nodes = world_map.nodes or {}
            edges = world_map.edges or []
            
            node_meta = nodes.get(current, {})
            location_context = f"\nPLAYER LOCATION: {node_meta.get('label', current)} (ID: {current})\n"
            location_context += f"LOCATION DESCRIPTION: {node_meta.get('description', 'Unexplored')}\n"
            
            # Briefly list known exits from here
            exits = [e.get('label') or e.get('to') for e in edges if e.get('from') == current]
            if exits:
                location_context += f"KNOWN EXITS: {', '.join(exits)}\n"

        sheet_json = json.dumps(character_sheet, indent=2)
        
        system_instruction = (
            "You are the Gamemaster (GM) of an AI Text Adventure RPG. "
            "You dynamically generate world narratives, resolve choices, and act as NPCs. "
            f"The world context/setting is:\n{world_context}\n\n"
            f"{location_context}\n"
            "Below is the REAL-TIME character sheet of the player. "
            "You MUST consider these stats, equipment, and HP in all your narratives:\n"
            f"{sheet_json}\n\n"
            "Respond organically. If a player attempts an impossible or extremely risky action, define a challenge rating."
        )
        return system_instruction

    @staticmethod
    def build_context(avatar: Avatar, world_context: str, recent_history: list[dict], world_map=None) -> list[dict]:
        """
        Combines the System Prompt with the sliding window of conversational history and map data.
        """
        messages = [
            {"role": "system", "content": MemoryManager.build_system_prompt(avatar, world_context, world_map)}
        ]
        
        # Sliding window logic
        history_window = recent_history[-MemoryManager.MAX_HISTORY_LENGTH:]
        messages.extend(history_window)
        
        return messages
