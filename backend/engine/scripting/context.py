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


class ScriptMessage(str):
    """Subclass of str with an attached role ('assistant' or 'system')."""
    role: str = "system"

    def __new__(cls, content: str, role: str = "system"):
        obj = super().__new__(cls, content)
        obj.role = role
        return obj


@dataclass
class ScriptChangeset:
    """Collected mutations produced during script execution."""
    player_hp_change: int = 0
    player_mana_change: int = 0
    player_stamina_change: int = 0
    player_xp_change: int = 0
    player_new_items: list[dict[str, Any]] = field(default_factory=list)
    player_removed_item_ids: list[str] = field(default_factory=list)
    player_status_effects_add: list[str] = field(default_factory=list)
    player_status_effects_remove: list[str] = field(default_factory=list)

    teleport_scene_id: Optional[str] = None
    entity_movements: list[dict[str, Any]] = field(default_factory=list)
    entity_updates: list[dict[str, Any]] = field(default_factory=list)
    exit_updates: list[dict[str, Any]] = field(default_factory=list)

    narrative_messages: list[str] = field(default_factory=list)
    system_messages: list[str] = field(default_factory=list)
    rejected_actions: list[str] = field(default_factory=list)
    new_memories: list[dict[str, Any]] = field(default_factory=list)

    completed_quest_ids: list[str] = field(default_factory=list)
    failed_quest_ids: list[str] = field(default_factory=list)
    granted_award_keys: list[str] = field(default_factory=list)
    sequence_completed: bool = False

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
    def xp(self) -> int:
        return int(self._avatar.get("xp", 0)) + self._changeset.player_xp_change

    @property
    def name(self) -> str:
        return str(self._avatar.get("name", "Protagonist"))

    def modify_hp(self, delta: int) -> None:
        self._changeset.player_hp_change += int(delta)

    def damage(self, amount: int) -> None:
        """Deals damage to the player."""
        self.modify_hp(-abs(int(amount)))

    def heal(self, amount: int) -> None:
        """Restores player HP."""
        self.modify_hp(abs(int(amount)))

    def get_stat(self, stat_name: str, default: Any = 0) -> Any:
        name_lower = str(stat_name).strip().lower()
        if name_lower == "hp":
            return self.hp
        elif name_lower == "mana":
            return self.mana
        elif name_lower == "stamina":
            return self.stamina
        elif name_lower == "xp":
            return self.xp
        if f"__stat_{name_lower}" in self._changeset.var_updates:
            return self._changeset.var_updates[f"__stat_{name_lower}"]
        return self._avatar.get(name_lower, self._avatar.get(f"stat_modifier_{name_lower}", default))

    def set_stat(self, stat_name: str, val: Any) -> None:
        name_lower = str(stat_name).strip().lower()
        if name_lower == "hp":
            self.modify_hp(int(val) - self.hp)
        elif name_lower == "mana":
            self.modify_mana(int(val) - self.mana)
        elif name_lower == "stamina":
            self.modify_stamina(int(val) - self.stamina)
        elif name_lower == "xp":
            self.modify_xp(int(val) - self.xp)
        else:
            self._changeset.var_updates[f"__stat_{name_lower}"] = val

    def modify_mana(self, delta: int) -> None:
        self._changeset.player_mana_change += int(delta)

    def modify_stamina(self, delta: int) -> None:
        self._changeset.player_stamina_change += int(delta)

    def modify_xp(self, delta: int) -> None:
        self._changeset.player_xp_change += int(delta)

    def give_item(self, item_id: str, name: Optional[str] = None, description: Optional[str] = None) -> None:
        self._changeset.player_new_items.append({
            "id": item_id,
            "name": name or item_id.replace("_", " ").title(),
            "description": description or ""
        })

    def add_item(self, item_id: str, name: Optional[str] = None, description: Optional[str] = None) -> None:
        """Alias for give_item()."""
        self.give_item(item_id, name, description)

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

    def __init__(self, current_scene_id: str, changeset: ScriptChangeset, npcs_mgr: 'EntityManagerProxy', objects_mgr: 'EntityManagerProxy'):
        self._current_scene_id = current_scene_id
        self._changeset = changeset
        self._npcs_mgr = npcs_mgr
        self._objects_mgr = objects_mgr

    @property
    def id(self) -> str:
        return self._changeset.teleport_scene_id or self._current_scene_id

    @property
    def npcs(self) -> list['NPCProxy']:
        return [npc for npc in self._npcs_mgr.all() if npc.current_scene_id == self.id]

    @property
    def items(self) -> list['ObjectProxy']:
        return [obj for obj in self._objects_mgr.all() if obj.current_scene_id == self.id]

    def teleport(self, target_scene_id: str) -> None:
        self._changeset.teleport_scene_id = target_scene_id

    def get_attribute(self, attr_name: str, default: Any = None) -> Any:
        k = f"__scene_attr_{self.id}_{attr_name}"
        if k in self._changeset.var_updates:
            return self._changeset.var_updates[k]
        return default

    def set_attribute(self, attr_name: str, val: Any) -> None:
        k = f"__scene_attr_{self.id}_{attr_name}"
        self._changeset.var_updates[k] = val


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

    def unlock(self, from_or_exit_id: str, to_scene_id: Optional[str] = None) -> None:
        if to_scene_id is not None:
            from_scene = from_or_exit_id
            to_scene = to_scene_id
        elif ":" in from_or_exit_id:
            from_scene, to_scene = from_or_exit_id.split(":", 1)
        else:
            from_scene = from_or_exit_id
            to_scene = ""
            for k in self._exit_states.keys():
                if k.startswith(f"{from_or_exit_id}:") or k.endswith(f":{from_or_exit_id}") or k == from_or_exit_id:
                    parts = k.split(":")
                    if len(parts) == 2:
                        from_scene, to_scene = parts[0], parts[1]
                        break

        self._changeset.exit_updates.append({
            "from_scene_id": from_scene,
            "to_scene_id": to_scene,
            "is_locked": False
        })

    def lock(self, from_or_exit_id: str, to_scene_id: Optional[str] = None, reason: Optional[str] = None) -> None:
        if to_scene_id is not None:
            from_scene = from_or_exit_id
            to_scene = to_scene_id
            lock_reason = reason
        elif ":" in from_or_exit_id:
            from_scene, to_scene = from_or_exit_id.split(":", 1)
            lock_reason = reason
        else:
            from_scene = from_or_exit_id
            to_scene = ""
            lock_reason = reason
            for k in self._exit_states.keys():
                if k.startswith(f"{from_or_exit_id}:") or k.endswith(f":{from_or_exit_id}") or k == from_or_exit_id:
                    parts = k.split(":")
                    if len(parts) == 2:
                        from_scene, to_scene = parts[0], parts[1]
                        break

        self._changeset.exit_updates.append({
            "from_scene_id": from_scene,
            "to_scene_id": to_scene,
            "is_locked": True,
            "lock_description": lock_reason or "The passage is barred."
        })


class EntityProxy:
    """Base proxy for a world entity (NPC or Object)."""

    def __init__(
        self,
        entity_id: str,
        entity_data: dict[str, Any],
        changeset: ScriptChangeset,
        current_player_scene_id: str = "",
        entity_mgr: Optional['EntityManagerProxy'] = None,
    ):
        self._id = entity_id
        self._data = entity_data
        self._changeset = changeset
        self._current_player_scene_id = current_player_scene_id
        self._entity_mgr = entity_mgr

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

    def get_attribute(self, attr_name: str, default: Any = None) -> Any:
        for upd in reversed(self._changeset.entity_updates):
            if upd.get("entity_id") == self._id and attr_name in upd:
                return upd[attr_name]
        return self._data.get(attr_name, default)

    def set_attribute(self, attr_name: str, val: Any) -> None:
        self._changeset.entity_updates.append({
            "entity_id": self._id,
            attr_name: val
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

    @property
    def inventory(self) -> list[Any]:
        for upd in reversed(self._changeset.entity_updates):
            if upd.get("entity_id") == self._id and "inventory" in upd:
                return list(upd["inventory"])
        return list(self._data.get("inventory") or [])

    def say(self, text: str) -> None:
        """Makes this NPC speak dialogue text."""
        clean_text = str(text).strip()
        formatted = f'{self.name}: "{clean_text}"'
        self._changeset.narrative_messages.append(formatted)

    def move_to(self, to_scene_id: str, spatial_position: Optional[str] = None) -> None:
        """Moves this NPC to another scene. Accepts 'current', 'here', 'player' or scene ID."""
        target_scene = to_scene_id
        if not target_scene or str(target_scene).strip().lower() in ("current", "here", "player"):
            target_scene = self._changeset.teleport_scene_id or self._current_player_scene_id or self._data.get("current_scene_id", "")
        self._changeset.entity_movements.append({
            "entity_id": self._id,
            "to_scene_id": target_scene,
            "to_spatial_position": spatial_position or self._data.get("spatial_position", "")
        })

    def move_to_player(self, spatial_position: Optional[str] = None) -> None:
        """Moves this NPC directly into the protagonist's current scene."""
        self.move_to("current", spatial_position)

    def drop_item(self, item_id: str, scene_id: Optional[str] = None, spatial_position: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Moves an item from this NPC's inventory into a scene (defaults to NPC/player's current scene)."""
        iid = str(item_id).strip().upper()
        current_inv = self.inventory
        dropped_item = None
        new_inv = []
        for it in current_inv:
            this_id = str(it.get("id") if isinstance(it, dict) else it).strip().upper()
            if this_id == iid and dropped_item is None:
                dropped_item = it if isinstance(it, dict) else {"id": it, "name": it}
            else:
                new_inv.append(it)

        if not dropped_item:
            dropped_item = {"id": item_id, "name": item_id}

        target_scene = scene_id
        if not target_scene:
            target_scene = self.current_scene_id or self._changeset.teleport_scene_id or self._current_player_scene_id or "START"
        elif str(target_scene).strip().lower() in ("player", "current", "here"):
            target_scene = self._changeset.teleport_scene_id or self._current_player_scene_id or self.current_scene_id or "START"

        self._changeset.entity_updates.append({
            "entity_id": self._id,
            "inventory": new_inv
        })

        item_raw_id = dropped_item.get("id") if isinstance(dropped_item, dict) else item_id
        self._changeset.entity_movements.append({
            "entity_id": item_raw_id,
            "to_scene_id": target_scene,
            "to_spatial_position": spatial_position or ""
        })
        self._changeset.entity_updates.append({
            "entity_id": item_raw_id,
            "current_scene_id": target_scene,
            "is_in_inventory": False,
            "is_hidden": False,
        })
        return dropped_item

    def give_item(self, item_id_or_dict: Any) -> None:
        """Moves/adds an item from a scene into this NPC's inventory."""
        item_id = item_id_or_dict.get("id") if isinstance(item_id_or_dict, dict) else str(item_id_or_dict)
        item_data = item_id_or_dict if isinstance(item_id_or_dict, dict) else {"id": item_id, "name": item_id}

        current_inv = self.inventory
        if not any(str(i.get("id") if isinstance(i, dict) else i).strip().upper() == str(item_id).strip().upper() for i in current_inv):
            current_inv.append(item_data)
            self._changeset.entity_updates.append({
                "entity_id": self._id,
                "inventory": current_inv
            })

        self._changeset.entity_updates.append({
            "entity_id": item_id,
            "current_scene_id": "INVENTORY",
            "is_in_inventory": False,
            "is_hidden": True,
        })

    def has_item(self, item_id: str) -> bool:
        """Checks if the NPC possesses the specified item."""
        iid = str(item_id).strip().upper()
        for it in self.inventory:
            if isinstance(it, dict) and str(it.get("id", "")).strip().upper() == iid:
                return True
            elif isinstance(it, str) and it.strip().upper() == iid:
                return True
        return False

    def kill(self, drop_inventory: bool = True) -> None:
        """Kills this NPC, setting HP to 0 and marking them defeated."""
        self.hp = 0
        self.is_defeated = True
        self._changeset.entity_updates.append({
            "entity_id": self._id,
            "hp": 0,
            "is_defeated": True
        })
        if drop_inventory:
            for it in list(self.inventory):
                iid = it.get("id") if isinstance(it, dict) else it
                if iid:
                    self.drop_item(str(iid))

    def die(self) -> None:
        """Alias for kill()."""
        self.kill()

    def modify_hp(self, delta: int) -> None:
        new_hp = max(0, self.hp + int(delta))
        self.hp = new_hp
        if new_hp == 0 and not self.is_defeated:
            self.kill()


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

    def move_to_scene(self, scene_id: str, spatial_position: Optional[str] = None) -> None:
        """Moves this item into a scene (accepts 'current' for protagonist scene)."""
        target_scene = scene_id
        if not target_scene or str(target_scene).strip().lower() in ("current", "here", "player"):
            target_scene = self._changeset.teleport_scene_id or self._current_player_scene_id or "START"
        self._changeset.entity_movements.append({
            "entity_id": self._id,
            "to_scene_id": target_scene,
            "to_spatial_position": spatial_position or ""
        })
        self._changeset.entity_updates.append({
            "entity_id": self._id,
            "current_scene_id": target_scene,
            "is_in_inventory": False,
            "is_hidden": False,
        })

    def give_to_npc(self, npc_id: str) -> None:
        """Transfers this item into an NPC's inventory."""
        if self._entity_mgr:
            self._entity_mgr.give_item(npc_id, self._data or {"id": self._id, "name": self.name})


class EntityManagerProxy:
    """Access point for querying NPCs or objects."""

    def __init__(
        self,
        entities: dict[str, dict[str, Any]],
        changeset: ScriptChangeset,
        proxy_cls: type[EntityProxy],
        current_player_scene_id: str = "",
    ):
        self._entities = entities
        self._changeset = changeset
        self._proxy_cls = proxy_cls
        self._current_player_scene_id = current_player_scene_id

    def get(self, entity_id: str) -> EntityProxy:
        if entity_id in self._entities:
            return self._proxy_cls(
                entity_id, self._entities[entity_id], self._changeset, self._current_player_scene_id, self
            )
        target_upper = str(entity_id).strip().upper()
        for eid, data in self._entities.items():
            if str(eid).strip().upper() == target_upper:
                return self._proxy_cls(
                    eid, data, self._changeset, self._current_player_scene_id, self
                )
        target_lower = str(entity_id).strip().lower()
        for eid, data in self._entities.items():
            if str(data.get("name", "")).strip().lower() == target_lower:
                return self._proxy_cls(
                    eid, data, self._changeset, self._current_player_scene_id, self
                )
        return self._proxy_cls(
            entity_id, {"id": entity_id, "name": entity_id}, self._changeset, self._current_player_scene_id, self
        )

    def all(self) -> list[EntityProxy]:
        return [self.get(eid) for eid in self._entities.keys()]

    def exists(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            return True
        target_upper = str(entity_id).strip().upper()
        return any(str(eid).strip().upper() == target_upper for eid in self._entities.keys())

    def say(self, entity_id: str, text: str) -> None:
        """Makes an NPC speak dialogue text."""
        ent = self.get(entity_id)
        if isinstance(ent, NPCProxy):
            ent.say(text)
        else:
            clean_text = str(text).strip()
            self._changeset.narrative_messages.append(f'{ent.name}: "{clean_text}"')

    def move(self, entity_id: str, to_scene_id: str, spatial_position: Optional[str] = None) -> None:
        """Moves an entity or NPC to another scene. Accepts 'current' for protagonist's scene."""
        ent = self.get(entity_id)
        if isinstance(ent, NPCProxy):
            ent.move_to(to_scene_id, spatial_position)
        else:
            target_scene = to_scene_id
            if not target_scene or str(target_scene).strip().lower() in ("current", "here", "player"):
                target_scene = self._changeset.teleport_scene_id or self._current_player_scene_id or ""
            self._changeset.entity_movements.append({
                "entity_id": entity_id,
                "to_scene_id": target_scene,
                "to_spatial_position": spatial_position or ""
            })

    def move_to_player(self, entity_id: str, spatial_position: Optional[str] = None) -> None:
        """Moves an entity or NPC into the protagonist's current scene."""
        self.move(entity_id, "current", spatial_position)

    def drop_item(self, npc_id: str, item_id: str, scene_id: Optional[str] = None, spatial_position: Optional[str] = None) -> None:
        """Transfers an item from an NPC's inventory to a scene."""
        ent = self.get(npc_id)
        if isinstance(ent, NPCProxy):
            ent.drop_item(item_id, scene_id, spatial_position)

    def give_item(self, npc_id: str, item_id_or_dict: Any) -> None:
        """Transfers an item from a scene into an NPC's inventory."""
        ent = self.get(npc_id)
        if isinstance(ent, NPCProxy):
            ent.give_item(item_id_or_dict)

    def kill(self, entity_id: str, drop_inventory: bool = True) -> None:
        """Kills an NPC by entity ID."""
        ent = self.get(entity_id)
        if isinstance(ent, NPCProxy):
            ent.kill(drop_inventory=drop_inventory)


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
        """Emits GM narration as if told by the Game Master."""
        self._changeset.narrative_messages.append(str(message).strip())

    def show_message(self, message: str) -> None:
        """Alias for narrate(). Emits GM narration."""
        self.narrate(message)

    def message(self, message: str) -> None:
        """Alias for narrate(). Emits GM narration."""
        self.narrate(message)

    def system_message(self, message: str) -> None:
        """Emits a system notification message."""
        self._changeset.system_messages.append(str(message).strip())

    def system(self, message: str) -> None:
        """Alias for system_message()."""
        self.system_message(message)

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

    def __init__(self, changeset: ScriptChangeset, in_game_time: int = 0):
        self._changeset = changeset
        self.in_game_time = in_game_time

    @property
    def time(self) -> int:
        return self.in_game_time

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


class SequencesProxy:
    """Safe proxy for sequence progression."""

    def __init__(self, changeset: ScriptChangeset):
        self._changeset = changeset

    def advance(self) -> None:
        self._changeset.sequence_completed = True

    def complete_current(self) -> None:
        self._changeset.sequence_completed = True


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
        in_game_time: int = 0,
    ):
        self.changeset = ScriptChangeset()
        self.player = PlayerProxy(avatar_data, self.changeset)
        self.npcs = EntityManagerProxy(
            {k: v for k, v in entities.items() if str(v.get("entity_type") or "").upper() == "NPC" or v.get("npc_type") or v.get("is_npc")},
            self.changeset,
            NPCProxy,
            current_player_scene_id=current_scene_id,
        )
        self.objects = EntityManagerProxy(
            {k: v for k, v in entities.items() if not (str(v.get("entity_type") or "").upper() == "NPC" or v.get("npc_type") or v.get("is_npc"))},
            self.changeset,
            ObjectProxy,
            current_player_scene_id=current_scene_id,
        )
        self.items = self.objects
        self.scene = SceneProxy(current_scene_id, self.changeset, self.npcs, self.objects)
        self.exits = ExitProxy(exit_states, self.changeset)
        self.vars = VarsProxy(script_vars, self.changeset)
        self.story = StoryProxy(self.changeset)
        self.memories = MemoriesProxy(self.changeset)
        self.game = GameProxy(self.changeset, in_game_time)
        self.quests = QuestsProxy(quests, self.changeset)
        self.awards = AwardsProxy(self.changeset)
        self.sequences = SequencesProxy(self.changeset)
        self.dice = DiceProxy()

    def narrate(self, message: str) -> None:
        """Shortcut for tw.story.narrate(). Emits GM narration."""
        self.story.narrate(message)

    def show_message(self, message: str) -> None:
        """Shortcut for tw.story.narrate(). Emits GM narration."""
        self.story.narrate(message)

    def system(self, message: str) -> None:
        """Shortcut for tw.story.system_message(). Emits system notification."""
        self.story.system_message(message)
