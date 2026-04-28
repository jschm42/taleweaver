import json
from typing import List, Optional
from backend.models.avatar import Avatar
from backend.engine.stat_aggregator import calculate_total_stats
from backend.core import prompts

class MemoryManager:
    """
    Responsible for generating the contextual prompt that is sent to the LLM.
    Implements a sliding window memory algorithm to limit tokens.
    """
    
    MAX_HISTORY_LENGTH = 20 # Can be adjusted based on token limits

    @staticmethod
    def format_game_time(minutes: int) -> str:
        """Translates total minutes into a Day X, HH:MM format (Starts at Day 1, 08:00 AM)."""
        base_hour = 8
        total_hours = minutes // 60
        extra_minutes = minutes % 60
        
        current_hour = (base_hour + total_hours) % 24
        days_passed = (base_hour + total_hours) // 24
        
        return f"Day {1 + days_passed}, {current_hour:02d}:{extra_minutes:02d}"

    @staticmethod
    def build_system_prompt(
        avatar: Avatar, 
        world_context: str, 
        current_scene=None, 
        entities=None, 
        exits=None,
        in_game_time: int = 0,
        awards: Optional[List[dict]] = None
    ) -> str:
        """
        Builds the foundational system prompt using the pre-generated world integrity.
        """
        time_str = MemoryManager.format_game_time(in_game_time)
        total_stats = calculate_total_stats(avatar)
        
        character_sheet = {
            "name": avatar.name,
            "role": getattr(avatar, 'role', None),
            "description": getattr(avatar, 'description', None),
            "profile_image": getattr(avatar, 'profile_image', None),
            "hp": avatar.hp,
            "stamina": avatar.stamina,
            "mana": avatar.mana,
            "stats": total_stats,
            "equipment": avatar.equipment,
            "inventory": avatar.inventory,
            "status_effects": avatar.status_effects
        }
        
        location_context = ""
        if current_scene:
            location_context = (
                f"\nCURRENT LOCATION:\n"
                f"NAME: {current_scene.label} (ID: {current_scene.id})\n"
                f"DESCRIPTION: {current_scene.description}\n"
            )
            
            # Entities present here
            if entities:
                npcs = []
                for e in entities:
                    if e.entity_type == "NPC":
                        stats = []
                        if e.hp is not None: stats.append(f"HP: {e.hp}/{e.max_hp or e.hp}")
                        if e.mana is not None: stats.append(f"Mana: {e.mana}/{e.max_mana or e.mana}")
                        if e.stamina is not None: stats.append(f"Stamina: {e.stamina}/{e.max_stamina or e.stamina}")
                        
                        stat_str = f" [{', '.join(stats)}]" if stats else ""
                        pos_str = f" (Position: {e.spatial_position})" if e.spatial_position else ""
                        npcs.append(f"{e.name}{stat_str}{pos_str}")
                
                objects = [f"{e.name} (Position: {e.spatial_position})" if e.spatial_position else e.name for e in entities if e.entity_type == "OBJECT"]
                
                if npcs:
                    location_context += f"PRESENT NPCs: {', '.join(npcs)}\n"
                if objects:
                    location_context += f"INTERACTABLE OBJECTS: {', '.join(objects)}\n"
            
            # Exits from here
            if exits:
                exit_list = []
                for e in exits:
                    status = "[LOCKED]" if e.is_locked else "[OPEN]"
                    desc = f" ({e.lock_description})" if e.is_locked and e.lock_description else ""
                    exit_list.append(f"- {e.label} to {e.to_scene_id} {status}{desc}")
                
                location_context += "AVAILABLE EXITS:\n" + "\n".join(exit_list) + "\n"

        sheet_json = json.dumps(character_sheet, indent=2)
        
        system_instruction = prompts.GAME_MASTER_SYSTEM_PROMPT_TEMPLATE.format(
            world_context=world_context,
            time_str=time_str,
            location_context=location_context,
            sheet_json=sheet_json
        )
        return system_instruction

    @staticmethod
    def build_context(
        avatar: Avatar, 
        world_context: str, 
        recent_history: list[dict], 
        current_scene=None, 
        entities=None, 
        exits=None,
        in_game_time: int = 0,
        awards: Optional[List[dict]] = None
    ) -> list[dict]:
        """
        Combines the System Prompt with the sliding window of history and structured world state.
        """
        sys_prompt = MemoryManager.build_system_prompt(
            avatar, world_context, current_scene, entities, exits, in_game_time, awards
        )
        messages = [{"role": "system", "content": sys_prompt}]
        
        history_window = recent_history[-MemoryManager.MAX_HISTORY_LENGTH:]
        messages.extend(history_window)
        
        return messages
