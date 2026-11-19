"""Conversation beats: when present NPCs talk with each other on their own.

The engine decides deterministically whether a beat happens (``beat_due``) and who talks about
what (``plan_beat``); the narration only writes the lines. A beat never needs an extra LLM
call: it becomes a CONVERSATION BEAT direction in the Pass 2 turn message.

A beat happens

* always when the player listens (``/listen``), if two NPCs can talk,
* otherwise only with chatter on (adventure level and in-game setting):
  on arrival in a scene (``NORMAL`` and ``LIVELY``) or after a few player messages in the
  scene that addressed no NPC (``QUIET_GAP``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from backend.engine.conversations.relations import related
from backend.engine.conversations.topics import ConversationTopic, pick_topic

CHATTY_KEY = "chatty"
# Player messages without addressing an NPC before the NPCs talk on their own.
QUIET_GAP = {"RARE": 5, "NORMAL": 3, "LIVELY": 2}
ARRIVAL_LEVELS = frozenset({"NORMAL", "LIVELY"})
_SPEAKING_TYPES = frozenset({"HUMANOID", "BEING"})


@dataclass(frozen=True)
class BeatRequest:
    """What happened this message, as far as conversations care."""

    level: str
    player_enabled: bool
    listen: bool = False
    arrival: bool = False
    addressed_npc: bool = False
    quiet: int = 0


@dataclass(frozen=True)
class Beat:
    """A planned conversation between two present NPCs."""

    speaker_a: Any
    speaker_b: Any
    topic: ConversationTopic | None = None


def beat_due(request: BeatRequest) -> bool:
    """True when a conversation beat should happen in this narration."""
    if request.listen:
        return True
    if request.level not in QUIET_GAP or not request.player_enabled:
        return False
    if request.arrival:
        return request.level in ARRIVAL_LEVELS
    if request.addressed_npc:
        return False
    return request.quiet + 1 >= QUIET_GAP[request.level]


def _metadata(npc: Any) -> dict[str, Any]:
    raw = getattr(npc, "metadata_json", None)
    return raw if isinstance(raw, dict) else {}


def can_chat(npc: Any, quiet_companion_id: str = "") -> bool:
    """True for a present NPC that can hold a conversation (speaks, is conscious, not opted out)."""
    if str(getattr(npc, "entity_type", "") or "").upper() != "NPC":
        return False
    if getattr(npc, "is_hidden", False) or getattr(npc, "is_defeated", False):
        return False
    if str(getattr(npc, "npc_type", "") or "HUMANOID").upper() not in _SPEAKING_TYPES:
        return False
    if _metadata(npc).get(CHATTY_KEY) is False:
        return False
    return not quiet_companion_id or str(npc.id).upper() != quiet_companion_id.upper()


def _pair_key(a: Any, b: Any) -> list[str]:
    return sorted([str(a.id).upper(), str(b.id).upper()])


def _free_pair(speakers: list[Any], entity_states: Any, last_pair: list[str]) -> tuple[Any, Any]:
    pairs = [(a, b) for i, a in enumerate(speakers) for b in speakers[i + 1 :]]
    fresh = [p for p in pairs if _pair_key(*p) != last_pair] or pairs
    related_pairs = [p for p in fresh if related(p[0], p[1], entity_states)]
    return (related_pairs or fresh)[0]


def plan_beat(
    speakers: Iterable[Any],
    entity_states: Any,
    heard: set[str],
    guard: Callable[[str], bool],
    last_pair: list[str] | None = None,
) -> Beat | None:
    """Who talks about what; ``None`` with fewer than two speakers.

    An open authored topic wins; otherwise two NPCs (preferably related ones, and not the
    pair of the last conversation) talk about their own concerns.
    """
    present = list(speakers)
    if len(present) < 2:
        return None
    picked = pick_topic(present, heard, guard)
    if picked:
        topic, owner, partner = picked
        return Beat(owner, partner, topic)
    a, b = _free_pair(present, entity_states, last_pair or [])
    return Beat(a, b)


def beat_direction(beat: Beat, *, listen: bool) -> str:
    """The CONVERSATION BEAT direction for the narration."""
    a, b = beat.speaker_a, beat.speaker_b
    when = (
        "The protagonist keeps quiet and listens."
        if listen
        else "After the reaction to the player's action,"
    )
    if beat.topic:
        subject = f"about {beat.topic.topic}"
        convey = (
            f" The exchange must make this clear to a listener: {beat.topic.must_convey}."
            if beat.topic.must_convey
            else ""
        )
    else:
        subject = "about their own concerns (their goals, the place, each other)"
        convey = ""
    return (
        f"CONVERSATION BEAT: {when} {a.name} ({a.id}) and {b.name} ({b.id}) talk with each other "
        f"{subject}, in two to four short dialogue lines.{convey} The protagonist only overhears "
        "it: they do not address the protagonist, and the protagonist does not speak. Keep both "
        "in character and in line with their relations; the talk changes no game state."
    )


LISTEN_ALONE_DIRECTION = (
    "LISTENING: The protagonist keeps quiet and listens, but nobody here holds a conversation. "
    "Describe what can be heard instead (sounds of the place, a lone character muttering)."
)
