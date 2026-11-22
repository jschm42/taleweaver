# Region Builder (Concept)

Status: phases A, B and C implemented; D open (section 13). Replaces the generation UI of
[world_sections.md](world_sections.md) section 9.4 (brief field + **Generate region** button).
Planning (9.3), validation and merge (9.5), the blueprint `Section` kind (9.6) and the
expansion of running sessions (9.7) stay as they are, apart from the changes listed here.

---

## 1. Problem

Today a planned region is generated from one text field (the brief). The author cannot:

* set size, features, strictness or media, as on the **Generate adventure** page;
* give a blueprint for the region, so key scenes, NPCs and puzzles are left to chance;
* choose which parts of the existing world go into the prompt. The ledger
  (`section_ledger.py`) is always sent whole and cut at 14,000 characters, so a large
  adventure loses the end of its lists without the author knowing, and a small region pays
  for context it does not need.

## 2. Goals

1. A **Region Builder** in the editor that looks and works like the Generate adventure page:
   Simple / Advanced, the same cards, the same Generate bar and progress stream.
2. Every generation option of a new adventure, except the global attributes of the
   adventure (section 4.3).
3. **Context options**: the author chooses which parts of the existing world are injected
   into the prompt. All are on by default; each shows its estimated token cost.
4. **Blueprint input**: the region's idea field accepts World-Builder blueprint syntax. Its
   fixed values are written over the LLM output, as for a new adventure.
5. Settings are remembered per region, so a failed or discarded region can be regenerated
   with one click.

Non-goals: changing existing content (the builder stays additive, section 7.4), generating
several regions in one job, editing the campaign outline from the builder.

## 3. Entry points

| Where | Action | Result |
| --- | --- | --- |
| Regions page, planned region | **Build region...** (replaces *Generate region*) | Builder opens for that region |
| Region card after a failed job | **Retry...** | Builder opens with the stored settings and the error shown |

A new region is added with **Add region** and saved as before, then built with *Build
region...*; a separate *New region...* button would only duplicate that. The button is
disabled while the Regions page has unsaved changes, because the builder reads the saved
region.

**Plan regions** stays as it is. The brief it writes is the builder's starting idea text.

The builder is a sub-page of the editor (`RegionBuilderPage.vue`, route
`/adventures/:adventureId/editor/regions/:sectionId/build`, name
`adventure-editor-region-build`), like the character and item detail pages: it keeps the
editor sidebar with *Regions* marked, reads the editor data and has no shell save bar. It is
not a modal, because it has as many cards as the Generate adventure page. **Build region**
saves the name and description with the region list, starts the job and returns to the
Regions page, which polls until the region is built (region generation has no progress
stream).

## 4. Builder options

### 4.1 Layout

Page header: *Build <region>*, the **Simple / Advanced** switch and a way back to Regions.
Sticky bottom bar (`RegionBuildBar.vue`): estimated prompt size (warning above 40k tokens),
*Preview prompt* (advanced) and **Build region** with the reason when it is disabled.
*Validate & fix afterwards* joins the bar in phase D.

Cards, top to bottom:

1. **Region**: name and description (saved with the region before the job starts), links
   to neighbouring regions with travel time, read-only (drawn on the Regions map).
2. **Region idea**: the region's brief. Free text now; blueprint input in phase C.
3. **World context**: the injection options (section 5), *All on* / *All off*, a token badge
   per option and the always-included gateway scenes.
4. **Region size**: simple mode a preset; advanced mode the ranges of scenes, items,
   chapters, side quests, containers, readable texts and awards (with their switches, the
   shared `LimitRow`), event scripts and strictness.
5. **Inherited from the adventure** (read-only, collapsed): the global attributes of 4.3,
   with a link to the page where each is changed.
6. **Images & voices**: scene, NPC and item images, NPC voice assignment. Phase D.

### 4.2 Simple vs. advanced

| Option | Simple | Advanced |
| --- | --- | --- |
| Region name, description, links | yes | yes |
| Region idea / blueprint | yes | yes |
| Context options (on/off) | yes | yes |
| Context detail level, walkthrough split, prompt preview | – | yes |
| Region size | preset: *Small* (3-5 scenes), *Medium* (6-10), *Large* (11-16) | min/max per category |
| Feature switches | all on | each switch |
| Strictness | creative | creative / strict |
| Images & voices | one switch "Generate images" + voices on | each switch |
| Validate & fix afterwards | on | switch |

Switching to Simple resets the advanced-only fields to the simple defaults
(`applySimpleDefaults` pattern), like the Generate adventure page.

### 4.3 Not offered (global attributes)

Inherited from the adventure and only shown in card 7: title, language, rule mode (rpg /
story / chat), combat damage rules, time system and pacing, image style, protagonist, cover,
narrator persona. The image style must stay global, or the new region's pictures would not
match the rest of the world.

Tone is global too. The region gets its mood from the idea text ("colder and lonelier than
the coast"), not from a second tone pick.

## 5. Context options

### 5.1 The options

All on by default. Each is one prompt block, built from the database at job start.

| Option | Block content | Default detail |
| --- | --- | --- |
| **Other regions** | id, name, status, summary (built) or description and brief (planned), links with travel time | full |
| **Campaign outline** | premise, arc, this region's purpose / gating / plants / resolves, open threads | full |
| **Chapters (sequences)** | order, title, description, goal and completion condition; **walkthrough** per chapter | full, walkthrough clipped to 600 chars per chapter |
| **Quests** | id, title, main/side, objective, region hint, required item / scene / NPC | full |
| **Global plot** | adventure plot, teaser and lore context | full |
| **World rules** | adventure `rules` text and the rule-relevant settings (combat damage, game-over rule) | full |
| **Characters (NPCs)** | id, name, scene and region, role / one-line description, relations | compact |
| **Scenes** | id, label, region (full: plus the first 400 chars of the description) | compact |
| **Items** | id, name, type, holder, what it unlocks (full: plus description, quest item flag) | compact |

*Campaign outline* is not in the original wish list. It is added because the outline is how
regions plan threads for each other (world_sections.md 9.1); without it the generated
`thread_updates` have no base. It is hidden when the adventure has no outline.

### 5.2 Always included

These are not options, because the region cannot be built without them:

* the adventure frame: title, language, rule mode, tone label;
* the target region (card 1) and the region idea;
* the **gateway scenes** of the linked, built neighbours, in full (so exits can be wired);
* the size and feature requirements of cards 4-5;
* the id rule (section 5.4).

### 5.2a Choosing the gateway scenes

Today `section_prompt._gateway_block` lists the first 8 scenes of each linked, built
neighbour **sorted by id**, so they are not necessarily the scenes at the region's border.
The builder chooses them like this:

1. Scenes the author picked in card 1 per link (new optional `gateway_scene_ids` on a
   planned link; the blueprint sets it implicitly through an `Exit` from an existing scene).
   Implemented: `GatewayScenePicker.vue` in card 1; picks are saved with the region list
   before the build, and the preview request carries unsaved picks (`gateways`).
2. Otherwise (implemented in `engine/world/section_gateways.py`) the neighbour's scenes that already have an exit leading out of the region or
   are fast travel points, then the rest, up to 8.

Without any built neighbour (the region has no `planned_links` to a built region),
validation still demands one exit to an existing scene ("No exit connects the region to an
existing scene"). The gateway block then lists fallback candidates (the start scene, fast
travel points and scenes without a region, up to 8), so the region can be connected even
with the *Scenes* option off.

### 5.3 Detail levels (advanced)

Each option offers `compact` / `full` where it makes a difference:

* Scenes, NPCs, items: `compact` = id, name and location only (items also what they
  unlock); `full` = plus description (scenes 400 chars, NPCs 300, items 200), character
  relations and the quest item flag.
* Chapters: walkthrough is its own sub-switch (*include walkthroughs*), default on.
* Other regions: `compact` = id, name, status only.

### 5.4 Token estimate and the cost hint

The **World context** card starts with the note:

> Every option adds context to the prompt. More context keeps the region consistent with the
> rest of the world, but costs more tokens and makes generation slower.

Each option shows `≈ 1.2k tokens`; the bar shows the total of all blocks (always-included
blocks plus the chosen options). The numbers come from the preview endpoint (section 8.2),
estimated as characters / 4 and labelled as an estimate. Above 40k tokens the total turns
into a warning ("Large prompt: consider compact detail for scenes, characters and items").

An option whose block is empty (no quests yet) is shown disabled with "nothing yet".

### 5.5 What turning an option off means

Turning an option off only removes it from the **prompt**. The full ledger is still built
for the deterministic checks (`section_validation.py`): id collisions, references, keys.
Two consequences need engine changes:

* **Id collisions without the lists.** With scenes, NPCs or items off, the LLM cannot see
  the taken ids. The prompt then asks for ids prefixed with the region id (`GLOOM_PEAKS` ->
  `GP_`), and `prepare_section` renames a colliding id deterministically (`<ID>_2`, all
  references in the region rewritten) instead of rejecting the region. Each rename is a
  generation note.
* **References to unknown content.** With items off, the region cannot reuse an existing
  key; that is expected. A reference to an id that exists in the ledger but was not in the
  prompt stays valid (the blueprint may name it, section 6.3).

## 6. Blueprint input

### 6.1 Syntax

The region idea (`RegionIdeaCard.vue`, up to 20,000 characters, stored as the region's
`brief`) takes the same syntax as the Story Idea, with the same `BlueprintSyntaxHelp`. Plain
text is a free brief; text with blueprint tags is parsed in **region mode**
(`engine/blueprint/region_mode.py`, `analyze_region_blueprint`). The text before the first
tag becomes the brief the prompt shows; the blocks become a prompt block of their own
(`blueprint`, between the region and the requirements). The user manual's example
("A blueprint for one region") is checked against the region-mode validator.

```text
Frozen dwarven ruins above the harbor. The surveyor's trail ends at a collapsed gatehouse.

[Scene: GP_GATEHOUSE] Ruined Gatehouse
fast_travel: yes
Ice-crusted gate, a broken winch.

[Exit: HARBOR_SQUARE -> GP_GATEHOUSE] the mountain road
travel: 8h

[NPC: GP_HERMIT] Old Brann
in: GP_GATEHOUSE

[Sequence: 1] Into the peaks
goal_scene: GP_GATEHOUSE
```

### 6.2 Region mode rules

| Kind | In region mode |
| --- | --- |
| `Scene`, `Exit`, `NPC`, `Item`, `Switch`, `Script`, `Sidequest`, `Award` (with their `Rule`, `Ability` children) | allowed, as in a new adventure |
| `Sequence` | allowed; numbers are local (1, 2, ...) and are appended after the existing chapters (`prepare_section`) |
| `World`, `Protagonist`, `Audio` | global; warning, block ignored |
| `Section` | warning, block ignored: the region is edited in the builder's Region card |

* `section:` on scenes may be left out; it defaults to the region being built. Another
  region is an error.
* `fixed` / `hint` / `open` keys work as for a new adventure. After the LLM call the fixed
  values are written over the region with `apply_blueprint(region, blueprint,
  known_scene_ids=ledger.scene_ids)` (exits may join existing scenes), then
  `prepare_section` runs. Entries the LLM left out and the merge cannot create become
  generation notes (`Blueprint: ...`).
* Strictness `strict` uses the blueprint's strict wording: keep its structure and add only
  what makes it playable or what the counts demand.
* The prompt section starts with REGION BLUEPRINT NOTES (existing ids are references, local
  chapter numbers).

### 6.3 References to existing content

A blueprint may **reference** existing ids, never redefine them: exit ends, keys, quest and
chapter requirements, relations. Referenced ids of the adventure are not reported as
missing (only ids that exist nowhere are, and the LLM is told to create them).

* A block whose id already exists (`[NPC: HARBORMASTER]`) is an error: "exists already; the
  Region Builder only adds content".
* An exit whose both ends are existing scenes is an error ("only joins existing scenes").
* An exit to an existing scene outside the linked regions is a warning (only when the region
  has links; without links any existing scene is a fitting gateway).

Errors block the build: the preview reports them (8.2), the page disables **Build region**,
and `POST .../generate` answers 400 before the job starts; the job itself refuses them too.

## 7. Generation job

### 7.1 Flow

```
Build region
  -> save region fields (card 1) and generation_settings
  -> status generating, progress stream starts
  -> build ledger (full) + context blocks (chosen options)
  -> parse blueprint (region mode)
  -> LLM: SectionManifest
  -> apply_blueprint -> prepare_section (incl. id renames) -> validate_section
       on errors: one retry with the errors (as today)
  -> merge_section
  -> media phase (optional): scene, NPC, item images; voice assignment
  -> validate & fix (optional): whole-template validators, AI fix limited to the new ids
  -> status built, generation_notes
```

### 7.2 Prompt layout

The system prompt stays static (`SECTION_SYSTEM_PROMPT` plus the scripting API), so it is
cached. The user prompt holds the blocks in a fixed order: frame, outline, other regions,
plot, rules, chapters, quests, scenes, NPCs, items, gateway scenes, target region, region
idea / blueprint section, requirements, retry errors. Volatile parts come last, so the retry
re-uses the cached prefix.

Size and feature requirements have their own builders in
`engine/world/section_requirements.py` instead of sharing `world_prompt_builder.py`'s: those
are worded for a whole adventure ("typically between 3 and 10 scenes"), a region needs
region-sized defaults (6 to 10 scenes, 0 to 2 side quests, 0 or 1 chapter). New ids get the
region's prefix (`section_prompt.id_prefix`: `GLOOM_PEAKS` -> `GP_`, `PEAKS` -> `PEA_`).

### 7.3 Media

Today a region gets no images. The media phase calls the same image and voice steps that run
after a new adventure is generated, limited to the region's new scenes and entities, in the
adventure's image style. An image error does not undo the region; it becomes a generation
note and the editor's visual tools can retry it.

### 7.4 Additive only

The builder never changes existing rows. If the author wants an existing NPC to point
towards the new region, that is a normal editor edit or an AI fix afterwards. (A later phase
may let the blueprint carry such edits as a reviewed change set, section 11.)

## 8. API

### 8.1 Generate

`POST /{template_id}/editor/sections/{section_id}/generate`, body extended (old body with
only `brief` stays valid; missing fields take the defaults):

```json
{
  "brief": "A frozen dwarven ruin ... [Scene: GP_GATEHOUSE] ...",
  "mode": "advanced",
  "context": {
    "regions": "full",
    "outline": "full",
    "sequences": "full",
    "walkthroughs": true,
    "quests": "full",
    "plot": "full",
    "rules": "full",
    "npcs": "compact",
    "scenes": "compact",
    "items": "compact"
  },
  "options": {
    "generation_strictness": "creative",
    "min_scenes": 6, "max_scenes": 10,
    "min_items": null, "max_items": null,
    "quest_generation_enabled": true, "min_quests": null, "max_quests": null,
    "min_sequences": 0, "max_sequences": 1,
    "container_generation_enabled": true,
    "scripts_generation_enabled": true,
    "text_log_generation_enabled": true,
    "award_generation_enabled": true,
    "generate_scene_images": true,
    "generate_npc_images": true,
    "generate_item_images": false,
    "automatic_npc_voice_assignment": true,
    "auto_validate_and_fix": true
  }
}
```

`context` values: `"off" | "compact" | "full"`. Request models live in a new
`editing/section_builder_models.py`; `section_generation.py` only gains the call.

### 8.2 Preview

`POST /{template_id}/editor/sections/{section_id}/generate/preview`, same body. Returns,
without an LLM call:

```json
{
  "blocks": [
    {"id": "scenes", "tokens": 2140, "items": 84, "empty": false, "always": false,
     "included": true, "detail": "compact"},
    {"id": "gateway", "tokens": 610, "items": 8, "empty": false, "always": true,
     "included": true, "detail": "full"}
  ],
  "total_tokens": 11830,
  "blueprint": {"issues": [{"line": 4, "message": "...", "severity": "warning"}], "kinds": {"scene": 4, "npc": 2}},
  "prompt": "..."
}
```

Blocks in prompt order: `system`, `frame`, the nine options, `gateway`, `region`,
`requirements`. An option that is off is still measured at its default detail
(`included: false`), so the page can show what turning it on would cost; `total_tokens`
counts only included blocks, the system prompt among them. `prompt` (the full user prompt) only when `?include_prompt=true`, for the advanced
**Preview prompt** button. The page calls preview debounced on every context or blueprint
change. `blueprint` is null for a plain-text idea; with tags it is the region-mode report,
so the existing `blueprint_routes.py` stays for new adventures only. The body may carry
`gateways` (unsaved gateway picks per linked region), which only the preview uses.

### 8.3 Stored settings

The last request is stored in the region as `generation_settings` (author field, like
`brief`). `normalize_sections` keeps it, the session filters (`player_sections`,
`session_manifest`) drop it, the `.adv` export keeps it so a shared template can be rebuilt
the same way.

## 9. Backend modules

| Module | Content |
| --- | --- |
| `engine/world/section_context.py` (new) | Block builders keyed by option id (dispatch dict), each `(adventure, rows, detail) -> str`; token estimate |
| `engine/world/section_ledger.py` | Keeps the full ledger for validation; its `text` rendering moves to `section_context` |
| `engine/world/section_prompt.py` | Assembles frame + chosen blocks + requirements + blueprint section |
| `engine/world/section_requirements.py` (new) | Option normalization and the REGION REQUIREMENTS block |
| `engine/world/section_context_world.py` (new) | Scene, character and item blocks |
| `engine/world/section_gateways.py` (new) | Gateway choice (5.2a) and the GATEWAY SCENES block |
| `engine/world/section_id_renames.py` (new) | Collision renames (5.5) |
| `engine/world/section_validation.py` | `prepare_section` renames colliding ids (5.5) |
| `engine/blueprint/region_mode.py` (new) | Region mode: dropped global blocks, ledger-aware reference, redefinition, scene-region and exit checks, prompt notes |
| `engine/blueprint/merge.py` | `apply_blueprint(..., known_scene_ids)`: exits may join scenes outside the manifest |
| `engine/world/section_blueprint.py` (new) | Region blueprint from the brief and the ledger, write-back, preview report |
| `engine/world/section_media.py` (new) | Image and voice phase for the new ids |
| `api/routes/adventures/editing/section_builder_models.py` (new) | Request / preview models |
| `api/routes/adventures/editing/section_generation.py` | Extended generate body, preview endpoint, progress events |

## 10. Frontend modules

| Module | Content |
| --- | --- |
| `components/editor/pages/RegionBuilderPage.vue` | Composes the cards; no logic |
| `composables/regionBuilder/regionBuilderForm.ts` | Form state, defaults, stored settings, simple reset, size presets, payload, token labels (pure; `frontend/tests/regionBuilderForm.test.mjs`) |
| `composables/regionBuilder/useRegionBuilder.ts` | Region and stored settings, debounced preview, saving name and description, starting the job |
| `composables/regionBuilder/regionBuilderContext.ts` | provide / inject of the page state |
| `components/editor/region-builder/` | `RegionInfoCard`, `RegionIdeaCard`, `ContextOptionsCard` + `ContextOptionRow`, `RegionSizeCard`, `InheritedSettingsCard`, `RegionBuildBar`, `PromptPreviewModal` |
| reused from `components/create-adventure/` | `LimitRow` (now takes the form as a prop) |
| `RegionsPage.vue`, `regions/RegionGenerateControls.vue` | *Build region...* / *Retry...* open the builder |

The cards of the Generate adventure page read that page's form through injection, so only
`LimitRow` is shared; `StorySection` and `MediaSection` become shareable when phases C and D
need them. Workbench UI rules apply (`.claude/rules/frontend-ui.md`); `region-builder/`,
`regions/` and `composables/regionBuilder/` are in the UI check
(`frontend/scripts/check_workbench_ui.mjs`).

## 11. Open points

1. **Undo a region.** A built region can only be removed by hand today. A "Discard region"
   action (delete rows with its `section_id`, remove appended quests, awards, chapters and
   scripts, back to `stub`) would make experimenting cheap. Proposed as phase D.
2. **Blueprint edits of existing content** (7.4): out of scope; could later produce a change
   set the author reviews.
3. **Token estimate accuracy**: characters / 4 is rough for non-English text. Good enough
   for a relative hint; a tokenizer per provider is not worth it.
4. **Context relevance**: a later step could pick only the NPCs and items related to the
   linked regions instead of all-or-nothing per option.

## 12. Engine propagation checklist

| Item | Change |
| --- | --- |
| World generation schemas | `SectionManifest` unchanged |
| Prompts | `section_prompt.py`, shared requirement builders |
| Blueprint | region mode in `engine/blueprint/` |
| Manifest import/export | `generation_settings` round trip in sections |
| Editor AI fix | validate & fix limited to the new ids |
| Validators | none new |
| Docs and skills | `world_sections.md` 9.4 points here; `world-builder-blueprint-manual.md` gets a region-mode chapter; `taleweaver-adventure-concept-creator` learns region blueprints; rebuild bundled skills |
| Autocomplete | not affected |
| Tests | context blocks per option and detail; preview totals; collision renames; blueprint region mode (allowed kinds, references, existing-id error); request defaults for the old body; form logic in `frontend/tests/regionBuilderForm.test.mjs` |

## 13. Phases

* **A: context options (backend first). Done.** `section_context.py`, extended request, preview
  endpoint, id renames. The current Regions page sends all-on and keeps working.
* **B: Region Builder page. Done.** Simple / Advanced, cards, token badges, stored settings.
  Gateway scenes can be picked by hand per linked region (`gateway_scene_ids`, 5.2a).
* **C: blueprint region mode. Done.** Parser mode, live validation in the preview, `apply_blueprint`
  in the job.
* **D: media phase and discard region.**

Acceptance for A-C: a region built with all options off except gateways still merges without
id collisions; a region blueprint with three fixed scenes and one gateway exit produces
exactly those scenes and that exit; the token total shown before the job is within 20 % of
the prompt tokens logged by `generate_section`.
