from backend.models.avatar import Avatar

class CommandParser:
    @staticmethod
    def parse_command(avatar: Avatar, command_text: str) -> str:
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
            return CommandParser._handle_drop(avatar, args)
        elif command == "/help":
            return CommandParser._handle_help()
        elif command == "/combine" or command == "/use":
            return f"[TRIGGER_COMBINE] {args}"
        elif command == "/take":
            return f"[TRIGGER_TAKE] {args}"
        elif command in ["/sheet", "/inventory", "/stats"]:
            return f"Opening character sheet for {avatar.name}..."
            
        return f"Unknown command: {command}. Type /help for a list of commands."

    @staticmethod
    def _handle_help() -> str:
        return (
            "**Available Commands:**\n"
            "- `/help`: Show this list.\n"
            "- `/map`: Toggle the world map.\n"
            "- `/equip <item>`: Equip an item from your inventory.\n"
            "- `/drop <item>`: Drop an item into the current room.\n"
            "- `/take <item>`: Pick up an item from the room.\n"
            "- `/combine <item1> <item2>`: Attempt to combine two objects.\n"
            "- `/use <item1> [on] <item2>`: Use/Combine objects.\n"
            "- `/sheet`: Open your character sheet.\n"
            "- `/debug <cmd>`: Engine debug commands.\n\n"
            "*Alternatively, just type your actions naturally!*"
        )

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

        if slot not in avatar.equipment:
            return f"Invalid equipment slot '{slot}' on item."

        currently_equipped = avatar.equipment[slot]
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

        return response_msg + f"Equipped {item_to_equip.get('name')} in slot {slot}."

    @staticmethod
    def _handle_drop(avatar: Avatar, item_name: str) -> str:
        if not item_name:
            return "Usage: /drop <item name>"

        # Find item
        item_idx = -1
        for idx, item in enumerate(avatar.inventory):
            if isinstance(item, dict) and item.get("name", "").lower() == item_name.lower():
                item_idx = idx
                break

        if item_idx == -1:
            return f"You don't have '{item_name}' in your inventory."

        new_inventory = list(avatar.inventory)
        dropped_item = new_inventory.pop(item_idx)
        avatar.inventory = new_inventory
        
        return f"You dropped {dropped_item.get('name')}."
