import random
from backend.models.avatar import Avatar
from backend.engine.stat_aggregator import calculate_total_stats

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
