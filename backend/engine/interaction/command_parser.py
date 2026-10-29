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
        items = ", ".join(f"{v} {_STAT_DISPLAY_NAMES.get(k, k.title())}" for k, v in lost.items())
        parts.append(f"You lose: {items}.")

    return " ".join(parts)


# Commands that forward their arguments to the turn engine as "<TAG> <args>".
_ARG_TRIGGERS = {
    "/drop": "[TRIGGER_DROP]",
    "/combine": "[TRIGGER_COMBINE]",
    "/craft": "[TRIGGER_CRAFT]",
    "/use": "[TRIGGER_COMBINE]",
    "/take": "[TRIGGER_TAKE_DIRECT]",
    "/take_direct": "[TRIGGER_TAKE_DIRECT]",
    "/open": "[TRIGGER_OPEN]",
    "/container_take_all": "[TRIGGER_CONTAINER_TAKE_ALL]",
    "/container_take_item": "[TRIGGER_CONTAINER_TAKE_ITEM]",
    "/container_drop_scene": "[TRIGGER_CONTAINER_DROP_SCENE]",
    "/say": "[TRIGGER_SAY]",
    "/speak": "[TRIGGER_SAY]",
    "/inspect": "[TRIGGER_INSPECT]",
    "/read": "[TRIGGER_READ]",
    "/push": "[TRIGGER_PUSH]",
    "/pull": "[TRIGGER_PULL]",
    "/switch": "[TRIGGER_SWITCH]",
    "/search": "[TRIGGER_SEARCH]",
    "/playagent": "[TRIGGER_AGENT]",
    "/play-agent": "[TRIGGER_AGENT]",
}

# Commands that map to a fixed tag regardless of arguments.
_FIXED_TRIGGERS = {
    "/lookaround": "[TRIGGER_LOOKAROUND]",
    "/look": "[TRIGGER_LOOKAROUND]",
    "/rest": "[TRIGGER_REST]",
    "/rule-pass": "[RULE_PASS]",
}

_SHEET_COMMANDS = {"/sheet", "/inventory", "/stats"}

# Standard equipment slots created on demand for older avatars.
_DEFAULT_SLOTS = (
    "Head",
    "Chest",
    "Arms",
    "Legs",
    "Hands",
    "Feet",
    "Ring_1",
    "Ring_2",
    "Neck",
    "MainHand",
    "OffHand",
)

_SLOT_ALIASES = {"Hand": "Hands", "Ring": "Ring_1"}
_OFFHAND_KEYWORDS = ("shield", "buckler", "torch")


def _find_inventory_index(avatar: Avatar, item_name: str) -> int:
    for idx, item in enumerate(avatar.inventory):
        if isinstance(item, dict) and item.get("name", "").lower() == item_name.lower():
            return idx
    return -1


def _resolve_equip_slot(item: dict) -> str | None:
    """Determines the target slot for an item, guessing for weapons and generic hand items."""
    from backend.engine.item_logic import get_item_slot

    slot = item.get("slot", "Hands")  # Fallback to hands if missing
    slot = _SLOT_ALIASES.get(slot, slot)
    if not slot or slot == "None":
        slot = item.get("slot")
    if slot and slot != "Hands":
        return slot

    item_type = item.get("item_type")
    name = item.get("name", "").lower()
    if item_type == "WEAPON":
        return "MainHand"
    if item_type == "TOOL" and any(kw in name for kw in _OFFHAND_KEYWORDS):
        return "OffHand"
    # Last resort: try guessing
    return get_item_slot(item.get("name", ""), item.get("item_type", "PICKABLE"))


def _ensure_equipment_slot(avatar: Avatar, slot: str) -> bool:
    """Self-heals missing standard slots; returns False when the slot is unknown."""
    if slot in avatar.equipment:
        return True
    if slot not in _DEFAULT_SLOTS:
        return False
    new_equipment = dict(avatar.equipment)
    for s in _DEFAULT_SLOTS:
        new_equipment.setdefault(s, None)
    avatar.equipment = new_equipment
    return True


def _split_stat_delta(
    new_mods: dict[str, int], old_mods: dict[str, int]
) -> tuple[dict[str, int], dict[str, int]]:
    """Returns (gained, lost) stats for swapping the old item for the new one."""
    gained: dict[str, int] = {}
    lost: dict[str, int] = {}
    for stat in set(new_mods) | set(old_mods):
        delta = new_mods.get(stat, 0) - old_mods.get(stat, 0)
        if delta > 0:
            gained[stat] = delta
        elif delta < 0:
            lost[stat] = delta
    return gained, lost


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

        if command in _ARG_TRIGGERS:
            return f"{_ARG_TRIGGERS[command]} {args}"
        if command in _FIXED_TRIGGERS:
            return _FIXED_TRIGGERS[command]
        if command in _SHEET_COMMANDS:
            return f"Opening character sheet for {avatar.name}..."

        handlers = {
            "/equip": lambda: CommandParser._handle_equip(avatar, args),
            "/unequip": lambda: CommandParser._handle_unequip(avatar, args),
            "/consume": lambda: CommandParser._handle_consume(avatar, args),
            "/help": lambda: CommandParser._handle_help(debug_enabled=debug_enabled),
            "/walkthrough": lambda: CommandParser._handle_walkthrough(args),
        }
        handler = handlers.get(command)
        if handler:
            return handler()
        return f"Unknown command: {command}. Type /help for a list of commands."

    @staticmethod
    def _handle_walkthrough(args: str) -> str:
        if args.strip().lower() == "reveal":
            return "[TRIGGER_WALKTHROUGH_REVEAL]"
        return "[TRIGGER_WALKTHROUGH]"

    @staticmethod
    def _handle_help(debug_enabled: bool = False) -> str:
        lines = [
            "**Available Commands:**",
            "- `/help`: Show this list.",
            "- `/map`: Toggle the world map.",
            "- `/say <text>`: Speak directly to NPCs (and others) in quoted/out-loud form.",
            "- `/inspect <target>`: Inspect an NPC, object or the surroundings.",
            "- `/open <target>`: Open a container or mechanism.",
            "- `/read <target>`: Read a note, book, sign, scroll, or text log.",
            "- `/search [target]`: Search the surroundings or a specific object.",
            "- `/lookaround` or `/look`: Get a fresh overview of the current area.",
            "- `/attack <target>`: Start a fight with a specific NPC (by name or ID).",
            "- `/push <target>`: Push an object, lever, mechanism, or obstacle.",
            "- `/pull <target>`: Pull an object, lever, mechanism, or obstacle.",
            "- `/switch <target> <state> [code]`: Set a switch/mechanism to a target state.",
            "- `/rest`: Take a short rest if the situation allows it.",
            "- `/equip <item>`: Equip an item from your inventory.",
            "- `/drop <item>`: Drop an item into the current room.",
            "- `/take <item>`: Pick up an item from the room.",
            "- `/open <container>`: Open a container item.",
            "- `/container_take_all <container>`: Take all items from a container.",
            "- `/container_take_item <container> | <item>`: Take a single item from a container.",
            "- `/container_drop_scene <container>`: Drop all container items into the scene.",
            "- `/unequip <slot>`: Remove an item from a slot.",
            "- `/consume <item>`: Use a consumable item.",
            "- `/combine <item1> <item2>`: Attempt to combine two objects.",
            "- `/craft <item1> | <item2> [| ...]`: Combine exactly these items deterministically (no GM).",
            "- `/use <item1> [on] <item2>`: Use/Combine objects.",
            "- `/walkthrough`: Open the secret walkthrough panel.",
            "- `/walkthrough reveal`: Reveal all steps for 150 XP.",
            "- `/sheet`: Open your character sheet.",
            "- `/playagent [on/off]`: Activate or deactivate the autonomous Play-Agent.",
            "- `/playagent personality <type>`: Set Play-Agent personality (Casual, Bureaucrat, Powerplayer, Custom).",
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

        item_idx = _find_inventory_index(avatar, item_name)
        if item_idx == -1:
            return f"You don't have '{item_name}' in your inventory."

        item_to_equip = avatar.inventory[item_idx]
        slot = _resolve_equip_slot(item_to_equip)
        if not slot:
            return f"'{item_to_equip.get('name')}' cannot be equipped."
        if not _ensure_equipment_slot(avatar, slot):
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
        gained, lost = _split_stat_delta(new_mods, old_mods)
        stat_msg = _format_stat_change_message(gained, lost)

        result = response_msg + f"Equipped {item_to_equip.get('name')} in slot {slot}."
        if stat_msg:
            result += f" {stat_msg}"
        item_id_str = item_to_equip.get("id") or "None"
        return f"[TRIGGER_EQUIP] {item_id_str} | {result}"

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
        item_id_str = currently_equipped.get("id") or "None"
        return f"[TRIGGER_UNEQUIP] {item_id_str} | {result}"

    @staticmethod
    def _handle_consume(avatar: Avatar, item_name: str) -> str:
        if not item_name:
            return "Usage: /consume <item name>"
        return f"[TRIGGER_CONSUME] {item_name}"
