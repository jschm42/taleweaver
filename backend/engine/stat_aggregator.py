from backend.models.avatar import Avatar

# A static map defining standard status effect modifiers for stats.
STATUS_MODIFIERS = {
    "Weakened": {"strength": -2},
    "Poisoned": {"constitution": -1, "strength": -1},
    "Enraged": {"strength": +3, "intelligence": -2},
    "Blessed": {"intelligence": +2, "dexterity": +1}
}

def calculate_total_stats(avatar: Avatar) -> dict:
    """
    Computes total O(1) representation of the Avatar's stats.
    Base Stats + Equipment Modifiers + Status Effects.
    """
    # Start with base stats from the avatar columns
    total_stats = {
        "strength": avatar.strength,
        "dexterity": avatar.dexterity,
        "intelligence": avatar.intelligence,
        "wisdom": avatar.wisdom,
        "charisma": avatar.charisma,
        "armor_class": avatar.armor_class
    }

    # If avatar.stats contains additional/override values, apply them
    if avatar.stats:
        for k, v in avatar.stats.items():
            total_stats[k] = v

    # 1. Add Equipment modifiers
    for slot, item in avatar.equipment.items():
        if not item or not isinstance(item, dict):
            continue
            
        # Handle legacy 'stat_modifiers' dict
        if "stat_modifiers" in item:
            for stat, value in item["stat_modifiers"].items():
                total_stats[stat] = total_stats.get(stat, 0) + value
        
        # Handle flat fields (stat_modifier_strength, etc.)
        for stat_key in total_stats.keys():
            mod_key = f"stat_modifier_{stat_key}"
            if mod_key in item and item[mod_key] is not None:
                total_stats[stat_key] += item[mod_key]
                
    # 2. Add Status Effect modifiers
    for status in avatar.status_effects:
        if status in STATUS_MODIFIERS:
            for stat, value in STATUS_MODIFIERS[status].items():
                total_stats[stat] = total_stats.get(stat, 0) + value

    return total_stats
