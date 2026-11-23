# Staged World Generation (Concept)

Status: draft, not implemented. Builds on [world_sections.md](world_sections.md) and
[region_builder.md](region_builder.md).

---

## 1. Problem

`WorldGenerator.generate_world` (`backend/engine/world/world_generator.py`) asks the LLM for
the complete `WorldManifesto` in **one** structured call: adventure meta, protagonist, all
scenes, exits, NPCs, objects, sequences, quests, awards, scripts and the init script.

The size of that answer grows with the adventure, but every model has a hard output cap that
the configured `max_tokens` cannot raise. Example (error `1fe8ffc03c`, "The Crimson Debt"):
`google/gemini-4-neon` via OpenRouter, configured limit 200,000, stopped at 65,536 output
tokens, of which 19,682 were reasoning. The manifest JSON was cut off and the whole
generation failed; nothing of the work was kept.

Consequences today:

* Large adventures cannot be generated with models whose output cap is 32k or 64k.
* Reasoning models spend part of the cap on thinking, so the usable size shrinks further.
* A failure late in the answer loses everything; a retry pays the full cost again.

## 2. Goals

1. No single LLM call has to produce more than a bounded part of the world, so the size of
   an adventure is no longer limited by the model's output cap.
2. Same input as today: the Generate adventure page, its options and blueprints work
   unchanged. The result is an ordinary adventure template.
3. A failed step is retried on its own; finished steps are kept, and a failed job can be
   resumed.
4. The progress view shows which step runs ("Building region 2 of 4: The Docks").
5. Reuse the region path (`section_generator`, `section_validation`, `section_merge`,
   `section_gateways`, region-mode blueprints) instead of building a second one.

Non-goals:

* A free-running tool-calling agent that decides its own steps (section 3).
* Changing the Region Builder or the expansion of running sessions.
* Parallel generation of regions (possible later, section 11).

## 3. Approach: fixed pipeline, not a free agent

A tool-calling agent (`create_scene`, `add_npc`, ... in a loop) was considered and rejected:

* many round trips, so slower and more expensive than a fixed number of calls;
* nondeterministic step order, hard to validate, resume and test;
* tool-calling quality differs a lot across the supported providers (OpenRouter, custom
  OpenAI endpoints, Ollama); the generator today only needs structured output.

Instead the job runs a fixed sequence of structured calls. Each one has its own schema and
its own validation; only the *number* of region steps depends on the adventure.

```
Skeleton ──► Region 1 ──► Region 2 ──► ... ──► Logic pass ──► Validate & fix ──► Media
   │            │            │                     │                │
   └─ stored ───┴─ merged ───┴─ merged ────────────┴─ merged ───────┘  (each step persisted)
```

## 4. Mode selection

New generation option `generation_mode`: `auto` (default) | `single` | `staged`.

* `single`: today's one-call path, unchanged.
* `staged`: always the pipeline.
* `auto`: staged when `max_scenes` exceeds `STAGED_SCENE_THRESHOLD` (default 10) or the
  blueprint declares more than one `[Section]`; otherwise single. A single-call generation
  that fails with `LLMTruncatedResponseError` is **not** retried automatically in staged
  mode (it would double the cost unasked); the error message suggests staged mode instead.

Shown on the Generate adventure page under *Advanced → Generation* with an info popover.

## 5. Step 1: Skeleton

One call, schema `WorldSkeleton` (new, `backend/engine/world/skeleton_schemas.py`). It fixes
everything that must be consistent across regions, but no full texts or entity details.

| Part | Content |
| --- | --- |
| Meta | All non-list fields of `WorldManifesto`: teaser, plot, rules, intro text, language, cover appearance, completed / game-over conditions and guards, game-over rules, NPC conversations, fast travel, damage flags, sequence progression mode, audio tracks |
| Protagonist | Full `ProtagonistSchema` (small, needed by every later step) |
| Regions | `id`, `label`, `description`, `brief`, `map_x`/`map_y`, `scene_budget` |
| Scene stubs | `id`, `label`, `section_id`, one-line `purpose` |
| Connections | `from_scene_id`, `to_scene_id`, `cross_region`, optional lock hint (`key:<item id>`, `code`, `rule`) |
| Key NPCs | `id`, `name`, `section_id`, `scene_id`, one-line `role` |
| Key items | `id`, `name`, `section_id`, `used_for` (e.g. "unlocks VAULT_DOOR in region DOCKS") |
| Chapters | sequence outline: `id`, `title`, `goal`, scene ids, order |
| Quest outline | `id`, `title`, `type` main/side, `section_id` hint, one-line objective |

Rules for the skeleton prompt:

* Region count = `ceil(max_scenes / SCENES_PER_STEP)` (default 6, section 9), at least 1.
* Every puzzle that spans regions (key in A, lock in B) must appear as a key item plus a
  connection with a lock hint; this is the only place where cross-region logic is decided.
* Ids follow the existing conventions (`preprocess_manifest_object_ids`).

After the skeleton the job writes the meta fields, the protagonist and the regions (status
`stub`, with brief) into the template. The skeleton itself is stored (section 8).

The cover-source options (`cover_source_manifest`, similarity) go into the skeleton prompt
only; later steps see the skeleton, not the source adventure.

## 6. Step 2: Regions

One call per region, in skeleton order, through the existing region path
(`section_generator.generate_section`), extended by a **reservation block**:

* the region's scene stubs, key NPCs and key items must be created with exactly these ids;
* the region's connections, including cross-region ones whose other side is already built
  (gateways come from `section_gateways.built_neighbours` as today);
* the quest and chapter outline lines that touch this region, as context only.

Validation (`section_validation.validate_section`) gets one more check: every reserved id of
the region exists in the result. Missing ids are errors and trigger the existing retry with
the errors in the prompt (`MAX_ATTEMPTS`).

Cross-region exits whose target region is not built yet are kept in the stored skeleton and
created deterministically when the target region is merged (both scene ids are reserved, so
no LLM call is needed). Lock fields come from the lock hint.

Region steps generate no quests, awards, sequences or scripts of their own except local
side content allowed by the options (section 7 owns everything global). Images are drawn
during the merge as today (`section_media`), according to the media options.

Every adventure keeps at least one region (default region rule). Whether the region steps
become **visible regions** is a choice:

* `split_regions: true` (default when the blueprint or the author asks for several regions,
  or `max_scenes` is large): regions stay as built; the world map appears from two built
  regions on (`sections.world_map_enabled`).
* `split_regions: false`: the steps are internal chunks; after the logic pass all scenes are
  moved into the default region `MAIN` and the chunk regions are removed. The player sees
  one region and no world map.

## 7. Step 3: Logic pass

One call, schema `WorldLogic`: `sequences` (full, incl. soft rules and sequence scripts),
`quests`, `awards`, `scripts`, `init_script`. The prompt gets the skeleton outline plus the
ledger of the built world (`section_ledger`, ids and one-line texts of all scenes, NPCs,
objects, exits). It may only reference existing ids; unknown ids are validation errors and
trigger one retry.

When the options disable quests, awards or scripts (chat mode, toggles), those lists are
not requested at all. If the logic output alone is too large (many sequences with scripts),
it is split into `sequences+quests+awards` and `scripts+init_script` (two calls).

## 8. Job state, retry and resume

New JSON column `AdventureTemplate.generation_plan` (Alembic migration):

```json
{
  "mode": "staged",
  "skeleton": { "...": "WorldSkeleton" },
  "steps": [
    {"id": "skeleton", "status": "done"},
    {"id": "region:DOCKS", "status": "done"},
    {"id": "region:OLD_TOWN", "status": "failed", "error_id": "1fe8ffc03c"},
    {"id": "logic", "status": "pending"},
    {"id": "validate", "status": "pending"}
  ],
  "settings": { "...": "the original CreateAdventureTemplatePayload" }
}
```

* Each step commits its result before the next one starts.
* A failed step leaves `creation_status = "failed"`; the template is not playable (it is
  not listed for play until `creation_status` is ready).
* `POST /adventures/{id}/generation/resume` (owner only) restarts the job at the first step
  that is not `done`. The progress dialog's error card gets a **Resume** button next to
  Copy / Save.
* Deleting the adventure or starting a new generation discards the plan. After a successful
  run the plan is cleared except `mode` (the skeleton is not needed later).

## 9. Output budget per step

`SCENES_PER_STEP` (default 6) bounds a region step. A server setting
`staged_scenes_per_step` lets the admin tune it for models with small output caps.

When a region step fails with `LLMTruncatedResponseError`, the job splits the region's scene
stubs into two halves and runs them as two calls for the same region (second call with the
first half in the ledger), once. Only if that also truncates does the step fail.

## 10. Blueprints

`prepare_blueprint` runs once on the whole blueprint as today; the blocks are then
distributed:

| Blueprint content | Goes to |
| --- | --- |
| World keys (title, plot, style, tone, language, rules ...) | Skeleton (fixed values written over the LLM result, as `_apply_blueprint_to_manifest` does today) |
| `[Section]` blocks | Skeleton regions (fixed ids, labels, briefs) |
| `[Scene]` with `section:` / scenes reached from a section | That region's step, as a region-mode blueprint (`engine/blueprint/region_mode.py`) |
| Scenes without a region | Skeleton assigns them; their blocks follow into that region's step |
| `[NPC]` / `[Item]` with `in: <scene>` | The region of that scene |
| `[NPC]` / `[Item]` with `in: <zone>` | Unchanged: dynamic zone (`zone_entities.move_zone_entities`) |
| `[Exit]` | The region of its `from` scene; cross-region exits are reserved in the skeleton |
| `[Sequence]`, `[Quest]`, `[Award]`, `[Script]` | Logic pass |

All blueprint ids are reserved in the skeleton, so a later step can rely on them. After each
step its blueprint subset is applied over the step's result (`apply_region_blueprint`), as
the Region Builder does today.

## 11. Cost and latency

* Calls: 1 skeleton + R regions + 1-2 logic (+ fix). For 24 scenes: about 6 calls instead
  of 1.
* Output tokens stay about the same; input tokens grow (skeleton + ledger per step). The
  system prompts are static per step type so provider prompt caching applies.
* Latency grows roughly with the number of calls. Region steps whose neighbours are all
  built could later run in parallel; V1 runs them in order, because gateways need the
  neighbour's scenes.

## 12. Progress and telemetry

* Status lines through the existing `status_callback`: "Planning the world...",
  "Building region 2 of 4: The Docks...", "Writing quests and scripts...",
  "Checking the world...".
* LLM operations: `generate_world_skeleton`, `generate_section` (existing),
  `generate_world_logic`; `log_structured_event("adventure.generation.step", step=..., ...)`
  per step with duration and token usage.
* The generation summary counts created entities over all steps.

## 13. Affected code (V1)

| Area | Change |
| --- | --- |
| `engine/world/world_generator.py` | dispatch on `generation_mode`; the staged job lives in a new `engine/world/staged_generation/` package (skeleton, region step, logic pass, plan state), not in the generator file |
| `engine/world/section_generator.py`, `section_prompt.py`, `section_validation.py` | reservation block and reserved-id check |
| `engine/manifest_apply/` | apply skeleton meta; deferred cross-region exits; chunk-to-`MAIN` fold for `split_regions: false` |
| `engine/blueprint/` | block distribution (section 10) |
| `api/routes/adventures/adventure_creation.py` | job runs the pipeline; resume endpoint (+ session-ownership style owner check) |
| `models/adventure_template.py` + migration | `generation_plan` column |
| Schemas / payload | `generation_mode`, `split_regions` |
| Frontend | option on the Generate page, step progress, Resume button |
| Docs | this spec, `world-builder-blueprint-manual.md` (section 10 behavior), `adventure_generation.mermaid` |

## 14. Tests

* Skeleton → region steps → logic pass with a mocked LLM: the final template equals a
  single-call template of the same content (scenes, exits, NPCs, objects, quests).
* Reserved ids missing in a region result → retry with the error, then failure.
* Cross-region exit with the target built later is created on the later merge.
* Truncation in a region step → split into two calls.
* Resume after a failed region step continues at that step and keeps finished regions.
* Blueprint distribution: each block kind reaches its step and its fixed values survive.
* `split_regions: false` → one region `MAIN`, no world map.

## 15. Phases

| Phase | Content |
| --- | --- |
| A | Skeleton schema + prompt, `generation_plan`, region steps with reservations, logic pass, `generation_mode` (`single` / `staged`) |
| B | Resume endpoint and UI, truncation split, `auto` mode |
| C | Blueprint distribution |
| D | `split_regions: false` fold, admin setting `staged_scenes_per_step` |

## 16. Open questions

1. Threshold of `auto` mode: scene count, or an estimate of output tokens from all min/max
   options?
2. Should validate & fix (AI fix) run automatically at the end, or only report findings as
   the Region Builder does?
3. Can a staged generation be cancelled halfway and the partial world kept for editing?
