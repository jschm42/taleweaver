# NPC Whispers (Concept)

Status: concept, not implemented. Builds on [NPC Conversations](npc_conversations.md) and NPC
memory ([world-builder-syntax.md](../world-builder-syntax.md#npc-memory)).

## Goal

A character can tell the protagonist something privately: the other characters present do not
hear it, do not react to it and cannot pass it on. The protagonist can whisper back.

Use cases:

- An informant whispers the password while the guard captain stands next to him.
- The companion quietly warns the hero about the merchant they are haggling with.
- A whispered secret stays safe, a secret said out loud spreads by gossip: the player has to
  choose how to share what they know.

## What exists already

| Piece | Where | Use for whispers |
| --- | --- | --- |
| Whisper delivery in TTS | vocal tags (`<whisper>`), `prompts.get_vocal_direction_prompt` | spoken style of whispered lines |
| Knowledge of the protagonist | NPC memory (`engine/rules/npc_memory.py`), NPC KNOWLEDGE rule in the GM prompt | the whisperer remembers what it shared |
| Spreading knowledge | gossip (`engine/conversations/gossip.py`) | must never spread whispered facts |
| Script directions | `tw.npcs.say_directed`, `tw.npcs.converse`, `tw.story.direct` | pattern for `whisper_directed` |
| Fixed lines | `tw.npcs.say` | pattern for `tw.npcs.whisper` |

What is missing is the notion of private knowledge: the narration is written from one
perspective, so everything said in a scene is public to every character present, and gossip
spreads facts no matter how a character learned them.

## Design

### 1. Secret store

Whispered facts are stored as secrets with the characters who know them, in the conversation
state (`entity_states["__conversations__"]["secrets"]`, part of every checkpoint):

```json
{"id": "back_door", "text": "The back door of the warehouse is unlocked after midnight.",
 "by": "INFORMANT", "knowers": ["INFORMANT"], "protagonist": true, "scene_id": "TAVERN",
 "minute": 615}
```

- `knowers`: NPC ids that know the secret (the whisperer, later more by script).
- `protagonist`: the hero knows it (always true for a whisper to the hero).
- Bounded list (newest N), one entry per id; a known id is replaced.

### 2. Prompt blocks

- **Pass 2 (narration)**: a SECRETS block in the CURRENT STATE, only for secrets whose knowers
  are present or that the protagonist may refer to: "Only Mira and the protagonist know: ...
  Every other character present acts as if they never heard it; nobody reacts to it, mentions
  it or hints at it."
- **Pass 1 (mechanics)**: the same block, so a player action that blurts the secret out loud can
  be recognized (see "Revealing a secret").
- A secret is only sent while at least one knower is in the scene, or while the protagonist acts
  on it; this keeps unrelated secrets out of the prompt (tokens, leak risk).

### 3. Gossip and memory rules (deterministic)

- Gossip never passes on a fact that came from a secret (secret facts carry `secret: true` in
  NPC memory, or are kept only in the secret store).
- Telling a secret on purpose is a script decision: `tw.secrets.reveal(id, to=npc_id)` adds a
  knower (betrayal, a bribed informant).

### 4. Authoring

- `tw.npcs.whisper(npc_id, text)`: a fixed whispered line plus a secret entry (id derived from
  the text or given with `secret_id=`).
- `tw.npcs.whisper_directed(npc_id, topic, must_convey="", secret_id=None, after=None)`: the next
  narration lets the NPC whisper about the topic; `must_convey` becomes the secret's text.
- Read access: `tw.secrets.known(id) -> bool`, `tw.secrets.knowers(id) -> list[str]`.
- Without code: a conversation-topic style NPC field `whispers` (`[{id, topic, must_convey,
  guard_expression, once}]`) that the engine offers when the protagonist talks to the NPC (or a
  `whisper: true` flag on `conversation_topics`).
- Trigger: `on_secret_shared` (target = secret id) for puzzles that react to the hero learning it.

### 5. Player side

- `/whisper <npc> <text>`: the hero whispers to a character in the scene. The message is saved
  with a whisper flag; Pass 1 gets the addressee, Pass 2 narrates a whispered answer, and other
  NPCs do not react.
- Typed forms ("I whisper to Mira: ...") are recognized by Pass 1 (`whisper_to` field), not by
  keyword matching (gameplay-guardrails rule 1).
- What the hero whispers can become a secret the NPC knows (NPC memory with `secret: true`).

### 6. Revealing a secret

When the protagonist says a secret out loud (Pass 1 reports `revealed_secret_ids`), every
character present becomes a knower and normal gossip rules apply from then on. This makes the
choice "whisper or say it" matter.

### 7. Presentation

- Chat: whispered lines are saved with a `whisper` flag; the story feed renders them as a muted,
  italic bubble with a small "whispers" label (and an ear or lock icon). Play-view skins style
  `.tw-bubble--whisper`.
- TTS: whispered lines get the whisper tag automatically.
- Debug inspector: a Secrets section (text, knowers, source, minute) next to the gossip log.

### 8. Chat history for Pass 2

Whispered messages stay in the history the narrator sees, marked as private
(`[WHISPER from Mira to the protagonist]`), so later narrations know they were not public.

## Risks

| Risk | Mitigation |
| --- | --- |
| The narrator leaks the secret through another character (the main risk; the LLM sees it) | explicit SECRETS rule last in the turn message, secrets only sent while a knower is present, whisper markers in the history; accept that narration cannot be enforced deterministically |
| Pass 1 misreads private talk (player side) | `/whisper` command as the reliable path; typed forms only through a dedicated intent field |
| Prompt growth | bounded secret store, scene-relevant secrets only |
| Confusion with gossip | one documented rule: whispered = never gossiped, said aloud = gossiped |

## Phases

1. Secret store, gossip rule, SECRETS prompt blocks, `on_secret_shared`, debug inspector section.
2. Script API (`tw.npcs.whisper`, `whisper_directed`, `tw.secrets.*`), whisper bubble style and
   TTS tag, Test-Lab demo (Vesper whispers something Nora must not learn).
3. Player side (`/whisper`, Pass 1 `whisper_to`, revealing a secret out loud), editor fields,
   blueprint keys, generation schema, docs (full engine-change checklist from `AGENTS.md`).

Effort: medium (about one phase of the NPC conversations feature per step).

## Open questions

- Should a companion always learn what the hero is whispered (it travels with them)?
- Can other characters notice that someone whispers (suspicion) without learning the content?
- Should whispering be possible in combat (e.g. a tactical hint from the companion)?
