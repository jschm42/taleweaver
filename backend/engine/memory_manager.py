from typing import Optional, Union
import json

from backend.core import prompts
from backend.engine.stat_aggregator import calculate_total_stats
from backend.models.avatar import Avatar


class MemoryManager:
    """
    Responsible for generating the contextual prompt that is sent to the LLM.
    Implements a sliding window memory algorithm to limit tokens.
    """
    
    MAX_HISTORY_LENGTH = 12 # Reduced for lower turn latency while keeping short-term context
    INVENTORY_CORE_FIELDS = {
        "id",
        "name",
        "item_type",
        "wearable_slots",
        "hp_change",
        "mana_change",
        "stamina_change",
        "stat_modifier_strength",
        "stat_modifier_dexterity",
        "stat_modifier_intelligence",
        "stat_modifier_wisdom",
        "stat_modifier_charisma",
        "stat_modifier_armor_class",
    }

    @staticmethod
    def _is_meaningful(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, dict)):
            return bool(value)
        return True

    @staticmethod
    def _compact_json(payload: object) -> str:
        return json.dumps(payload, separators=(",", ":"))

    @staticmethod
    def _prune_payload(data: dict) -> dict:
        return {k: v for k, v in data.items() if MemoryManager._is_meaningful(v)}

    @staticmethod
    def _project_inventory_item(item: object) -> object:
        if not isinstance(item, dict):
            return item
        projected = {
            key: value
            for key, value in item.items()
            if key in MemoryManager.INVENTORY_CORE_FIELDS and MemoryManager._is_meaningful(value)
        }
        return projected if projected else {"name": item.get("name") or item.get("id") or "Unknown Item"}

    @staticmethod
    def _build_location_context(current_scene=None, entities=None, exits=None, detail_level: str = "full") -> str:
        if not current_scene:
            return ""

        detail = detail_level if detail_level in {"full", "concise"} else "full"
        if detail == "concise":
            description = (current_scene.description or "").strip().replace("\n", " ")
            if len(description) > 240:
                description = description[:240].rstrip() + "..."

            location_context = (
                f"\nCURRENT LOCATION: {current_scene.label} (ID: {current_scene.id})\n"
                f"SCENE SUMMARY: {description}\n"
            )
        else:
            location_context = (
                f"\nCURRENT LOCATION:\n"
                f"NAME: {current_scene.label} (ID: {current_scene.id})\n"
                f"DESCRIPTION: {current_scene.description}\n"
            )

        if entities:
            npcs = []
            for e in entities:
                if e.entity_type != "NPC":
                    continue
                stats = []
                if e.hp is not None:
                    stats.append(f"HP:{e.hp}/{e.max_hp or e.hp}")
                if e.mana is not None:
                    stats.append(f"Mana:{e.mana}/{e.max_mana or e.mana}")
                if e.stamina is not None:
                    stats.append(f"Stamina:{e.stamina}/{e.max_stamina or e.stamina}")

                stat_str = f" [{' '.join(stats)}]" if stats else ""
                pos_str = f" (Position: {e.spatial_position})" if e.spatial_position else ""
                goal_str = f" [Goal: {e.goal}]" if e.goal else ""
                char_str = f" [Character: {e.character}]" if e.character else ""
                hidden_str = " [HIDDEN]" if getattr(e, 'is_hidden', False) else ""
                npcs.append(f"{e.name}{stat_str}{pos_str}{goal_str}{char_str}{hidden_str}")

            objects = []
            for e in entities:
                if e.entity_type == "OBJECT":
                    pos_str = f" (Position: {e.spatial_position})" if e.spatial_position else ""
                    hidden_str = " [HIDDEN]" if getattr(e, 'is_hidden', False) else ""
                    objects.append(f"{e.name}{pos_str}{hidden_str}")

            if npcs:
                prefix = "NPCS" if detail == "concise" else "PRESENT NPCs"
                location_context += f"{prefix}: {', '.join(npcs)}\n"
            if objects:
                prefix = "OBJECTS" if detail == "concise" else "INTERACTABLE OBJECTS"
                location_context += f"{prefix}: {', '.join(objects)}\n"

        if exits:
            if detail == "concise":
                exit_list = []
                for e in exits:
                    status = "[LOCKED]" if e.is_locked else "[OPEN]"
                    exit_list.append(f"{e.label}->{e.to_scene_id}{status}")
                location_context += "EXITS: " + "; ".join(exit_list) + "\n"
            else:
                exit_list = []
                for e in exits:
                    status = "[LOCKED]" if e.is_locked else "[OPEN]"
                    desc = f" ({e.lock_description})" if e.is_locked and e.lock_description else ""
                    exit_list.append(f"- {e.label} to {e.to_scene_id} {status}{desc}")

                location_context += "AVAILABLE EXITS:\n" + "\n".join(exit_list) + "\n"

        return location_context

    @staticmethod
    def _build_world_npcs_context(other_npcs: Optional[list] = None, scene_map: Optional[dict[str, str]] = None) -> str:
        if not other_npcs:
            return ""

        lines = ["WORLD NPCS (INTERNAL GM META-INFORMATION - Do NOT reveal these locations or existence to the player unless justified):"]
        for npc in other_npcs:
            scene_label = scene_map.get(npc.current_scene_id, npc.current_scene_id) if scene_map else npc.current_scene_id
            pos_str = f", Position: {npc.spatial_position}" if npc.spatial_position else ""
            hidden_str = " [HIDDEN]" if getattr(npc, 'is_hidden', False) else ""
            desc = npc.description.strip()
            if desc.endswith("."):
                desc = desc[:-1]
            goal_str = f", Goal: {npc.goal}" if npc.goal else ""
            char_str = f", Character: {npc.character}" if npc.character else ""
            lines.append(f"- {npc.name}: {desc}. Location: {scene_label}{pos_str}{goal_str}{char_str}{hidden_str}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def format_game_time(minutes: int, time_system: str = "calendar", time_config: Optional[dict] = None) -> str:
        """Translates total minutes into a formatted string based on the system."""
        time_config = time_config or {}
        day_label = time_config.get("day_label", "Day")
        base_hour = 8
        
        # If there's a start_time in config, use it instead of 08:00
        if time_config.get("start_time"):
            try:
                h, m = map(int, time_config["start_time"].split(':'))
                base_hour = h
                # We could also use m here if we wanted to be precise
            except:
                pass

        total_hours = minutes // 60
        extra_minutes = minutes % 60
        
        current_hour = (base_hour + total_hours) % 24
        days_passed = (base_hour + total_hours) // 24
        
        if time_system == "relative":
            return f"{day_label} {1 + days_passed}, {current_hour:02d}:{extra_minutes:02d}"
        
        # Calendar mode is handled by the frontend mostly, 
        # but for the LLM prompt we provide a readable string.
        return f"Day {1 + days_passed}, {current_hour:02d}:{extra_minutes:02d}"

    @staticmethod
    def build_system_prompt(
        avatar: Avatar, 
        world_context: str, 
        current_scene=None, 
        entities=None, 
        exits=None,
        in_game_time: int = 0,
        awards: Optional[list[dict]] = None,
        plot: Optional[str] = None,
        rules: Optional[str] = None,
        walkthrough: Optional[str] = None,
        completed_condition: Optional[str] = None,
        gameover_condition: Optional[str] = None,
        time_system: str = "calendar",
        time_config: Optional[dict] = None,
        is_adventure_generator: bool = False,
        location_detail_level: str = "full",
        other_npcs: Optional[list] = None,
        scene_map: Optional[dict[str, str]] = None
    ) -> str:

        """
        Builds the foundational system prompt using the pre-generated world integrity.
        """
        time_str = MemoryManager.format_game_time(in_game_time, time_system=time_system, time_config=time_config)
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
            "inventory": [MemoryManager._project_inventory_item(i) for i in (avatar.inventory or [])],
            "status_effects": avatar.status_effects
        }
        character_sheet = MemoryManager._prune_payload(character_sheet)
        
        location_context = MemoryManager._build_location_context(
            current_scene=current_scene,
            entities=entities,
            exits=exits,
            detail_level=location_detail_level,
        )
        
        world_npcs_context = MemoryManager._build_world_npcs_context(
            other_npcs=other_npcs,
            scene_map=scene_map
        )

        sheet_json = MemoryManager._compact_json(character_sheet)
        
        system_instruction = prompts.GAME_MASTER_SYSTEM_PROMPT_TEMPLATE.format(
            plot=plot or "Explore and survive.",
            rules=rules or "Standard RPG rules apply.",
            walkthrough=walkthrough or "No specific walkthrough guidance available.",
            completed_condition=completed_condition or "No specific win condition set.",
            gameover_condition=gameover_condition or "No specific game over condition set.",
            world_context=world_context,
            time_str=time_str,
            location_context=location_context,
            world_npcs_context=world_npcs_context,
            sheet_json=sheet_json
        )
        
        if is_adventure_generator:
            system_instruction += prompts.ADVENTURE_GENERATOR_INSTRUCTIONS
            
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
        awards: Optional[list[dict]] = None,
        plot: Optional[str] = None,
        rules: Optional[str] = None,
        walkthrough: Optional[str] = None,
        completed_condition: Optional[str] = None,
        gameover_condition: Optional[str] = None,
        time_system: str = "calendar",
        time_config: Optional[dict] = None,
        is_adventure_generator: bool = False,
        location_detail_level: str = "full",
        other_npcs: Optional[list] = None,
        scene_map: Optional[dict[str, str]] = None
    ) -> list[dict]:

        """
        Combines the System Prompt with the sliding window of history and structured world state.
        """
        sys_prompt = MemoryManager.build_system_prompt(
            avatar, world_context, current_scene, entities, exits, in_game_time, awards,
            plot=plot, rules=rules, walkthrough=walkthrough,
            completed_condition=completed_condition, gameover_condition=gameover_condition,
            time_system=time_system, time_config=time_config,
            is_adventure_generator=is_adventure_generator,
            location_detail_level=location_detail_level,
            other_npcs=other_npcs,
            scene_map=scene_map
        )

        messages = [{"role": "system", "content": sys_prompt}]
        
        history_window = recent_history[-MemoryManager.MAX_HISTORY_LENGTH:]
        messages.extend(history_window)
        
        return messages

