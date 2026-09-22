"""
Script execution context and transactional proxy models for TaleWeaver.

Encapsulates all runtime state reading and isolates all mutations
within a declarative ScriptChangeset.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ScriptChangeset:
    """Collected mutations produced during script execution."""
    player_hp_change: int = 0
    player_mana_change: int = 0
    player_stamina_change: int = 0
    player_new_items: list[dict[str, Any]] = field(default_factory=list)
    player_removed_item_ids: list[str] = field(default_factory=list)
    player_status_effects_add: list[str] = field(default_factory=list)
    player_status_effects_remove: list[str] = field(default_factory=list)

    teleport_scene_id: Optional[str] = None
    entity_movements: list[dict[str, Any]] = field(default_factory=list)
    entity_updates: list[dict[str, Any]] = field(default_factory=list)
    exit_updates: list[dict[str, Any]] = field(default_factory=list)

    narrative_messages: list[str] = field(default_factory=list)
    rejected_actions: list[str] = field(default_factory=list)
    new_memories: list[dict[str, Any]] = field(default_factory=list)

    completed_quest_ids: list[str] = field(default_factory=list)
    failed_quest_ids: list[str] = field(default_factory=list)
    granted_award_keys: list[str] = field(default_factory=list)

    var_updates: dict[str, Any] = field(default_factory=dict)
    game_completed: bool = False
    game_over: bool = False
    status_note: Optional[str] = None
    completed_condition_override: Optional[str] = None
    gameover_condition_override: Optional[str] = None


class PlayerProxy:
    """Safe proxy for inspecting and mutating the player character."""

    def __init__(self, avatar_data: dict[str, Any], changeset: ScriptChangeset):
        self._avatar = avatar_data
        self._changeset = changeset

    @property
    def hp(self) -> int:
        return int(self._avatar.get("hp", 100)) + self._changeset.player_hp_change

    @property
    def mana(self) -> int:
        return int(self._avatar.get("mana", 50)) + self._changeset.player_mana_change

    @property
    def stamina(self) -> int:
        return int(self._avatar.get("stamina", 100)) + self._changeset.player_stamina_change

    @property
    def name(self) -> str:
        return str(self._avatar.get("name", "Protagonist"))

    def modify_hp(self, delta: int) -> None:
        self._changeset.player_hp_change += int(delta)

    def modify_mana(self, delta: int) -> None:
        self._changeset.player_mana_change += int(delta)

    def modify_stamina(self, delta: int) -> None:
        self._changeset.player_stamina_change += int(delta)

    def give_item(self, item_id: str, name: Optional[str] = None, description: Optional[str] = None) -> None:
        self._changeset.player_new_items.append({
            "id": item_id,
            "name": name or item_id.replace("_", " ").title(),
            "description": description or ""
        })

    def remove_item(self, item_id: str) -> None:
        if item_id not in self._changeset.player_removed_item_ids:
            self._changeset.player_removed_item_ids.append(item_id)

    def has_item(self, item_id: str) -> bool:
        if item_id in self._changeset.player_removed_item_ids:
            return False
        for item in self._changeset.player_new_items:
            if item.get("id") == item_id:
                return True
        current_inv = self._avatar.get("inventory") or []
        for it in current_inv:
            if isinstance(it, dict) and it.get("id") == item_id:
                return True
            elif isinstance(it, str) and it == item_id:
                return True
        return False

    def add_status_effect(self, effect_name: str) -> None:
        if effect_name not in self._changeset.player_status_effects_add:
            self._changeset.player_status_effects_add.append(effect_name)

    def remove_status_effect(self, effect_name: str) -> None:
        if effect_name not in self._changeset.player_status_effects_remove:
            self._changeset.player_status_effects_remove.append(effect_name)

    def has_status_effect(self, effect_name: str) -> bool:
        if effect_name in self._changeset.player_status_effects_remove:
            return False
        if effect_name in self._changeset.player_status_effects_add:
            return True
        return effect_name in (self._avatar.get("status_effects") or [])


class SceneProxy:
    """Safe proxy for scene inspection and transitions."""

    def __init__(self, current_scene_id: str, changeset: ScriptChangeset):
        self._current_scene_id = current_scene_id
        self._changeset = changeset

    @property
    def id(self) -> str:
        return self._changeset.teleport_scene_id or self._current_scene_id

    def teleport(self, target_scene_id: str) -> None:
        self._changeset.teleport_scene_id = target_scene_id


class ExitProxy:
    """Safe proxy for exit queries and lock/unlock mutations."""

    def __init__(self, exit_states: dict[str, Any], changeset: ScriptChangeset):
        self._exit_states = exit_states
        self._changeset = changeset

    def _key(self, from_scene_id: str, to_scene_id: str) -> str:
        return f"{from_scene_id}:{to_scene_id}"

    def is_locked(self, from_scene_id: str, to_scene_id: str) -> bool:
        k = self._key(from_scene_id, to_scene_id)
        # Check changeset overrides first
        for update in reversed(self._changeset.exit_updates):
            if update.get("from_scene_id") == from_scene_id and update.get("to_scene_id") == to_scene_id:
                return bool(update.get("is_locked", False))
        # Check session exit states
        st = self._exit_states.get(k, {})
        return bool(st.get("is_locked", False))

    def unlock(self, from_scene_id: str, to_scene_id: str) -> None:
        self._changeset.exit_updates.append({
            "from_scene_id": from_scene_id,
            "to_scene_id": to_scene_id,
            "is_locked": False
        })

    def lock(self, from_scene_id: str, to_scene_id: str, reason: Optional[str] = None) -> None:
        self._changeset.exit_updates.append({
            "from_scene_id": from_scene_id,
            "to_scene_id": to_scene_id,
            "is_locked": True,
            "lock_description": reason or "The passage is barred."
        })


class EntityProxy:
    """Base proxy for a world entity (NPC or Object)."""

    def __init__(self, entity_id: str, entity_data: dict[str, Any], changeset: ScriptChangeset):
        self._id = entity_id
        self._data = entity_data
        self._changeset = changeset

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return str(self._data.get("name", self._id))

    @property
    def current_scene_id(self) -> str:
        for move in reversed(self._changeset.entity_movements):
            if move.get("entity_id") == self._id:
                return str(move.get("to_scene_id"))
        return str(self._data.get("current_scene_id", ""))

    @property
    def is_hidden(self) -> bool:
        for upd in reversed(self._changeset.entity_updates):
            if upd.get("entity_id") == self._id and "is_hidden" in upd:
                return bool(upd["is_hidden"])
        return bool(self._data.get("is_hidden", False))

    def set_hidden(self, hidden: bool) -> None:
        self._changeset.entity_updates.append({
            "entity_id": self._id,
            "is_hidden": bool(hidden)
        })


class NPCProxy(EntityProxy):
    """Safe proxy for Non-Player Characters."""

    @property
    def hp(self) -> int:
        for upd in reversed(self._changeset.entity_updates):
            if upd.get("entity_id") == self._id and "hp" in upd:
                return int(upd["hp"])
        return int(self._data.get("hp", 50))

    @hp.setter
    def hp(self, val: int) -> None:
        self._changeset.entity_updates.append({
            "entity_id": self._id,
            "hp": max(0, int(val))
        })

    @property
    def is_defeated(self) -> bool:
        for upd in reversed(self._changeset.entity_updates):
            if upd.get("entity_id") == self._id and "is_defeated" in upd:
                return bool(upd["is_defeated"])
        return bool(self._data.get("is_defeated", False))

    @is_defeated.setter
    def is_defeated(self, val: bool) -> None:
        self._changeset.entity_updates.append({
            "entity_id": self._id,
            "is_defeated": bool(val)
        })

    def move_to(self, to_scene_id: str, spatial_position: Optional[str] = None) -> None:
        self._changeset.entity_movements.append({
            "entity_id": self._id,
            "to_scene_id": to_scene_id,
            "to_spatial_position": spatial_position or self._data.get("spatial_position", "")
        })

    def modify_hp(self, delta: int) -> None:
        new_hp = max(0, self.hp + int(delta))
        self.hp = new_hp


class ObjectProxy(EntityProxy):
    """Safe proxy for world objects, switches, and containers."""

    @property
    def switch_state(self) -> Optional[str]:
        for upd in reversed(self._changeset.entity_updates):
            if upd.get("entity_id") == self._id and "switch_state" in upd:
                return str(upd["switch_state"])
        return self._data.get("switch_state")

    def set_state(self, state: str) -> None:
        self._changeset.entity_updates.append({
            "entity_id": self._id,
            "switch_state": str(state)
        })

    @property
    def is_locked(self) -> bool:
        for upd in reversed(self._changeset.entity_updates):
            if upd.get("entity_id") == self._id and "locked" in upd:
                return bool(upd["locked"])
        return bool(self._data.get("locked", False) or self._data.get("is_locked", False))

    def unlock(self) -> None:
        self._changeset.entity_updates.append({
            "entity_id": self._id,
            "locked": False
        })

    def lock(self) -> None:
        self._changeset.entity_updates.append({
            "entity_id": self._id,
            "locked": True
        })


class EntityManagerProxy:
    """Access point for querying NPCs or objects."""

    def __init__(self, entities: dict[str, dict[str, Any]], changeset: ScriptChangeset, proxy_cls: type[EntityProxy]):
        self._entities = entities
        self._changeset = changeset
        self._proxy_cls = proxy_cls

    def get(self, entity_id: str) -> EntityProxy:
        data = self._entities.get(entity_id, {"id": entity_id})
        return self._proxy_cls(entity_id, data, self._changeset)

    def exists(self, entity_id: str) -> bool:
        return entity_id in self._entities


class VarsProxy:
    """Safe proxy for persistent story variables and custom flags."""

    def __init__(self, initial_vars: dict[str, Any], changeset: ScriptChangeset):
        self._vars = dict(initial_vars)
        self._changeset = changeset

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._changeset.var_updates:
            return self._changeset.var_updates[key]
        return self._vars.get(key, default)

    def set(self, key: str, val: Any) -> None:
        self._changeset.var_updates[key] = val

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, val: Any) -> None:
        self.set(key, val)


class StoryProxy:
    """Safe proxy for narrative messages and action rejections."""

    def __init__(self, changeset: ScriptChangeset):
        self._changeset = changeset

    def narrate(self, message: str) -> None:
        self._changeset.narrative_messages.append(str(message).strip())

    def reject_action(self, reason: str) -> None:
        self._changeset.rejected_actions.append(str(reason).strip())


class MemoriesProxy:
    """Safe proxy for world memories."""

    def __init__(self, changeset: ScriptChangeset):
        self._changeset = changeset

    def add(self, description: str, scope: str = "global", emotion: str = "neutral") -> None:
        self._changeset.new_memories.append({
            "description": str(description).strip(),
            "scope": scope if scope in ("local", "global") else "global",
            "emotion": emotion if emotion in ("positive", "negative", "neutral") else "neutral",
        })


class GameProxy:
    """Safe proxy for game outcome and victory/defeat criteria."""

    def __init__(self, changeset: ScriptChangeset):
        self._changeset = changeset

    def win(self, reason: Optional[str] = None) -> None:
        self._changeset.game_completed = True
        self._changeset.status_note = reason or "Victory has been achieved!"

    def game_over(self, reason: Optional[str] = None) -> None:
        self._changeset.game_over = True
        self._changeset.status_note = reason or "Game Over."

    def set_completed_condition(self, condition: str) -> None:
        self._changeset.completed_condition_override = str(condition).strip()

    def set_gameover_condition(self, condition: str) -> None:
        self._changeset.gameover_condition_override = str(condition).strip()


class QuestsProxy:
    """Safe proxy for quest state."""

    def __init__(self, quests: list[dict[str, Any]], changeset: ScriptChangeset):
        self._quests = {q.get("id"): q for q in quests if isinstance(q, dict) and q.get("id")}
        self._changeset = changeset

    def complete(self, quest_id: str) -> None:
        if quest_id not in self._changeset.completed_quest_ids:
            self._changeset.completed_quest_ids.append(quest_id)

    def fail(self, quest_id: str) -> None:
        if quest_id not in self._changeset.failed_quest_ids:
            self._changeset.failed_quest_ids.append(quest_id)

    def is_completed(self, quest_id: str) -> bool:
        if quest_id in self._changeset.completed_quest_ids:
            return True
        q = self._quests.get(quest_id)
        return bool(q and q.get("status") == "completed")


class AwardsProxy:
    """Safe proxy for award unlocking."""

    def __init__(self, changeset: ScriptChangeset):
        self._changeset = changeset

    def grant(self, award_key: str) -> None:
        if award_key not in self._changeset.granted_award_keys:
            self._changeset.granted_award_keys.append(award_key)


class DiceProxy:
    """Safe proxy for dice rolls."""

    def roll(self, dice_str: str) -> int:
        match = re.match(r"^(\d+)?d(\d+)(?:([+-])(\d+))?$", dice_str.strip().lower())
        if not match:
            return random.randint(1, 20)
        num = int(match.group(1) or 1)
        sides = int(match.group(2))
        sign = match.group(3)
        mod = int(match.group(4) or 0)
        total = sum(random.randint(1, sides) for _ in range(min(num, 20)))
        if sign == "+":
            total += mod
        elif sign == "-":
            total -= mod
        return total

    def d20(self) -> int:
        return random.randint(1, 20)


class GameContext:
    """
    Root context object exposed to scripts as `tw` (and `game`).
    """

    def __init__(
        self,
        avatar_data: dict[str, Any],
        current_scene_id: str,
        entities: dict[str, dict[str, Any]],
        exit_states: dict[str, Any],
        quests: list[dict[str, Any]],
        script_vars: dict[str, Any],
    ):
        self.changeset = ScriptChangeset()
        self.player = PlayerProxy(avatar_data, self.changeset)
        self.scene = SceneProxy(current_scene_id, self.changeset)
        self.exits = ExitProxy(exit_states, self.changeset)
        self.npcs = EntityManagerProxy(
            {k: v for k, v in entities.items() if v.get("npc_type") or v.get("is_npc")},
            self.changeset,
            NPCProxy
        )
        self.objects = EntityManagerProxy(
            {k: v for k, v in entities.items() if not (v.get("npc_type") or v.get("is_npc"))},
            self.changeset,
            ObjectProxy
        )
        self.vars = VarsProxy(script_vars, self.changeset)
        self.story = StoryProxy(self.changeset)
        self.memories = MemoriesProxy(self.changeset)
        self.game = GameProxy(self.changeset)
        self.quests = QuestsProxy(quests, self.changeset)
        self.awards = AwardsProxy(self.changeset)
        self.dice = DiceProxy()
