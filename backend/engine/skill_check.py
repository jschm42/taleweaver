import random

from backend.engine.stat_aggregator import calculate_total_stats
from backend.models.avatar import Avatar


def roll_skill_check(avatar: Avatar, base_stat: str, challenge_rating: int) -> dict:
    """
    Perform a D20 roll + total stat modifier and check against a Challenge Rating (DC).
    Returns a dict with details about the roll.
    """
    total_stats = calculate_total_stats(avatar)
    modifier = total_stats.get(base_stat, 0)
    
    d20_roll = random.randint(1, 20)
    total = d20_roll + modifier
    
    success = total >= challenge_rating
    
    return {
        "d20": d20_roll,
        "modifier": modifier,
        "total": total,
        "challenge_rating": challenge_rating,
        "success": success
    }

def parse_dice(dice_str: str) -> int:
    """
    Parses a dice string like '1d8+2' or '2d6' and returns the result.
    """
    res = roll_dice_detailed(dice_str)
    return res["total"]

def roll_dice_detailed(dice_str: str) -> dict:
    """
    Parses a dice string and returns detailed roll results.
    """
    import re
    match = re.match(r"(\d+)d(\d+)([+-]\d+)?", dice_str.lower().replace(" ", ""))
    if not match:
        return {"total": 0, "dice_total": 0, "rolls": [], "bonus": 0, "dice_str": dice_str}
    
    num_dice = int(match.group(1))
    sides = int(match.group(2))
    bonus = int(match.group(3)) if match.group(3) else 0
    
    rolls = [random.randint(1, sides) for _ in range(num_dice)]
    dice_total = sum(rolls)
    total = dice_total + bonus
    
    return {
        "total": total,
        "dice_total": dice_total,
        "rolls": rolls,
        "bonus": bonus,
        "dice_str": dice_str
    }

def roll_attack(avatar: Avatar, hit_stat: str, target_ac: int, damage_dice: str) -> dict:
    """
    Performs an attack roll (D20 + hit_stat mod) vs target_ac.
    If hit, rolls damage_dice.
    Also handles DEX-based critical hits:
    - critical threshold is 20 - max(0, (dexterity - 10) // 4), clamped to >= 15.
    - if d20 roll >= crit_threshold, it's a critical hit (auto-hit, double damage total).
    """
    total_stats = calculate_total_stats(avatar)
    hit_modifier = total_stats.get(hit_stat, 0)
    dexterity = int(total_stats.get("dexterity", avatar.dexterity or 10))
    
    # Critical hit threshold based on DEX
    crit_threshold = 20 - max(0, (dexterity - 10) // 4)
    crit_threshold = max(15, crit_threshold)
    
    d20_roll = random.randint(1, 20)
    hit_total = d20_roll + hit_modifier
    
    is_crit = (d20_roll >= crit_threshold)
    is_hit = is_crit or (hit_total >= target_ac)
    
    damage_info = {"total": 0, "dice_total": 0, "rolls": [], "bonus": 0, "dice_str": damage_dice}
    damage_total = 0
    if is_hit:
        damage_info = roll_dice_detailed(damage_dice)
        damage_total = damage_info["total"]
        if is_crit:
            damage_total *= 2
        
    return {
        "hit_roll": d20_roll,
        "hit_modifier": hit_modifier,
        "hit_total": hit_total,
        "target_ac": target_ac,
        "is_hit": is_hit,
        "is_crit": is_crit,
        "damage_total": damage_total,
        "damage_dice_total": damage_info["dice_total"],
        "damage_rolls": damage_info["rolls"],
        "damage_bonus": damage_info["bonus"],
        "damage_dice_str": damage_info["dice_str"]
    }


