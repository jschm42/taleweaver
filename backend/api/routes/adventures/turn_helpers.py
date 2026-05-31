from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.rule_engine import AdventureGeneratorToolIntent, GameEvent
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene


class TurnManagerLike(Protocol):
    state: Any
    adventure: Any
    user: Any

    def _get_gm_notes(self) -> list[str]:
        ...


class TurnProgressionBuilder:
    """Builds reduced progression payloads and progression events."""

    def __init__(
        self,
        manager: TurnManagerLike,
        *,
        gm_notes_prompt_max_items: int,
        gm_chat_rule_pass_npcs_max_items: int,
        gm_chat_prompt_template: str,
    ) -> None:
        self.manager = manager
        self.gm_notes_prompt_max_items = gm_notes_prompt_max_items
        self.gm_chat_rule_pass_npcs_max_items = gm_chat_rule_pass_npcs_max_items
        self.gm_chat_prompt_template = gm_chat_prompt_template

    @staticmethod
    def compact_json(payload: object) -> str:
        return json.dumps(payload, separators=(",", ":"))

    def build_mechanics_awards(self) -> list[dict]:
        awards = list(self.manager.adventure.awards or [])
        earned_awards = list(self.manager.user.earned_awards or [])
        earned_keys = {
            entry.get("key")
            for entry in earned_awards
            if entry.get("key") and (
                entry.get("template_id") == self.manager.adventure.id
                or entry.get("adventure_id") == self.manager.adventure.id
            )
        }
        return [a for a in awards if not a.get("key") or a.get("key") not in earned_keys]

    def build_chat_progression_quests(self) -> list[dict]:
        reduced_quests = []
        for quest in list(self.manager.state.quests or []):
            status = quest.get("status")
            if status == "completed":
                continue
            if not quest.get("id"):
                continue
            reduced_quests.append(
                {
                    "id": quest.get("id"),
                    "title": quest.get("title"),
                    "status": status,
                    "is_main": bool(quest.get("is_main")),
                }
            )
        return reduced_quests

    @staticmethod
    def build_chat_progression_awards(unearned_awards: list[dict]) -> list[dict]:
        reduced_awards = []
        for award in unearned_awards:
            key = award.get("key")
            if not key:
                continue
            reduced_awards.append(
                {
                    "key": key,
                    "title": award.get("title"),
                    "tier": award.get("tier"),
                }
            )
        return reduced_awards

    def build_chat_progression_npcs(self, entities: list[WorldEntity]) -> list[dict]:
        reduced_npcs = []
        for entity in entities:
            if (entity.entity_type or "").upper() != "NPC":
                continue
            reduced_npcs.append(
                {
                    "id": entity.id,
                    "name": entity.name,
                    "scene_id": entity.current_scene_id,
                    "position": entity.spatial_position,
                }
            )
            if len(reduced_npcs) >= self.gm_chat_rule_pass_npcs_max_items:
                break
        return reduced_npcs

    @staticmethod
    def build_chat_progression_scenes(session_scenes: list[WorldScene]) -> list[dict]:
        reduced_scenes = []
        for scene in (session_scenes or []):
            reduced_scenes.append(
                {
                    "id": scene.id,
                    "label": scene.label,
                }
            )
        return reduced_scenes

    @staticmethod
    def build_chat_progression_exits(exits: list[WorldExit]) -> list[dict]:
        reduced_exits = []
        for ex in exits:
            reduced_exits.append(
                {
                    "to_scene_id": ex.to_scene_id,
                    "label": ex.label,
                    "is_locked": ex.is_locked,
                    "code_to_unlock": getattr(ex, "code_to_unlock", None),
                    "item_to_unlock": getattr(ex, "item_to_unlock", None),
                    "rule_to_unlock": getattr(ex, "rule_to_unlock", None),
                }
            )
        return reduced_exits

    def build_chat_rule_pass_prompt(
        self,
        quests: list[dict],
        awards: list[dict],
        npcs: list[dict],
        scenes: list[dict],
        exits: list[dict],
    ) -> str:
        notes = self.manager._get_gm_notes()
        if len(notes) > self.gm_notes_prompt_max_items:
            notes = notes[-self.gm_notes_prompt_max_items :]

        current_scene_label = "Unknown"
        if self.manager.state and self.manager.state.current_scene_id:
            for scene in scenes:
                if scene.get("id") == self.manager.state.current_scene_id:
                    current_scene_label = scene.get("label") or "Unknown"
                    break

        return self.gm_chat_prompt_template.format(
            quests_json=self.compact_json(quests),
            awards_json=self.compact_json(awards),
            npcs_json=self.compact_json(npcs),
            scenes_json=self.compact_json(scenes),
            exits_json=self.compact_json(exits),
            notes_json=self.compact_json(notes),
            current_scene_id=self.manager.state.current_scene_id,
            current_scene_label=current_scene_label,
        )

    @staticmethod
    def build_progression_event(intent: AdventureGeneratorToolIntent) -> GameEvent:
        return GameEvent(
            narrative_description=intent.narrative_description or "",
            hp_change=intent.hp_change,
            stamina_change=intent.stamina_change,
            mana_change=intent.mana_change,
            new_status_effects=intent.new_status_effects or [],
            new_inventory_items=intent.new_inventory_items or [],
            removed_inventory_item_ids=intent.removed_inventory_item_ids,
            updated_inventory_items=intent.updated_inventory_items or [],
            spawned_items=intent.spawned_items,
            completed_quest_ids=intent.completed_quest_ids,
            earned_award_keys=intent.earned_award_keys,
            remember_notes=intent.remember_notes,
            forget_notes=intent.forget_notes,
            clear_notes=bool(intent.clear_notes),
            game_over=bool(intent.game_over),
            game_completed=bool(intent.game_completed),
            status_note=intent.status_note,
            new_scene_id=intent.new_scene_id,
            exit_label=intent.exit_label,
            moved_entities=intent.moved_entities,
            updated_entities=intent.updated_entities,
            deleted_entities=intent.deleted_entities,
            extra_time_minutes=intent.extra_time_minutes,
        )


class TurnSessionStateHelper:
    """Encapsulates session notes and terminal epilogue flags handling."""

    def __init__(
        self,
        manager: TurnManagerLike,
        *,
        gm_notes_state_key: str,
        gm_notes_max_items: int,
        terminal_epilogue_state_key: str,
    ) -> None:
        self.manager = manager
        self.gm_notes_state_key = gm_notes_state_key
        self.gm_notes_max_items = gm_notes_max_items
        self.terminal_epilogue_state_key = terminal_epilogue_state_key

    def get_gm_notes(self) -> list[str]:
        exit_states = self.manager.state.exit_states or {}
        notes = exit_states.get(self.gm_notes_state_key)
        if not isinstance(notes, list):
            return []
        return [str(n).strip() for n in notes if str(n).strip()]

    def get_terminal_epilogue_state(self) -> dict[str, bool]:
        exit_states = self.manager.state.exit_states or {}
        epilogue_state = exit_states.get(self.terminal_epilogue_state_key) or {}
        if not isinstance(epilogue_state, dict):
            epilogue_state = {}
        return {
            "completed_sent": bool(epilogue_state.get("completed_sent")),
            "game_over_sent": bool(epilogue_state.get("game_over_sent")),
        }

    def terminal_status_flags(self) -> tuple[bool, bool]:
        if not self.manager.state or not self.manager.state.session:
            return False, False
        status = self.manager.state.session.status
        epilogue_state = self.get_terminal_epilogue_state()
        pending = (status == "completed" and not epilogue_state["completed_sent"]) or (
            status == "game_over" and not epilogue_state["game_over_sent"]
        )
        input_locked = status == "game_over" and epilogue_state["game_over_sent"]
        return pending, input_locked

    def is_terminal_epilogue_pending(self) -> bool:
        pending, _ = self.terminal_status_flags()
        return pending

    def is_input_locked(self) -> bool:
        _, locked = self.terminal_status_flags()
        return locked

    def set_terminal_epilogue_sent(self, status: str, sent: bool = True) -> None:
        if not self.manager.state:
            return
        epilogue_state = self.get_terminal_epilogue_state()
        if status == "completed":
            epilogue_state["completed_sent"] = sent
        elif status == "game_over":
            epilogue_state["game_over_sent"] = sent

        exit_states = dict(self.manager.state.exit_states or {})
        exit_states[self.terminal_epilogue_state_key] = epilogue_state
        self.manager.state.exit_states = exit_states
        flag_modified(self.manager.state, "exit_states")

    def build_terminal_flags_payload(self) -> dict[str, Any]:
        pending, input_locked = self.terminal_status_flags()
        return {
            "game_over": (self.manager.state.session.status == "game_over")
            if self.manager.state and self.manager.state.session
            else False,
            "game_completed": (self.manager.state.session.status == "completed")
            if self.manager.state and self.manager.state.session
            else False,
            "status_note": self.manager.state.session.status_note
            if self.manager.state and self.manager.state.session
            else None,
            "input_locked": input_locked,
            "pending_terminal_epilogue": pending,
        }

    def apply_gm_notes_update(
        self,
        remember_notes: list[str] | None,
        forget_notes: list[str] | None,
        clear_notes: bool,
    ) -> None:
        existing = self.get_gm_notes()
        if clear_notes:
            existing = []

        forget_set = {
            str(note).strip().lower()
            for note in (forget_notes or [])
            if str(note).strip()
        }
        if forget_set:
            existing = [n for n in existing if n.strip().lower() not in forget_set]

        for note in (remember_notes or []):
            normalized = str(note).strip()
            if not normalized:
                continue
            if any(n.strip().lower() == normalized.lower() for n in existing):
                continue
            existing.append(normalized)

        if len(existing) > self.gm_notes_max_items:
            existing = existing[-self.gm_notes_max_items :]

        exit_states = dict(self.manager.state.exit_states or {})
        if existing:
            exit_states[self.gm_notes_state_key] = existing
        else:
            exit_states.pop(self.gm_notes_state_key, None)
        self.manager.state.exit_states = exit_states
        flag_modified(self.manager.state, "exit_states")

    def build_gm_notes_prompt_block(self) -> str:
        notes = self.get_gm_notes()
        if not notes:
            return "\n\nSESSION NOTES:\n- none"
        lines = "\n".join(f"- {note}" for note in notes)
        return "\n\nSESSION NOTES:\n" + lines


class TurnCombatStateHelper:
    """Encapsulates combat state persistence and log appends."""

    def __init__(self, manager: TurnManagerLike) -> None:
        self.manager = manager

    def read_combat_state(self) -> dict[str, Any]:
        states = self.manager.state.entity_states or {}
        combat = states.get("__combat__")
        if isinstance(combat, dict):
            return combat
        return {}

    def is_combat_active(self) -> bool:
        combat = self.read_combat_state()
        return bool(combat.get("active"))

    def has_combat_phase(self) -> bool:
        combat = self.read_combat_state()
        return bool(combat.get("active") or combat.get("loot_pending") or combat.get("outcome"))

    def set_combat_state(self, combat: dict[str, Any]) -> None:
        states = dict(self.manager.state.entity_states or {})
        states["__combat__"] = combat
        self.manager.state.entity_states = states
        self.manager.state.combat_json = combat
        flag_modified(self.manager.state, "entity_states")

    def append_combat_log(self, combat: dict[str, Any], text: str, entry_type: str = "log") -> None:
        logs = list(combat.get("log") or [])
        logs.append(
            {
                "round": combat.get("round", 1),
                "type": entry_type,
                "text": text,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        combat["log"] = logs[-80:]
