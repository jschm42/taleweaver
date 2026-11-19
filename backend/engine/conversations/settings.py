"""The adventure's NPC conversation switch (``AdventureTemplate.npc_conversations``).

Stored as ``{"chatter": "OFF" | "RARE" | "NORMAL" | "LIVELY", "gossip": bool}``. A missing value
means chatter off and no gossip, so existing adventures keep their behavior. Present NPCs still
react to the protagonist (and to each other) inside a normal narration either way; the chatter
level only decides whether the engine also starts conversations by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.engine.conversations.state import player_chatter_enabled, read_conversations

NPC_CONVERSATIONS_FIELD = "npc_conversations"
CHATTER_OFF = "OFF"
CHATTER_LEVELS = (CHATTER_OFF, "RARE", "NORMAL", "LIVELY")


@dataclass(frozen=True)
class ConversationSettings:
    """Normalized adventure settings."""

    chatter: str = CHATTER_OFF
    gossip: bool = False

    @property
    def chatter_enabled(self) -> bool:
        return self.chatter != CHATTER_OFF


def _level(raw: Any) -> str:
    value = str(raw or "").strip().upper()
    return value if value in CHATTER_LEVELS else CHATTER_OFF


def parse_conversation_settings(raw: Any) -> ConversationSettings:
    """Settings from a stored or authored value; anything unknown falls back to off."""
    if not isinstance(raw, dict):
        return ConversationSettings()
    return ConversationSettings(chatter=_level(raw.get("chatter")), gossip=bool(raw.get("gossip")))


def normalize_conversation_settings(raw: Any) -> dict[str, Any] | None:
    """Stored form; ``None`` when everything is off (the default)."""
    settings = parse_conversation_settings(raw)
    if not settings.chatter_enabled and not settings.gossip:
        return None
    return {"chatter": settings.chatter, "gossip": settings.gossip}


def conversation_settings(adventure: Any) -> ConversationSettings:
    """The settings of an ``AdventureTemplate`` (or any object with the attribute)."""
    return parse_conversation_settings(getattr(adventure, NPC_CONVERSATIONS_FIELD, None))


def chatter_sheet_fields(raw_settings: Any, entity_states: Any) -> dict[str, Any]:
    """``sheet["npc_chatter"]`` for the in-game settings: level, availability, player switch."""
    settings = parse_conversation_settings(raw_settings)
    return {
        "level": settings.chatter,
        "available": settings.chatter_enabled,
        "enabled": settings.chatter_enabled and player_chatter_enabled(entity_states),
        # Two NPCs at the last message's place could talk (listening mode goes on); unknown
        # before the first message counts as possible.
        "listen_possible": read_conversations(entity_states).get("listen_possible") is not False,
    }
