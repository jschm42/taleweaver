# NPC Conversations

Status: implemented (manifest format 1.4.0).

NPCs already react to the protagonist and to each other inside a normal narration (GM prompt,
NPC INITIATIVE RULE). This feature adds conversations between NPCs that the engine starts by
itself, gives them direction (relations), lets authors plan clues the player can overhear
(topics), and lets NPCs pass on what they know about the protagonist (gossip).

Authoring syntax: [world-builder-syntax.md](../world-builder-syntax.md#npc-conversations).
Scripting API: [scripting_engine.md](../scripting_engine.md#twnpcs).

## Decisions

| Question | Decision |
| --- | --- |
| Who switches chatter on? | The author per adventure (`npc_conversations.chatter`, editor page *Logic → NPC conversations*), the player per session (in-game settings, Narrator tab), and the player per message (`/listen`, works even with chatter off). |
| Does `/listen` cost time? | Yes. It is a normal player message, so the clock ticks once. |
| Extra LLM calls? | None. A conversation is a direction in the Pass 2 turn message (CONVERSATION BEAT). |
| Gossip? | Yes, adventure switch `npc_conversations.gossip`, deterministic, no LLM. |
| Authored conversations | Both kinds in scripts: fixed lines (`tw.npcs.converse(..., lines=[...])`) and directed topics (`topic=`, `must_convey=`). Without code: `conversation_topics` on the NPC. |

## Data

* NPC `metadata_json`: `relations` (`[{npc_id, kind, note}]`, directed), `chatty` (only `false`
  is stored), `conversation_topics` (`[{id, topic, with_npc_id, must_convey, guard_expression,
  repeatable, on_heard_script, on_heard_text}]`).
* Adventure column `npc_conversations`: `{chatter: OFF|RARE|NORMAL|LIVELY, gossip: bool}`;
  `null` = all off. Sessions read their adventure snapshot copy.
* Session: `entity_states["__conversations__"]`: `player_off`, `scene`, `quiet`, `last_pair`,
  `heard`, `pending_beat`, `relations` (script overrides). Part of every checkpoint.

## Turn flow

1. `/listen` maps to `[TRIGGER_LISTEN]`; the turn runs as a normal player action
   ("I keep quiet and listen…") with `manager.listen_requested = True`.
2. After interaction triggers, `on_logic_pass_done` and the in-game turn change,
   `plan_conversation_beat` decides (`engine/conversations/chatter.py`):
   * skipped in the opening prologue, `/continue_story`, while a choice is open and in combat;
   * a new scene resets the quiet counter and counts as arrival;
   * `/listen` always plans a beat; otherwise chatter must be on (adventure and player) and
     either the protagonist arrived (`NORMAL`, `LIVELY`) or enough messages addressed no NPC
     (`RARE` 5, `NORMAL` 3, `LIVELY` 2);
   * speakers: visible, undefeated `HUMANOID` / `BEING` NPCs in the scene, not `chatty: false`,
     not a companion with `banter: QUIET`;
   * an open topic (not heard or repeatable, partner present, guard true) wins; else two NPCs,
     preferably related and not the last pair.
3. The direction is stored as `pending_beat`; a planned topic counts as heard immediately:
   world memory "Overheard: …", `on_heard_script` / `on_heard_text`, `on_conversation_heard`
   scripts (target = topic id). Never parsing the narration keeps the rule "state, not text".
4. Pass 2 takes `pending_beat` once as a reminder. Its CURRENT STATE carries NPC RELATIONS for
   related NPCs present together.
5. At every in-game turn change, with gossip on, `spread_gossip` lets memory NPCs in the same
   scene pass one own (non-hearsay) fact per pair to an NPC they have a sharing relation to
   (all kinds except `RIVAL`, `ENEMY`); the listener stores it as "Heard from <name>: …".

## Limits

* One beat per message, two to four lines, the protagonist only overhears.
* Gossip never overwrites a fact the listener already has and never re-shares hearsay.
* Topic ids share one "heard" flag across NPCs; the validator warns about duplicates.
