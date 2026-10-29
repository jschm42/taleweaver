import json
import logging
from typing import Any, Optional

from backend.core import prompts
from backend.engine import location_context
from backend.engine.stat_aggregator import calculate_total_stats
from backend.models.avatar import Avatar

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Responsible for generating the contextual prompt that is sent to the LLM.
    Implements a sliding window memory algorithm to limit tokens.
    """

    MAX_HISTORY_LENGTH = 12  # Reduced for lower turn latency while keeping short-term context
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
        projected = {}
        for key, value in item.items():
            if key not in MemoryManager.INVENTORY_CORE_FIELDS:
                continue
            if not MemoryManager._is_meaningful(value):
                continue
            if (
                key.startswith("stat_modifier_")
                or key in ("hp_change", "mana_change", "stamina_change")
            ) and value == 0:
                continue
            projected[key] = value
        return (
            projected
            if projected
            else {"name": item.get("name") or item.get("id") or "Unknown Item"}
        )

    @staticmethod
    def _project_equipment(equipment: object) -> dict:
        if not isinstance(equipment, dict):
            return {}
        projected_eq: dict[str, Any] = {}
        for slot, item in equipment.items():
            if not item:
                continue
            if isinstance(item, dict):
                projected_eq[slot] = MemoryManager._project_inventory_item(item)
            elif isinstance(item, str) and item.strip():
                projected_eq[slot] = {"name": item.strip()}
        return projected_eq

    @staticmethod
    def _build_location_context(
        current_scene=None, entities=None, exits=None, detail_level: str = "full"
    ) -> str:
        return location_context.build_location_context(current_scene, entities, exits, detail_level)

    @staticmethod
    def _build_hidden_entities_context(
        hidden_entities: Optional[list] = None, for_narration: bool = False
    ) -> str:
        return location_context.build_hidden_entities_context(
            hidden_entities, for_narration=for_narration
        )

    @staticmethod
    def _build_world_npcs_context(
        other_npcs: Optional[list] = None, scene_map: Optional[dict[str, str]] = None
    ) -> str:
        return location_context.build_world_npcs_context(other_npcs, scene_map)

    @staticmethod
    def format_game_time(
        minutes: int | float, time_system: str = "calendar", time_config: Optional[dict] = None
    ) -> str:
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
            except (TypeError, ValueError, OverflowError):
                logger.debug(
                    "Invalid start_datetime %r; falling back to day clock.",
                    time_config["start_datetime"],
                )

        day_label = time_config.get("day_label", "Day")
        try:
            initial_day = int(time_config.get("initial_day", 1))
        except (TypeError, ValueError):
            initial_day = 1
        base_minutes_of_day = 8 * 60  # default 08:00

        # If there's a start_time in config, use it instead of 08:00
        if time_config.get("start_time"):
            try:
                h, m = map(int, str(time_config["start_time"]).split(":"))
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
    def build_static_prompt(
        world_context: str,
        plot: Optional[str] = None,
        rules: Optional[str] = None,
        walkthrough: Optional[str] = None,
        completed_condition: Optional[str] = None,
        gameover_condition: Optional[str] = None,
        is_adventure_generator: bool = False,
    ) -> str:
        """
        Builds the static GM system prompt (persona, adventure frame, core rules).
        It only changes on sequence changes, so it forms a cacheable prompt prefix.
        """
        static_prompt = prompts.GAME_MASTER_SYSTEM_PROMPT_TEMPLATE.format(
            plot=plot or "Explore and survive.",
            rules=rules or "Standard RPG rules apply.",
            walkthrough=walkthrough or "No specific walkthrough guidance available.",
            completed_condition=completed_condition or "No specific win condition set.",
            gameover_condition=gameover_condition or "No specific game over condition set.",
            world_context=world_context,
        )
        if is_adventure_generator:
            static_prompt += prompts.ADVENTURE_GENERATOR_INSTRUCTIONS
        return static_prompt

    @staticmethod
    def build_character_sheet(avatar: Avatar) -> dict:
        character_sheet = {
            "name": avatar.name,
            "role": getattr(avatar, "role", None),
            "description": getattr(avatar, "description", None),
            "hp": avatar.hp,
            "stamina": avatar.stamina,
            "mana": avatar.mana,
            "stats": calculate_total_stats(avatar),
            "equipment": MemoryManager._project_equipment(avatar.equipment),
            "inventory": [
                MemoryManager._project_inventory_item(i) for i in (avatar.inventory or [])
            ],
            "status_effects": avatar.status_effects,
        }
        return MemoryManager._prune_payload(character_sheet)

    @staticmethod
    def build_state_block(
        avatar: Avatar,
        current_scene=None,
        entities=None,
        exits=None,
        in_game_time: int = 0,
        time_system: str = "calendar",
        time_config: Optional[dict] = None,
        location_detail_level: str = "full",
        other_npcs: Optional[list] = None,
        scene_map: Optional[dict[str, str]] = None,
        hidden_entities: Optional[list] = None,
    ) -> str:
        """
        Builds the volatile CURRENT STATE block (time, location, NPCs, character sheet).
        It belongs in the latest user message so the system prompt stays cacheable.
        """
        return prompts.GM_STATE_BLOCK_TEMPLATE.format(
            time_str=MemoryManager.format_game_time(
                in_game_time, time_system=time_system, time_config=time_config
            ),
            location_context=location_context.build_location_context(
                current_scene, entities, exits, location_detail_level
            ),
            world_npcs_context=location_context.build_world_npcs_context(other_npcs, scene_map),
            hidden_entities_context=location_context.build_hidden_entities_context(
                hidden_entities, for_narration=location_detail_level == "full"
            ),
            sheet_json=MemoryManager._compact_json(MemoryManager.build_character_sheet(avatar)),
        )

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
        Builds a single self-contained system prompt (static part + CURRENT STATE).
        Used by single-shot callers; the turn pipeline uses the split builders instead.
        """
        _ = awards
        static_prompt = MemoryManager.build_static_prompt(
            world_context,
            plot=plot,
            rules=rules,
            walkthrough=walkthrough,
            completed_condition=completed_condition,
            gameover_condition=gameover_condition,
            is_adventure_generator=is_adventure_generator,
        )
        state_block = MemoryManager.build_state_block(
            avatar,
            current_scene=current_scene,
            entities=entities,
            exits=exits,
            in_game_time=in_game_time,
            time_system=time_system,
            time_config=time_config,
            location_detail_level=location_detail_level,
            other_npcs=other_npcs,
            scene_map=scene_map,
            hidden_entities=hidden_entities,
        )
        return f"{static_prompt}\n\n{state_block}"

    @staticmethod
    def build_context(
        avatar: Avatar,
        world_context: str,
        recent_history: list[dict],
        **kwargs: Any,
    ) -> list[dict]:
        """
        Combines the System Prompt with the sliding window of history and structured world state.
        """
        sys_prompt = MemoryManager.build_system_prompt(avatar, world_context, **kwargs)
        messages = [{"role": "system", "content": sys_prompt}]
        messages.extend(recent_history[-MemoryManager.MAX_HISTORY_LENGTH :])
        return messages
