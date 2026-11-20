"""World generation schemas for NPC conversations (relations, topics, adventure switch).

The manifest applier reads these fields (``engine/conversations/npc_fields.py``,
``engine/conversations/settings.py``); the schemas use ``extra="forbid"`` like every world
schema, so every field the applier reads must exist here.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from backend.engine.world.schema_base import WorldBaseSchema

RelationKind = Literal[
    "FRIEND",
    "FAMILY",
    "PARTNER",
    "ALLY",
    "COLLEAGUE",
    "SUPERIOR",
    "SUBORDINATE",
    "RIVAL",
    "ENEMY",
]


class NpcRelationSchema(WorldBaseSchema):
    """How this NPC sees another NPC."""

    npc_id: str = Field(..., description="ID of the other NPC.")
    kind: RelationKind = Field(..., description="How this NPC sees the other one.")
    note: Optional[str] = Field(
        None, description="Optional short reason in English (max 80 chars), e.g. 'owes her money'."
    )


class ConversationTopicSchema(WorldBaseSchema):
    """A topic this NPC talks about with another NPC while the protagonist can overhear it."""

    id: Optional[str] = Field(None, description="Short snake_case id (default: from the topic).")
    topic: str = Field(..., description="What the two talk about, in English (max 160 chars).")
    with_npc_id: Optional[str] = Field(
        None, description="ID of the partner NPC; null = any other NPC present."
    )
    must_convey: Optional[str] = Field(
        None,
        description=(
            "The clue the listener must learn from the talk (a code, a hiding place, a secret). "
            "Null for flavor-only topics."
        ),
    )
    guard_expression: Optional[str] = Field(
        None, description="Optional Python guard; the topic only comes up while it is True."
    )
    repeatable: Optional[bool] = Field(None, description="True: can come up again after heard.")
    on_heard_script: Optional[str] = Field(
        None, description="Optional Python script run once the protagonist overheard the topic."
    )
    on_heard_text: Optional[str] = Field(
        None, description="Optional system note shown once the protagonist overheard the topic."
    )


class NpcConversationsSchema(WorldBaseSchema):
    """Adventure switch: NPCs start conversations on their own; gossip spreads memories."""

    chatter: Literal["OFF", "RARE", "NORMAL", "LIVELY"] = Field(
        "OFF",
        description=(
            "How often present NPCs talk with each other on their own. NORMAL for lively places "
            "(taverns, markets, camps); OFF for lonely or horror adventures."
        ),
    )
    gossip: bool = Field(
        False,
        description=(
            "True: NPCs with memory slots tell related NPCs (friends, family, colleagues) what "
            "they learned about the protagonist."
        ),
    )
