"""NPC conversations: characters talk with each other, not only with the protagonist.

* ``settings``: the adventure's ``npc_conversations`` switch (chatter level, gossip).
* ``state``: the session state in ``entity_states["__conversations__"]``.
* ``relations``: how NPCs see each other (``metadata_json["relations"]``).
* ``topics``: authored conversation topics with consequences (``conversation_topics``).
* ``chatter``: when the engine lets present NPCs talk (conversation beats).
* ``gossip``: memory NPCs pass facts about the protagonist on to related NPCs.
* ``ops``: replay of the ``tw.npcs`` conversation script operations.

Design notes: ``docs/specs/npc_conversations.md``.
"""
