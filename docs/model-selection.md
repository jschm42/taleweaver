# Choosing LLM Models per Pass

This guide helps admins find the cheapest and fastest model that still works reliably for each
pass (**Administration → Intelligence**, and **Play-Agent**). The "?" button on every pass card
shows a short version of it (`frontend/src/components/admin/modelGuidance.ts`; keep both in sync).

The tiers below are an estimate from what each pass has to do, not a benchmark. Verify a
candidate with your own adventures (see [How to compare models](#how-to-compare-models)).

## Summary

| Pass | Minimum class | Where a too-weak model hurts | Save here? |
| --- | --- | --- | --- |
| 1 · Mechanics | Flash / mini (Gemini Flash, GPT-4.1-mini, Claude Haiku) with strict JSON schemas | Correctness: player actions get missed | No, not first |
| 2 · Narration | Flash / mini | Rule following and prose quality | Partly: stronger models mainly write better |
| 3 · World-Builder | Strong model, long context, reliable structured output | Invalid manifests, broken puzzles | No; runs rarely, so price matters little |
| 4 · Play-Agent | Flash / mini with structured output | Loops, no progress | Yes |
| 5 · Memory | Small / Lite | Forgotten facts in long games | Yes, the cheapest place to save |

Do not use the cheapest model for Pass 1. A weak Pass 1 makes the game feel broken, a weak
Pass 2 mostly makes it read worse.

## Pass 1 · Mechanics

The harder of the two turn passes. It has to:

- fill a large structured schema (`MechanicsIntent`) correctly: many optional fields
  (`given_items`, `npc_memories`, `triggered_soft_rule_ids`, `companion_order`, time fields,
  ...) that must be set exactly when they apply and left empty otherwise,
- pick exact entity IDs from a long CURRENT STATE block (often 5–15k tokens),
- resolve references such as "open it" or "give him the key" from the tail of the last
  narration, in any language,
- decide whether a sentence is an action or just talk (e.g. whether to set `new_scene_id`).

**Failure mode of a too-weak model.** Pass 1.5 (the guardrails) catches false positives:
invented IDs, impossible unlocks and unearned quest completions are reverted. It cannot catch
**false negatives**: when the model misses an action, nothing happens, and the game seems to
ignore the player. That is the typical failure of models that are too small.

**Minimum:** the Flash / mini class with strict JSON schema support and reliable instruction
following over long context.

- Flash-Lite / nano class: borderline. Simple turns work; expect missed handovers, NPC memory
  facts and soft rules.
- Open models around 8B parameters: not reliable for this schema.

## Pass 2 · Narration

Easier than it looks, because the outcome is already decided: the model mostly turns the TURN
RESOLUTION into prose. It still has to follow many directions:

- narrate a failure when there are rule violations instead of describing success,
- stop at an OPEN CHOICE instead of deciding it,
- the NPC KNOWLEDGE rule (characters who never met the protagonist do not know their name),
- never reveal lock secrets,
- TTS tags, the narrator persona and the player's language.

**Minimum:** the Flash / mini class. Smaller models write passable text but break these rules
more often, especially "do not decide the choice" and "narrate the failure". Prose in languages
other than English is noticeably weaker in small models. A stronger model mainly buys better
prose, not more correctness.

## Other passes

- **Pass 3 · World-Builder** produces long, strictly valid JSON manifests with consistent
  world logic, puzzles and scripts. Use a strong model with long context; it runs rarely, so
  speed and price matter least.
- **Pass 4 · Play-Agent** picks the next action from the known map, quests and inventory.
  Fights are played by a deterministic tactician, so the Flash / mini class is enough.
- **Pass 5 · Memory** summarizes older turns. A small / Lite model is enough; empty uses the
  Pass 1 model.

## Speed and cost

- **Turn thinking / reasoning off** for Pass 1 and Pass 2. It costs a lot of time to first
  token, and Pass 2 streams. If a non-reasoning model misses actions in Pass 1, try a "low"
  reasoning setting before switching to a bigger model.
- **Compare cached input prices, not list prices.** Both passes are input-heavy (Pass 1
  answers with a short JSON object). The system prompts are static and calls of a session are
  routed to the same endpoint, so most input tokens are cached; the price per cached input
  token decides the cost.
- **The small-model helper checks are easy.** The removal reference check, the hidden-entity
  reveal check and the handover recovery are short yes/no decisions that also use the small
  model.

## Capability test

Every pass card has two test buttons. **Test model** only checks that the model answers.
**Test capabilities** sends a few small fixed scenarios (in parallel) and checks the answers
deterministically (`backend/core/model_capability_probe.py`):

| Pass | Checks |
| --- | --- |
| 1 · Mechanics | valid JSON for the real Pass 1 schema; a German handover lands in `given_items` (`BRASS_KEY` → `GUARD_MIRA`); only IDs from the state; moving through an open exit sets `new_scene_id`; a question is treated as talk (no move, no handover) |
| 2 · Narration | visible text; the lock code stays secret; the failure is not narrated as success; the requested language (German) is used |
| 3 · World-Builder, 4 · Play-Agent | valid JSON for the Pass 1 schema, the handover and exact IDs |
| 5 · Memory | visible text; names and numbers survive the summary |

It is a quick screen: a model that fails here will likely break in play, a model that passes
is worth a real playtest. A request error or schema mismatch shows up as a failed check with
the reason.

The handover check sends "Hier, Mira, nimm meinen Messingschlüssel." ("Here, Mira, take my
brass key.") with no command: Pass 1 must recognize the handover and report it in
`given_items` as `BRASS_KEY` → `GUARD_MIRA`.

The setup wizard's Intelligence page has the same button for both of its models: the story
model is tested as Pass 2 (narration), the fast model as Pass 1 (mechanics).

### Speed rating

Both test buttons rate the speed of the slowest request as **fast**, **ok** or **slow**
(`backend/core/model_speed_rating.py`). The limits depend on the pass:

| Pass | Fast up to | Ok up to |
| --- | --- | --- |
| 1 · Mechanics | 2 s | 5 s |
| 2 · Narration (full passage) | 4 s | 9 s |
| 4 · Play-Agent | 3 s | 7 s |
| 5 · Memory | 5 s | 12 s |
| 3 · World-Builder | 8 s | 20 s |

The test prompts are short; real turns carry a larger state block and take somewhat longer, so
use the rating to compare models. Pass 2 streams in play, so the first words appear before the
full passage is done.

### OpenRouter provider check

A pass can pin OpenRouter providers in its **OpenRouter provider** field (e.g. `Groq`). If none of
them hosts the chosen model, OpenRouter rejects the request and the engine retries with the
providers OpenRouter offers or without any restriction, so play keeps working, but on another
provider. Many providers host only a few models; Groq, for example, does not serve Gemini or
GPT-4.1 models.

Both test buttons show which provider answered ("Served by Groq via OpenRouter."). When the
pinned provider was not used, a warning names the provider that served the request instead.
Pick a model the pinned provider hosts, or clear the field. The engine still logs every
fallback as a server warning (`OpenRouter provider routing failed ...`).

## How to compare models

1. Let the [Play-Agent](play-agent.md) play the same route (e.g. the Test-Lab) once per
   candidate model.
2. Compare latency p50/p90 per pass and the token usage incl. cached tokens
   (`gm.turn.pipeline.*` telemetry, see the `taleweaver-telemetry` skill).
3. Count rule violations and reverted updates in the debug inspector.
4. Read the chat log for missed actions: the only failure the guardrails cannot show.
