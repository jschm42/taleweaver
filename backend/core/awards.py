from typing import Any

SPOILER_SEEKER_AWARD: dict[str, Any] = {
    "key": "SPOILER_SEEKER",
    "title": "Spoiler Seeker",
    "description": "Purchased the secret walkthrough for -150 XP.",
    "tier": "negative",
    "requirement": "Reveal the secret walkthrough for this adventure.",
}

GLOBAL_AWARDS: list[dict[str, Any]] = [
    SPOILER_SEEKER_AWARD,
]
