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

        description = current_scene.description or ""
        decorative_suffix = ""
        decorative_list = current_scene.decorative_objects or []
        if isinstance(decorative_list, list) and decorative_list:
            decor_items = ", ".join(str(d).strip() for d in decorative_list if str(d).strip())
            if decor_items:
                decorative_suffix = f"DECORATIVE BACKGROUND DETAILS (STATIC, NON-INTERACTABLE): {decor_items}\n"

        detail = detail_level if detail_level in {"full", "concise"} else "full"
        if detail == "concise":
            short_desc = description.strip().replace("\n", " ")
            if len(short_desc) > 240:
                short_desc = short_desc[:240].rstrip() + "..."

            location_context = (
                f"\nCURRENT LOCATION: {current_scene.label} (ID: {current_scene.id})\n"
                f"SCENE SUMMARY: {short_desc}\n"
            )
            if decorative_suffix:
                location_context += decorative_suffix
        else:
            location_context = (
                f"\nCURRENT LOCATION:\n"
                f"NAME: {current_scene.label} (ID: {current_scene.id})\n"
                f"DESCRIPTION: {description}\n"
            )
            if decorative_suffix:
                location_context += decorative_suffix

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
                inv_str = ""
                if e.inventory:
                    items_list = []
                    for item in e.inventory:
                        if isinstance(item, dict):
                            item_name = item.get("name")
                            item_id = item.get("id")
                            if item_name and item_id:
                                items_list.append(f"{item_name} (ID: {item_id})")
                            elif item_name:
                                items_list.append(item_name)
                    if items_list:
                        inv_str = f" [Inventory: {', '.join(items_list)}]"
                defeated_str = " [DEFEATED]" if getattr(e, 'is_defeated', False) else ""
                desc_str = f" - Description: {e.description}" if (e.description and detail != "concise") else ""
                npcs.append(f"{e.name} (ID: {e.id}){stat_str}{pos_str}{goal_str}{char_str}{hidden_str}{defeated_str}{inv_str}{desc_str}")

            objects = []
            for e in entities:
                if e.entity_type == "OBJECT":
                    pos_str = f" (Position: {e.spatial_position})" if e.spatial_position else ""
                    hidden_str = " [HIDDEN]" if getattr(e, 'is_hidden', False) else ""
                    
                    item_type = str(e.item_type or "DEFAULT").upper()
                    type_str = f" [Type: {item_type}]"
                    
                    switch_details = ""
                    if item_type == "SWITCH":
                        metadata = e.metadata_json or {}
                        switch_cfg = metadata.get("switch") or {}
                        states = metadata.get("switch_states") or switch_cfg.get("states") or []
                        states_str = f" (Possible states: {', '.join(states)})" if states else ""

                        current_st = getattr(e, "current_switch_state", None)
                        if not current_st:
                            current_st = switch_cfg.get("initial_state") or metadata.get("switch_initial_state") or ""

                        current_str = f" [Current State: {current_st}]" if current_st else ""

                        # Build per-transition gate summary so the LLM knows requirements
                        transitions = metadata.get("switch_transitions") or switch_cfg.get("transitions") or []
                        gate_parts: list[str] = []
                        if isinstance(transitions, list):
                            for t in transitions:
                                if not isinstance(t, dict):
                                    continue
                                to_s = str(t.get("to") or t.get("to_state") or "").strip()
                                gates = t.get("gates") if isinstance(t.get("gates"), dict) else {}
                                req_code = str(gates.get("code") or t.get("code") or "").strip()
                                req_item = str(gates.get("item") or t.get("required_item") or "").strip()
                                req_rule = str(gates.get("rule") or t.get("required_rule") or "").strip()
                                reqs: list[str] = []
                                if req_code:
                                    reqs.append(f"code:{req_code}")
                                if req_item:
                                    reqs.append(f"item:{req_item}")
                                if req_rule:
                                    reqs.append(f"rule:{req_rule}")
                                if to_s and reqs:
                                    gate_parts.append(f"→{to_s}({','.join(reqs)})")
                        gate_str = f" [Gates: {' '.join(gate_parts)}]" if gate_parts else ""
                        switch_details = f"{states_str}{current_str}{gate_str}"

                    container_details = ""
                    if item_type == "CONTAINER":
                        # Lock info lives in metadata_json, not as direct entity columns
                        meta = dict(e.metadata_json or {})
                        entity_states = {}  # overrides not available here; use metadata baseline
                        code_to_unlock = str(meta.get("code_to_unlock") or "").strip()
                        item_to_unlock = str(meta.get("item_to_unlock") or "").strip()
                        rule_to_unlock = str(meta.get("rule_to_unlock") or "").strip()
                        is_locked = bool(code_to_unlock or item_to_unlock or rule_to_unlock)

                        lock_parts = []
                        if is_locked:
                            lock_parts.append("LOCKED")
                            if code_to_unlock:
                                lock_parts.append(f"code_to_unlock:{code_to_unlock}")
                            if item_to_unlock:
                                lock_parts.append(f"item_to_unlock:{item_to_unlock}")
                            if rule_to_unlock:
                                lock_parts.append(f"rule_to_unlock:{rule_to_unlock}")
                        lock_str = f" [{', '.join(lock_parts)}]" if lock_parts else " [UNLOCKED]"

                        cont_items = []
                        if e.inventory:
                            for item in e.inventory:
                                if isinstance(item, dict):
                                    item_name = item.get("name")
                                    item_id = item.get("id")
                                    if item_name and item_id:
                                        cont_items.append(f"{item_name} (ID: {item_id})")
                                    elif item_name:
                                        cont_items.append(item_name)
                                elif isinstance(item, str):
                                    cont_items.append(item)
                        cont_str = f" [Contains: {', '.join(cont_items)}]" if cont_items else " [Empty]"
                        container_details = f"{lock_str}{cont_str}"

                    readable_details = ""
                    if item_type == "READABLE":
                        metadata = e.metadata_json or {}
                        fmt = metadata.get("text_log_format") or getattr(e, "text_log_format", "DOCUMENT")
                        content = metadata.get("text_log_content") or ""
                        readable_details = f" [Format: {fmt}] [Readable text content: \"{content}\"]"

                    if detail == "concise":
                        objects.append(f"{e.name} (ID: {e.id}){type_str}{pos_str}{hidden_str}{switch_details}{container_details}{readable_details}")
                    else:
                        desc_str = f" - Description: {e.description}" if e.description else ""
                        objects.append(f"- {e.name} (ID: {e.id}):{type_str}{desc_str}{pos_str}{hidden_str}{switch_details}{container_details}{readable_details}")

            if npcs:
                if detail == "concise":
                    location_context += f"NPCS: {', '.join(npcs)}\n"
                else:
                    location_context += "PRESENT NPCs:\n" + "\n".join(f"- {npc}" for npc in npcs) + "\n"
            if objects:
                if detail == "concise":
                    location_context += f"OBJECTS: {', '.join(objects)}\n"
                else:
                    location_context += "INTERACTABLE OBJECTS:\n" + "\n".join(objects) + "\n"

        if exits:
            if detail == "concise":
                exit_list = []
                for e in exits:
                    status = "[LOCKED]" if e.is_locked else "[OPEN]"
                    status_parts = []
                    if e.is_locked:
                        if getattr(e, "code_to_unlock", None):
                            status_parts.append(f"code:{e.code_to_unlock}")
                        if getattr(e, "item_to_unlock", None):
                            status_parts.append(f"item:{e.item_to_unlock}")
                        if getattr(e, "rule_to_unlock", None):
                            status_parts.append(f"rule:{e.rule_to_unlock}")
                    status_req = f"({','.join(status_parts)})" if status_parts else ""
                    exit_list.append(f"{e.label}->{e.to_scene_id}{status}{status_req}")
                location_context += "EXITS: " + "; ".join(exit_list) + "\n"
            else:
                exit_list = []
                for e in exits:
                    status = "[LOCKED]" if e.is_locked else "[OPEN]"
                    desc_parts = []
                    if e.is_locked:
                        if e.lock_description:
                            desc_parts.append(e.lock_description)
                        if getattr(e, "code_to_unlock", None):
                            desc_parts.append(f"code_to_unlock: {e.code_to_unlock}")
                        if getattr(e, "item_to_unlock", None):
                            desc_parts.append(f"item_to_unlock: {e.item_to_unlock}")
                        if getattr(e, "rule_to_unlock", None):
                            desc_parts.append(f"rule_to_unlock: {e.rule_to_unlock}")
                    desc = f" ({', '.join(desc_parts)})" if desc_parts else ""
                    exit_list.append(f"- {e.label} to {e.to_scene_id} {status}{desc}")

                location_context += "AVAILABLE EXITS:\n" + "\n".join(exit_list) + "\n"

        return location_context

    @staticmethod
    def _build_hidden_entities_context(hidden_entities: Optional[list] = None) -> str:
        """
        Builds a GM-only context block for hidden NPCs/objects in the current scene,
        including their reveal rules so the GM knows when to make them visible.
        """
        if not hidden_entities:
            return ""

        lines = [
            "HIDDEN ENTITIES IN CURRENT SCENE (GM EYES ONLY — Do NOT reveal their existence to the player unless the reveal condition is met):"
        ]
        for e in hidden_entities:
            pos_str = f" (Position: {e.spatial_position})" if e.spatial_position else ""
            reveal_rule = getattr(e, 'reveal_rule', None) or ""
            entity_type = getattr(e, 'entity_type', 'ENTITY')
            if reveal_rule:
                rule_str = f" | Reveal condition: \"{reveal_rule}\""
            elif entity_type == "NPC":
                rule_str = " | Reveal condition: (default) reveal when the protagonist searches the scene OR when this NPC starts speaking"
            else:
                rule_str = " | Reveal condition: (default) reveal when the protagonist searches the scene"
            lines.append(f"- [{entity_type}] ID='{e.id}' Name='{e.name}'{pos_str}{rule_str}")

        lines.append(
            "REVEAL MECHANIC: When a reveal condition is met, reveal the entity by including its exact ID in 'updated_entities' with is_hidden=false (e.g. {\"entity_id\": \"ITEM_ID\", \"is_hidden\": false}) or in 'spawned_items'. "
            "This immediately makes the item/NPC visible to the player."
        )
        return "\n".join(lines) + "\n"

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
            inv_str = ""
            if npc.inventory:
                items_list = []
                for item in npc.inventory:
                    if isinstance(item, dict):
                        item_name = item.get("name")
                        item_id = item.get("id")
                        if item_name and item_id:
                            items_list.append(f"{item_name} (ID: {item_id})")
                        elif item_name:
                            items_list.append(item_name)
                if items_list:
                    inv_str = f", Inventory: {', '.join(items_list)}"

            lines.append(f"- {npc.name}: {desc}. Location: {scene_label}{pos_str}{goal_str}{char_str}{hidden_str}{inv_str}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def format_game_time(minutes: int | float, time_system: str = "calendar", time_config: Optional[dict] = None) -> str:
        """Translates total time into a formatted string based on the system (calendar, relative, or units)."""
        time_config = time_config or {}

        if time_system == "units":
            unit_name = time_config.get("unit_name") or time_config.get("unit") or "Units"
            initial_value = time_config.get("initial_value", 0)
            try:
                numeric_initial = float(initial_value)
            except (TypeError, ValueError):
                numeric_initial = 0.0
            total_val = numeric_initial + float(minutes or 0)
            formatted_val = f"{int(total_val)}" if total_val.is_integer() else f"{total_val:g}"
            return f"{formatted_val} {unit_name}"

        # Calendar with explicit start_datetime
        if time_config.get("start_datetime"):
            try:
                from datetime import datetime, timedelta
                raw_iso = str(time_config["start_datetime"]).strip().replace("Z", "+00:00")
                start_dt = datetime.fromisoformat(raw_iso)
                current_dt = start_dt + timedelta(minutes=float(minutes or 0))
                return current_dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        day_label = time_config.get("day_label", "Day")
        try:
            initial_day = int(time_config.get("initial_day", 1))
        except (TypeError, ValueError):
            initial_day = 1
        base_minutes_of_day = 8 * 60  # default 08:00
        
        # If there's a start_time in config, use it instead of 08:00
        if time_config.get("start_time"):
            try:
                h, m = map(int, str(time_config["start_time"]).split(':'))
                base_minutes_of_day = h * 60 + m
            except (TypeError, ValueError):
                pass

        total_minutes = int(base_minutes_of_day + (minutes or 0))
        days_passed = total_minutes // (24 * 60)
        rem_minutes = total_minutes % (24 * 60)
        current_hour = rem_minutes // 60
        current_minute = rem_minutes % 60
        
        if time_config.get("time_format") == "12h":
            h12 = current_hour % 12 or 12
            ampm = "PM" if current_hour >= 12 else "AM"
            return f"{day_label} {initial_day + days_passed}, {h12:02d}:{current_minute:02d} {ampm}"
        
        return f"{day_label} {initial_day + days_passed}, {current_hour:02d}:{current_minute:02d}"

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
        scene_map: Optional[dict[str, str]] = None,
        hidden_entities: Optional[list] = None,
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

        hidden_entities_context = MemoryManager._build_hidden_entities_context(
            hidden_entities=hidden_entities
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

        if hidden_entities_context:
            system_instruction += "\n" + hidden_entities_context
        
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
        scene_map: Optional[dict[str, str]] = None,
        hidden_entities: Optional[list] = None,
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
            scene_map=scene_map,
            hidden_entities=hidden_entities,
        )

        messages = [{"role": "system", "content": sys_prompt}]
        
        history_window = recent_history[-MemoryManager.MAX_HISTORY_LENGTH:]
        messages.extend(history_window)
        
        return messages

