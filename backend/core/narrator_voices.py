"""Narrator voices: HOW the GM narrates (diction, rhythm, attitude), not how much.

The admin manages a catalog of voices (``User.narrator_voice_catalog``, defaults below). An
adventure stores its voice in ``AdventureTemplate.narrator_voice`` as a full copy
(``{"id", "name", "instruction", "sample"}``), so manifests and running sessions keep working
without the catalog. ``id == "custom"`` marks a voice written by the author in the editor.

Narration length stays with the player's narration style (``core/narration_styles.py``).
"""

from __future__ import annotations

import re
from typing import Any, Final, Optional

CUSTOM_VOICE_ID: Final = "custom"
MAX_NAME_LENGTH: Final = 80
MAX_DESCRIPTION_LENGTH: Final = 300
MAX_INSTRUCTION_LENGTH: Final = 1500
MAX_SAMPLE_LENGTH: Final = 500

DEFAULT_NARRATOR_VOICES: Final[list[dict[str, str]]] = [
    {
        "id": "campfire-storyteller",
        "name": "Weathered Campfire Storyteller",
        "description": "Grimdark / epic fantasy: rough, slow and marked by a hard life.",
        "instruction": (
            "Narrate like an old veteran by a crackling fire who has seen too many battles: weary, "
            "unhurried and gravelly, with a trace of warmth. Use plain, heavy words, slow sentences "
            "and the occasional short line that lands like a stone. Let hard-won wisdom and quiet "
            "irony show; never glorify violence."
        ),
        "sample": (
            "They tell you heroes die with a song on their lips. Don't believe a word of it. Out in "
            "the Ash Wastes, men just rust away, one cold breath at a time."
        ),
    },
    {
        "id": "noir-detective",
        "name": "Hardboiled Noir Detective",
        "description": "Cyberpunk / crime / thriller: cynical, dry and world-weary.",
        "instruction": (
            "Narrate like a hardboiled noir detective muttering to himself in a dark room: dry, "
            "cynical, almost bored by the rot of the world. Use clipped sentences, wry similes about "
            "rain, neon and bad decisions, and laconic understatement. Keep the tone low-key; "
            "never sound excited."
        ),
        "sample": (
            "Rain hit the neon sign outside my window like cheap static. She walked in carrying a "
            "briefcase full of bad decisions and a story she didn't expect me to buy."
        ),
    },
    {
        "id": "cozy-fireside",
        "name": "Cozy British Fireside Narrator",
        "description": "Whimsical / classic mystery: warm, articulate and gently mischievous.",
        "instruction": (
            "Narrate like a warm, articulate British storyteller by the fireside: inviting, gently "
            "theatrical and quietly mischievous. Use elegant, slightly formal phrasing, polite "
            "understatement and affectionate humour about the characters' small vanities."
        ),
        "sample": (
            "Now, it wasn't that Barnaby hated Mondays in particular. He simply objected to the "
            "rather rude manner in which they interrupted his perfectly good Sundays."
        ),
    },
    {
        "id": "breathless-thriller",
        "name": "Breathless Psychological Thriller",
        "description": "Suspense / horror: close, tense and quietly paranoid.",
        "instruction": (
            "Narrate close and tense, as if whispering into the player's ear: short, uneven "
            "sentences, sudden fragments, present-moment urgency and creeping paranoia. Speed up "
            "when danger rises. Leave threats half-seen; let what is not said do the work."
        ),
        "sample": (
            "Don't look at the mirror. Keep walking down the hall. Count the floorboards if you "
            "have to. Just don't stop when you hear the second set of footsteps."
        ),
    },
    {
        "id": "cold-chronicler",
        "name": "Cold Sci-Fi Chronicler",
        "description": "Hard sci-fi / dystopia: clinical, calm and quietly authoritative.",
        "instruction": (
            "Narrate like a detached chronicler or ship's log: precise, measured and almost "
            "emotionless, with calm authority. Prefer exact numbers, technical terms and plain "
            "statements of fact. Let horror and wonder come from the facts themselves, never from "
            "emotional adjectives."
        ),
        "sample": (
            "At four hundred million kilometers from Earth, silence isn't a metaphor. It is a "
            "physical law. When Hull Breach Seven registered on the telemetry, nobody screamed."
        ),
    },
    {
        "id": "witty-snark",
        "name": "Witty Snarky Sidekick",
        "description": "Urban fantasy / LitRPG: lively, self-ironic and fast.",
        "instruction": (
            "Narrate like a witty friend telling the story at a bar: energetic, conversational and "
            "full of dry sarcasm and self-irony. Use casual phrasing, rhetorical questions, comic "
            "asides and sudden changes of pace; poke fun at the hero's bad luck without mocking "
            "the player."
        ),
        "sample": (
            "So there I was: level two, armed with a rusty ladle, and staring down a demon lord who "
            "definitely skipped leg day. Honestly? Not even in my top five worst Tuesdays."
        ),
    },
    {
        "id": "gothic-ghost-story",
        "name": "Gothic Victorian Ghost Storyteller",
        "description": "Dark romance / classic horror: melancholic, poetic and theatrical.",
        "instruction": (
            "Narrate like a Victorian teller of ghost stories: melancholic, poetic and formal, "
            "savouring every word. Use long, flowing sentences, archaic elegance, personified "
            "houses and weather, and a lingering sense of decay and longing."
        ),
        "sample": (
            "Blackwood Manor did not merely stand upon the moor; it brooded there, drinking the "
            "autumn fog through cracked gargoyles and forgotten chimneys."
        ),
    },
    {
        "id": "action-pacer",
        "name": "High-Octane Action Pacer",
        "description": "Military / LitRPG / adventure: punchy, direct and urgent.",
        "instruction": (
            "Narrate like a high-octane action sequence: punchy, direct and rhythmic. Use short, "
            "hard sentences, strong verbs, countdowns and status calls, and keep the pulse high. "
            "Cut every word that slows the momentum; never pause for long descriptions."
        ),
        "sample": (
            "Shields down to ten percent. Two seconds to impact. Reyes slammed the manual "
            "override, braced his boots against the bulkhead, and prayed the welds would hold."
        ),
    },
    {
        "id": "southern-gothic-drifter",
        "name": "Southern Gothic Drifter",
        "description": "Americana / weird west / dark folk: earthy, slow and atmospheric.",
        "instruction": (
            "Narrate like a drifter on a porch in the deep South: earthy, unhurried and smoky, "
            "with a hint of dark folklore. Use colloquial rhythm, homespun metaphors of dust, heat, "
            "rivers and old wood, and a fatalistic calm."
        ),
        "sample": (
            "Round here, the river doesn't wash your sins away. It just drags 'em downstream and "
            "leaves 'em tangled in the cypress roots for the crows to pick at."
        ),
    },
    {
        "id": "epic-historian",
        "name": "Omniscient Epic Historian",
        "description": "High fantasy / historical fiction: majestic, dignified and sweeping.",
        "instruction": (
            "Narrate like the prologue of a great epic: majestic, dignified and omniscient, as if "
            "recounting history from centuries later. Use sweeping sentences, a sense of grand "
            "scale and ancient wisdom, and occasional foreshadowing of what fate holds."
        ),
        "sample": (
            "Three centuries before the crown was forged in dragonfire, the northern valleys "
            "belonged to the wind and the wolves. Empires were nothing more than a rumor in the "
            "south."
        ),
    },
]


def _clean(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize_voice(raw: Any) -> Optional[dict[str, str]]:
    """A clean voice entry, or None when it has no instruction to narrate by."""
    if not isinstance(raw, dict):
        return None
    instruction = _clean(raw.get("instruction"), MAX_INSTRUCTION_LENGTH)
    if not instruction:
        return None
    name = _clean(raw.get("name"), MAX_NAME_LENGTH)
    voice_id = _clean(raw.get("id"), MAX_NAME_LENGTH) or _slugify(name) or CUSTOM_VOICE_ID
    return {
        "id": voice_id,
        "name": name or ("Custom" if voice_id == CUSTOM_VOICE_ID else voice_id),
        "description": _clean(raw.get("description"), MAX_DESCRIPTION_LENGTH),
        "instruction": instruction,
        "sample": _clean(raw.get("sample"), MAX_SAMPLE_LENGTH),
    }


def default_narrator_voices() -> list[dict[str, str]]:
    return [dict(voice) for voice in DEFAULT_NARRATOR_VOICES]


def normalize_voice_catalog(raw: Any) -> list[dict[str, str]]:
    """The admin catalog without broken or duplicate entries; empty falls back to the defaults."""
    voices: dict[str, dict[str, str]] = {}
    for entry in raw if isinstance(raw, list) else []:
        voice = normalize_voice(entry)
        if voice and voice["id"] != CUSTOM_VOICE_ID:
            voices.setdefault(voice["id"], voice)
    return list(voices.values()) or default_narrator_voices()


def narrator_voice_rules(voice: Any) -> str:
    """Narration prompt block for the adventure's voice; empty without one."""
    clean = normalize_voice(voice)
    if clean is None:
        return ""
    sample = (
        f' Style sample (match its voice, never reuse its content): "{clean["sample"]}"'
        if clean["sample"]
        else ""
    )
    return (
        f"NARRATOR VOICE — {clean['name'].upper()}: {clean['instruction']}{sample} "
        "The voice shapes word choice, sentence rhythm and attitude of the narration in the "
        "response language. It never overrides the length rules, the formatting rules or the "
        "facts of the turn, and NPCs keep their own way of speaking in their dialogue lines."
    )
