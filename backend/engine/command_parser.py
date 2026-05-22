from backend.models.avatar import Avatar


# Canonical stat names for display
_STAT_DISPLAY_NAMES = {
    "strength": "Strength",
    "dexterity": "Dexterity",
    "intelligence": "Intelligence",
    "wisdom": "Wisdom",
    "charisma": "Charisma",
    "armor_class": "Armor Class",
    "hp": "HP",
    "stamina": "Stamina",
    "mana": "Mana",
}


def _extract_item_stat_modifiers(item: dict) -> dict[str, int]:
    """
    Extracts all stat modifiers from an item dict.
    Supports both legacy 'stat_modifiers' dict and flat 'stat_modifier_*' fields.
    Returns a dict like {"strength": 5, "dexterity": -2}.
    """
    mods: dict[str, int] = {}
    if not item or not isinstance(item, dict):
        return mods

    # Legacy nested dict
    if "stat_modifiers" in item and isinstance(item["stat_modifiers"], dict):
        for stat, value in item["stat_modifiers"].items():
            if isinstance(value, (int, float)) and value != 0:
                mods[stat.lower()] = int(value)

    # Flat fields (stat_modifier_strength, etc.)
    for stat_key in _STAT_DISPLAY_NAMES:
        flat_key = f"stat_modifier_{stat_key}"
        val = item.get(flat_key)
        if val is not None and isinstance(val, (int, float)) and int(val) != 0:
            mods[stat_key] = int(val)

    return mods


def _format_stat_change_message(gained: dict[str, int], lost: dict[str, int]) -> str:
    """
    Builds a human-readable stat change suffix.
    Example: "You gain: +5 Strength, +2 Stamina. You lose: -3 Dexterity."
    """
    parts: list[str] = []

    if gained:
        items = ", ".join(
            f"+{v} {_STAT_DISPLAY_NAMES.get(k, k.title())}" for k, v in gained.items()
        )
        parts.append(f"You gain: {items}.")

    if lost:
        items = ", ".join(
            f"{v} {_STAT_DISPLAY_NAMES.get(k, k.title())}" for k, v in lost.items()
        )
        parts.append(f"You lose: {items}.")

    return " ".join(parts)


class CommandParser:
    @staticmethod
    def parse_command(avatar: Avatar, command_text: str, debug_enabled: bool = False) -> str:
        """
        Parses direct slash commands and synchronously applies them to the Avatar.
        Examples: /equip Iron Sword, /drop Torch
        """
        parts = command_text.strip().split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/equip":
            return CommandParser._handle_equip(avatar, args)
        elif command == "/drop":
            return f"[TRIGGER_DROP] {args}"
        elif command == "/help":
            return CommandParser._handle_help(debug_enabled=debug_enabled)
        elif command == "/walkthrough":
            return "[TRIGGER_WALKTHROUGH_REVEAL]" if args.strip().lower() == "reveal" else "[TRIGGER_WALKTHROUGH]"
        elif command == "/hint":
            return "[TRIGGER_HINT]"
        elif command == "/combine" or command == "/use":
            return f"[TRIGGER_COMBINE] {args}"
        elif command == "/take":
            return f"[TRIGGER_TAKE] {args}"
        elif command == "/take_direct":
            return f"[TRIGGER_TAKE_DIRECT] {args}"
        elif command == "/talk":
            return f"[TRIGGER_TALK] {args}"
        elif command == "/say" or command == "/speak":
            return f"[TRIGGER_SAY] {args}"
        elif command == "/inspect":
            return f"[TRIGGER_INSPECT] {args}"
        elif command == "/unequip":
            return CommandParser._handle_unequip(avatar, args)
        elif command == "/consume":
            return CommandParser._handle_consume(avatar, args)
        elif command == "/rule-pass":
            return "[RULE_PASS]"
        elif command in ["/sheet", "/inventory", "/stats"]:
            return f"Opening character sheet for {avatar.name}..."
            
        return f"Unknown command: {command}. Type /help for a list of commands."

    @staticmethod
    def _handle_help(debug_enabled: bool = False) -> str:
        lines = [
            "**Available Commands:**",
            "- `/help`: Show this list.",
            "- `/map`: Toggle the world map.",
            "- `/talk <target>`: Talk to an NPC.",
            "- `/say <text>`: Say something out loud (wörtliche Rede).",
            "- `/inspect <target>`: Inspect an NPC, object or the surroundings.",
            "- `/attack <target>`: Start a fight with a specific NPC (by name or ID).",
            "- `/equip <item>`: Equip an item from your inventory.",
            "- `/drop <item>`: Drop an item into the current room.",
            "- `/take <item>`: Pick up an item from the room.",
            "- `/unequip <slot>`: Remove an item from a slot.",
            "- `/consume <item>`: Use a consumable item.",
            "- `/combine <item1> <item2>`: Attempt to combine two objects.",
            "- `/use <item1> [on] <item2>`: Use/Combine objects.",
            "- `/walkthrough`: Open the secret walkthrough panel.",
            "- `/walkthrough reveal`: Reveal all steps for 200 XP.",
            "- `/hint`: Buy one tactical hint for 50 XP.",
            "- `/sheet`: Open your character sheet.",
            "- `/agent on/off`: Turn on/off autonomous agent gameplay mode."
        ]
        
        if debug_enabled:
            lines.append("- `/debug on/off`: Toggle in-game debug mode.")
            lines.append("- `/debug npc drop_items`: Force NPCs in scene to drop all items.")
            lines.append("- `/debug item dynamic on/off`: Toggle dynamic item creation by GM.")
            lines.append("- `/debug walkthrough`: Reveal walkthrough without XP cost (debug).")
            lines.append("- `/debug <cmd>`: Engine debug commands.")
            
        lines.append("\n*Alternatively, just type your actions naturally!*")
        return "\n".join(lines)

    @staticmethod
    def _handle_equip(avatar: Avatar, item_name: str) -> str:
        if not item_name:
            return "Usage: /equip <item name>"

        # Find item in inventory
        item_idx = -1
        for idx, item in enumerate(avatar.inventory):
            if isinstance(item, dict) and item.get("name", "").lower() == item_name.lower():
                item_idx = idx
                break

        if item_idx == -1:
            return f"You don't have '{item_name}' in your inventory."

        item_to_equip = avatar.inventory[item_idx]
        slot = item_to_equip.get("slot", "Hands") # Fallback to hands if missing
        
        from backend.engine.item_logic import get_item_slot
        
        # Normalize slot names
        if slot == "Hand": slot = "Hands"
        if slot == "Ring": slot = "Ring_1"

        # Determine target slot if not provided
        if not slot or slot == "None":
            slot = item_to_equip.get("slot")

        # Smart Redirection / Guessing
        if not slot or slot == "Hands":
            # If it's a weapon or tool, move to Hand slots
            if item_to_equip.get("item_type") == "WEAPON":
                slot = "MainHand"
            elif item_to_equip.get("item_type") == "TOOL" and any(kw in item_to_equip.get("name", "").lower() for kw in ["shield", "buckler", "torch"]):
                slot = "OffHand"
            else:
                # Last resort: try guessing
                slot = get_item_slot(item_to_equip.get("name", ""), item_to_equip.get("item_type", "PICKABLE"))

        if not slot:
            return f"'{item_to_equip.get('name')}' cannot be equipped."

        # Self-healing: Ensure standard slots exist
        DEFAULT_SLOTS = {
            "Head": None, "Chest": None, "Arms": None, "Legs": None,
            "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None, "Neck": None,
            "MainHand": None, "OffHand": None
        }
        
        if slot not in avatar.equipment:
            if slot in DEFAULT_SLOTS:
                new_equipment = dict(avatar.equipment)
                for s, val in DEFAULT_SLOTS.items():
                    if s not in new_equipment:
                        new_equipment[s] = val
                avatar.equipment = new_equipment
            else:
                return f"The protagonist does not have an equipment slot for '{slot}'."

        currently_equipped = avatar.equipment.get(slot)
        response_msg = ""
        
        # SQLAlchemy mutability safely handled by re-assigning lists/dicts
        new_equipment = dict(avatar.equipment)
        new_inventory = list(avatar.inventory)

        if currently_equipped is not None:
            new_inventory.append(currently_equipped)
            response_msg = f"Unequipped {currently_equipped.get('name')}. "

        # Equip new item
        new_equipment[slot] = item_to_equip
        del new_inventory[item_idx]

        avatar.equipment = new_equipment
        avatar.inventory = new_inventory

        # Compute net stat change (new item minus old item)
        new_mods = _extract_item_stat_modifiers(item_to_equip)
        old_mods = _extract_item_stat_modifiers(currently_equipped) if currently_equipped else {}
        all_stats = set(new_mods.keys()) | set(old_mods.keys())
        gained: dict[str, int] = {}
        lost: dict[str, int] = {}
        for stat in all_stats:
            delta = new_mods.get(stat, 0) - old_mods.get(stat, 0)
            if delta > 0:
                gained[stat] = delta
            elif delta < 0:
                lost[stat] = delta
        stat_msg = _format_stat_change_message(gained, lost)

        result = response_msg + f"Equipped {item_to_equip.get('name')} in slot {slot}."
        if stat_msg:
            result += f" {stat_msg}"
        return result

    @staticmethod
    def _handle_unequip(avatar: Avatar, slot_name: str) -> str:
        if not slot_name:
            return "Usage: /unequip <slot name>"

        # Normalize slot name
        slots = list(avatar.equipment.keys())
        match = next((s for s in slots if s.lower() == slot_name.lower()), None)
        if not match:
            return f"Invalid slot: {slot_name}. Available: {', '.join(slots)}"

        currently_equipped = avatar.equipment[match]
        if currently_equipped is None:
            return f"Nothing is equipped in the {match} slot."

        # Move to inventory
        new_equipment = dict(avatar.equipment)
        new_inventory = list(avatar.inventory)
        
        new_equipment[match] = None
        new_inventory.append(currently_equipped)
        
        avatar.equipment = new_equipment
        avatar.inventory = new_inventory
        
        # Compute stat losses from the removed item
        removed_mods = _extract_item_stat_modifiers(currently_equipped)
        lost = {k: -v for k, v in removed_mods.items() if v > 0}
        gained = {k: -v for k, v in removed_mods.items() if v < 0}
        stat_msg = _format_stat_change_message(gained, lost)
        
        result = f"Unequipped {currently_equipped.get('name')} from {match}."
        if stat_msg:
            result += f" {stat_msg}"
        return result

    @staticmethod
    def _handle_consume(avatar: Avatar, item_name: str) -> str:
        if not item_name:
            return "Usage: /consume <item name>"
        return f"[TRIGGER_CONSUME] {item_name}"

