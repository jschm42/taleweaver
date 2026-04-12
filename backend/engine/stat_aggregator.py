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
    total_stats = dict(avatar.stats)

    # 1. Add Equipment modifiers
    for slot, item in avatar.equipment.items():
        if item and isinstance(item, dict) and "stat_modifiers" in item:
            for stat, value in item["stat_modifiers"].items():
                total_stats[stat] = total_stats.get(stat, 0) + value
                
    # 2. Add Status Effect modifiers
    for status in avatar.status_effects:
        if status in STATUS_MODIFIERS:
            for stat, value in STATUS_MODIFIERS[status].items():
                total_stats[stat] = total_stats.get(stat, 0) + value

    return total_stats
