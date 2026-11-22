# World Sections, Travel Time and Fast Travel (Concept)

Status (2026-11-21): **phases 1-4 implemented.** Planning regions is an editor action
instead of a toggle in the creation wizard (9.3).

| Phase 4 piece | Where |
| --- | --- |
| Player world map | `frontend/src/components/game/PlayerRegionMap.vue` (map dialog's travel strip) |
| Triggers `on_enter_section` / `on_leave_section` | `api/routes/adventures/section_triggers.py`; fired after an exit, each fast travel step, GM transitions and the respawn (not for script teleports or `/debug goto`) |
| World map tiles (`AdventureTemplate.world_map_layout` = `{cols, rows, tiles: [{col, row, url}]}`, migrations `e8a0c2d4f6b7`, `f1b3d5e7a9c2` converts the old single image into a 1 x 1 layout) | `engine/world/world_map_layout.py` (normalize, place/remove tile, rescale regions, per-tile prompt); `editing/section_map_routes.py`: `GET .../map-image/prompt?col&row` (default prompt of that tile, style, tone), `POST .../map-image {col, row, prompt, use_style, use_tone}`, `POST .../map-image/upload` (form `col`, `row`, `file`), `DELETE .../map-image?col&row`. A new tile must touch the map: one column right or one row below, at most 6 x 6. Growing or shrinking the grid rescales the region positions so they stay over the same spot. Map API field `world_map_layout`; export, import and cloning keep every tile. Editor: **Map images** dialog (tile grid, draw, upload, download, remove); both world maps (`components/worldmap/WorldMapViewport.vue`) zoom with the wheel or buttons and pan by dragging the background, markers keep their screen size |
| Map views | Editor Map page and players' map dialog open on the world map; a region opens its scene graph (`utils/regionMapView.ts`, `regionGraph.regionSceneIds`), scenes without a region have an own entry; no view of all scenes at once |
| Connections and travel times on the world map | `RegionMapCard.vue`: **Connect regions** creates a gateway exit between two built regions (scene of each, name, two-way, travel time) or a planned route with a planned region; a route's chip opens its travel time (the gateway exits' `travel_minutes`, or the planned route's), with an estimate from the map distance (hours per 10 % of the map) |
| Quest region hint (quest `section_id`, blueprint `region:`) | `agent_objectives.py` ("continues in ..."), region generation fills it, quest dialog |
| Several travel points per section | already possible: any number of scenes can be fast travel points (decision 7) |
| Road events | recipe in the blueprint manual (*Long journeys and fast travel*) |

| Phase 3 piece | Where |
| --- | --- |
| Outline (`AdventureTemplate.world_outline`, migration `d6f8b0c2e4a5`) | `engine/world/section_outline.py` |
| Ledger | `engine/world/section_ledger.py` |
| Schemas, prompts, generator, validation | `engine/world/section_schemas.py`, `section_prompt.py`, `section_generator.py`, `section_validation.py` |
| Merge into the template | `engine/manifest_apply/section_merge.py` |
| Editor endpoints (generate in background, plan) | `api/routes/adventures/editing/section_generation.py` |
| Session expansion | `api/routes/adventures/session_expansion.py`, `expansion_routes.py`, `frontend/src/composables/useRegionExpansion.ts` |
| Editor UI | `components/editor/regions/RegionGenerateControls.vue`, `RegionPlanModal.vue`, `RegionOutlineCard.vue` |
| Tests | `tests/test_world_section_generation.py` |

| Phase 1 piece | Where |
| --- | --- |
| Section model, normalization, session filter, region line | `engine/world/sections.py` |
| Columns `AdventureTemplate.world_sections`, `WorldScene.section_id` | migration `b8d2f4a6c9e1` |
| Generation schema | `engine/world/world_section_schema.py`, `world_schemas.py` |
| Manifest apply / export / `.adz` import / cloner | `manifest_apply/adventure_meta.py`, `scenes.py`, `adventure_exporter.py`, `adventure_importer.py`, `adventure_cloner.py` |
| Blueprint `[Section]` / `[Region]`, scene `section` | `engine/blueprint/section_converters.py`, `field_specs.py` |
| Validators | `core/world_validation/sections.py` |
| Map API (`sections`, `section_links`, node `section_id`) | `engine/interaction/map_sections.py`, `api/routes/map_api.py` |
| Editor endpoints, change-set ops `set_sections` / `assign_section` | `api/routes/adventures/editing/section_crud.py` |
| Editor UI: Regions page, Map region filter, scene region select, list filters | `components/editor/regions/`, `pages/RegionsPage.vue`, `pages/MapPage.vue`, `SceneSectionSelect.vue`, `components/editor/filters/` |
| Tests | `tests/test_world_sections.py` |

| Phase | Content | Depends on |
| --- | --- | --- |
| 1 | Sections as structure: data model, manifest `1.5.0`, editor maps | – |
| 2 | Travel time on exits, fast travel points, player world map | 1 (world map only) |
| 3 | Campaign outline, world ledger, per-section generation in the editor | 1 |
| 4 | Optional extras: section hooks, world map image, travel events | 2, 3 |

Phases 2 and 3 are independent of each other and can be built in either order.

## 1. Goals

* Adventures can grow to 50–100+ scenes without the generator running out of context and
  without the scene graph becoming unreadable.
* Distance matters: crossing the country costs in-game time, a door does not.
* Players can return to places they know without clicking through every scene.
* Existing adventures keep working unchanged, with no data migration.

Non-goals:

* Nested sections (a section inside a section). One level only.
* Mounts, vehicles or travel modes as mechanics. A route has a duration and a free-text label.
* Generating sections at play time. Dynamic zones (`dynamic_zone`,
  `engine/world/dynamic_cluster_*.py`) stay the tool for runtime-generated areas.

## 2. Terms

| Term | Meaning |
| --- | --- |
| Section | A spatial group of scenes (a town, a mine, a mountain range). Player-facing label: **Region**. |
| Stub | A planned section without scenes. Visible to authors only. |
| Fast travel point | A scene the author marked as a travel destination. Usable once it is unlocked in the session. |
| Gateway exit | A normal exit whose two scenes belong to different sections. |
| World map | Derived view: sections as nodes, gateway exits as links. |
| Section map | The existing scene graph, filtered to one section. |
| Sequence | Unchanged: the narrative chapter. A sequence may span several sections. |

Sections are purely spatial. They do not own quests, sequences or scripts, and they do not
gate anything by themselves. Gating stays on exits.

Naming: the backend calls them sections (`world_sections`). The frontend already has
`components/editor/WorldMapSection.vue` (a UI panel, unrelated), so new components use the
`Region` prefix (`RegionMap.vue`, `RegionNode.vue`).

## 3. Design decisions

1. **Travel is an exit, not a new edge type.** `WorldExit` already carries locks, unlock
   guards, hooks and `companions_allowed`, and every traversal runs
   `scene_entry.enter_scene`. A separate route table would have to copy all of it. A route
   between sections is a gateway exit with `travel_minutes`.
2. **The world map is derived.** Nothing stores "section A connects to section B" for built
   sections; it follows from the gateway exits. Only stubs store planned links, because they
   have no scenes yet.
3. **No new session state for discovery.** A section is discovered when one of its scenes
   was visited (`WorldMap.nodes`). Templates stay immutable; there is no `is_unlocked`
   column.
4. **`section_id` is nullable.** `NULL` means "this adventure has no sections" and
   everything behaves as today. No `SECTION_MAIN` backfill, no world map in the UI.
5. **Stubs never reach players.** They are not copied into sessions and not returned by the
   session map API.
6. **Fast travel is automated walking.** It walks the known route hop by hop with all hooks
   and stops when something happens. It is not a teleport.
7. **Fast travel points are scenes, not sections.** The author marks single scenes; the
   player can travel to a point once it is unlocked. This works in adventures without
   sections too, so fast travel does not depend on phase 1 data.
8. **Section generation is additive.** It adds scenes, entities, quests and scripts. It
   never rewrites existing content; that stays with the editor and AI fix. This is also
   what makes it possible to add a new section to a running session (9.7).

## 4. Data model

One Alembic migration per phase.

### 4.1 Section list (phase 1)

Implemented as a JSON list in `AdventureTemplate.world_sections`, like the audio library,
instead of a `WorldSection` table: a section never changes during play, and every session
already freezes all template columns in its adventure snapshot
(`entity_states["__manifest_snapshot__"]`), which travels with checkpoints, session copies
and session exports. A table would have needed session rows and copy code in every one of
those paths. The snapshot keeps only built sections without the author fields
(`sections.player_sections`). Fields of one entry (normalized by
`sections.normalize_sections`):

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string (50) | unique within the adventure, e.g. `HARBOR_TOWN` |
| `label` | string (100) | |
| `description` | String(2000) | one paragraph; also shown to the GM as regional context |
| `map_x`, `map_y` | Float | 0–100, position on the world map |
| `order_index` | Integer | list order in the editor |
| `status` | String(20) | `stub`, `generating`, `built` |
| `brief` | Text, nullable | author directions for generation |
| `summary` | Text, nullable | compressed description of the built content, for later prompts |
| `planned_links` | JSON, nullable | stubs only: `[{"to_section_id", "travel_minutes", "note", "gateway_scene_ids"}]`; `gateway_scene_ids` are up to 8 scenes of the target region the Region Builder connects to first |

### 4.2 Changed tables

| Table | Column | Phase | Notes |
| --- | --- | --- | --- |
| `WorldScene` | `section_id` String(50), nullable | 1 | no backfill |
| `WorldScene` | `is_fast_travel_point` Boolean, default false | 2 | |
| `WorldScene` | `fast_travel_unlock` String(20), default `visit` | 2 | `visit`: unlocked on first entry; `script`: only by a script |
| `WorldExit` | `travel_minutes` Integer, nullable | 2 | `NULL`/0 = no travel time |
| `WorldExit` | `travel_label` String(100), nullable | 2 | flavour, e.g. "two days by ship" |
| `AdventureTemplate` | `fast_travel_enabled` Boolean, default true | 2 | |
| `AdventureTemplate` | `world_outline` JSON, nullable | 3 | see 9.1 |

Sequences get an optional field `fast_travel_allowed` (default true) in their JSON, next to
`companions_allowed` and `respawn_allowed`.

### 4.3 Session copies

Sections reach sessions through the adventure snapshot (4.1). `WorldScene.section_id` is
part of `scene_fields.SCENE_CONTENT_FIELDS`, which session start, session copies, session
import and template reset share. For the phase 2 exit fields check every file that mentions
`companions_allowed` (14 files); `session_materializer._EXIT_COPY_FIELDS` and
`session_cloning._EXIT_FIELDS` are explicit lists: a field missing there is silently lost in
every new session.

## 5. Manifest format `1.5.0`

Update `docs/specs/adventure_format.md`.

```json
{
  "adventure": {
    "fast_travel_enabled": true,
    "world_outline": { "...": "see 9.1" }
  },
  "sections": [
    {
      "id": "HARBOR_TOWN",
      "label": "Harbor Town",
      "description": "A fishing port under a broken lighthouse.",
      "map_x": 20, "map_y": 65,
      "status": "built"
    },
    {
      "id": "GLOOM_PEAKS",
      "label": "Gloom Peaks",
      "description": "Abandoned silver mines above the tree line.",
      "map_x": 70, "map_y": 25,
      "status": "stub",
      "brief": "Dwarven ruins, cold, few NPCs.",
      "planned_links": [{ "to_section_id": "HARBOR_TOWN", "travel_minutes": 480 }]
    }
  ],
  "scenes": [
    {
      "id": "HARBOR_SQUARE", "section_id": "HARBOR_TOWN",
      "is_fast_travel_point": true, "fast_travel_unlock": "visit"
    }
  ],
  "exits": [
    {
      "from_scene_id": "HARBOR_GATE", "to_scene_id": "PEAK_TRAIL",
      "travel_minutes": 480, "travel_label": "a day's march uphill"
    }
  ]
}
```

* Import of `<= 1.4.0`: no `sections`, all `section_id` stay `NULL`.
* Export always writes stubs, so an author can continue a campaign from an `.adz`.
* A round-trip test (export → import → export) must keep every new field.

## 6. Runtime

### 6.1 Section awareness

* `engine/world/sections.py`: normalization, `player_sections`, `region_line`.
* The CURRENT STATE location block of both passes gets one line when the current scene has
  a built section: `Region: <label>: <description>`. It belongs to the volatile user message,
  not the static system prompt.
* `engine/interaction/map_sections.attach_sections` tags the map nodes with their section
  at response time (unexplored placeholders get none) and derives the discovered sections
  (`discovery: visited | revealed`) and the links between them from the known edges.

### 6.1a How a route's travel time is set

Nothing is calculated: a route between two built regions takes the `travel_minutes` of its
gateway exits (the shortest one is shown on the world map), a planned route stores its own
`travel_minutes` until its region is generated. The world map's route dialog edits them and can
suggest a value from the straight-line map distance and a pace the author enters.

### 6.2 Travel time on exits (phase 2)

Implemented as `rules/travel_time.advance_travel_time(state, minutes) -> int` (returns the
minutes actually added) and `travel_flow.apply_exit_travel(manager, world_exit)`:

* Returns 0 while the clock is paused. Like the narration tick it does not depend on
  `clock_enabled` (that switch only shows or hides the clock).
* Not capped by `max_time_per_turn`; that cap is for GM-requested extra time only.
* A message that applied travel time does not also get the narration tick
  (`clock_tick_pending` is cleared). Travel replaces the tick.

Call sites, right after `enter_scene` and before `on_enter_scene`:

* `turn_interactions._handle_traverse_exit` (`/traverse_exit`)
* `gameplay.py` exit endpoint (around line 945)
* `turn_state_applier` when the GM transition used an exit with travel time

Script teleports and `/debug goto` add no travel time.

The clock moves at the traversal, so the arrival narration already sees the new time; the
chat line "The journey (...) takes ..." and a hint in the arrival prompt make the narration
mention the journey. Due `on_time_reached` scripts and timers fire after the narration,
where the tick's events would have fired (`tick_after_narration`). The REST traverse
endpoint has no turn: its time events fire with the next message.

The exit tile and the map show the duration ("8 h") before the player commits.

### 6.3 Fast travel (phase 2)

**Fast travel points.** The author marks scenes with `is_fast_travel_point` (a town
square, an inn, a waystone). A point becomes a destination once it is unlocked in the
session:

* `fast_travel_unlock: "visit"` (default): on first entry. `scene_entry.enter_scene` calls
  a new `note_fast_travel_point`, next to `note_respawn_point`, so every scene-change path
  is covered. The chat shows "Fast travel point unlocked: <label>."
* `fast_travel_unlock: "script"`: only a script unlocks it, e.g. when the player activates
  the waystone or pays the ferryman.
* Scripts can unlock and lock any point at any time (see script control below).

Unlocked points are stored in `entity_states["__travel__"]["unlocked"]` (list of scene
ids), so they are part of every checkpoint. Logic lives in `engine/rules/fast_travel.py`.

**What the player can reach.** Every unlocked point to which a route of open exits exists.
The route runs over visited scenes only (the destination itself may be unvisited when a
script unlocked it). Same knowledge rule as the Play-Agent's `/travel`: no hidden exits.
A point without a known open route is listed as unavailable with the reason. The player can
start from any scene, not only from another point.

**Route.** Move the path search out of `agent_known_map.py` into
`engine/interaction/route_finder.py` and make it weighted (Dijkstra, weight =
`travel_minutes`, tie-break by hop count). `MapExit` gains `travel_minutes` and
`companions_allowed`. The Play-Agent uses the same module.

**Command.** `/fast_travel <scene id or label>`, sent by the map UI and typeable.
New module `api/routes/adventures/fast_travel.py`.

**Blocked when** (a system message names the reason):

* `fast_travel_enabled` is off, or the active sequence has `fast_travel_allowed: false`
* a combat or a choice dialog is open
* scripts locked it (see below)
* no open route is known

**Execution.** One player message, several hops:

1. For each exit on the route, run the same steps as `/traverse_exit` (`fast_travel._hop`
   reuses its trigger and map helpers): `on_leave_scene`, `on_exit_used`, set
   `current_scene_id`, `enter_scene`, travel time, `on_enter_scene`, due time events. No
   narration for intermediate hops; the arrival narration is shared with `/traverse_exit`
   (`arrival_narration_flow.narrate_arrival`).
2. After each hop, stop the trip when any of these is true: a choice dialog opened, a
   combat started, a script moved the player, the next exit is now locked, the protagonist
   went down, the session ended, or a hook or time event produced a chat message.
3. One arrival narration (`arrival_narration = True`) at the place where the trip ended,
   with a travel summary: places passed, total minutes, and the interruption reason if any.

Consequences, stated so nobody has to guess:

* One in-game turn boundary (`on_turn_end` → status ticks → `on_turn_start`) and one
  `SCENE_CHANGE` checkpoint per fast travel, not one per hop.
* Companions follow per hop through `enter_scene`. When the cheapest route uses an exit
  with `companions_allowed: false` and a companion is following, the route finder prefers
  a route without one; if none exists, the confirmation names the companion that stays
  behind.
* Every passed scene is registered on the map and can set the respawn point, as when
  walking.

**Preview endpoint.** `GET /{game_id}/travel/options` returns, per unlocked point:
`scene_id`, `label`, `section_id`, `minutes`, `hops`, `available`, `reason`. It
resolves the session with `resolve_session_state(db, game_id, user_id=...)` and is added
to the parametrized list in `tests/test_session_ownership.py`.

**Script control.** Three calls, recorded as ordered `ScriptChangeset.travel_ops` and
replayed by every changeset applier with `apply_travel_ops` into
`entity_states["__travel__"]`:

* `tw.game.unlock_fast_travel(scene_id)`: unlocks a point (the scene must be marked as one)
* `tw.game.lock_fast_travel(scene_id)`: removes it again (a collapsed bridge, a burnt inn)
* `tw.game.set_fast_travel(enabled, reason=None)`: switches fast travel off or on as a whole

Needs `docs/scripting_engine.md`, `world_scripting_prompt.py` and
`frontend/src/utils/twScriptApiDefinitions.ts`.

## 7. Player UI

* (Phase 2.) `MapModal.vue` gets two tabs when the adventure has sections: **Region** (scene graph of
  the current section, as today) and **World**.
* World tab (`RegionMap.vue`): discovered sections at `map_x`/`map_y`, links from known
  gateway exits with their duration, locked links marked. A section behind an
  `is_revealed` gateway exit shows as known but unvisited. The current section is
  highlighted.
* Unlocked fast travel points are listed under their region on the World tab and carry a
  marker on the scene node in the Region tab. Clicking one opens a confirmation ("Travel
  to Harbor Square, about 8 h") and sends `/fast_travel`. Unavailable points are greyed
  out with their reason.
* In an adventure without sections there is no World tab; the points are markers on the
  scene graph plus a "Travel" list.
* The region tab can switch to any discovered section for viewing.
* Map API (`backend/api/routes/map_api.py`, `GET /adventures/{template_id}/map`): the
  response gains `sections` and `section_links`. With a `session_id` it returns discovered
  sections only and never stubs.

## 8. Editor

* `MapTab.vue` gets the same two levels. The scene graph is filtered by a section selector,
  which is what fixes the spider web. Scenes without a section appear under "Unassigned".
* World level: drag sections to set `map_x`/`map_y`, create stubs, draw planned links
  between stubs and built sections, edit label, description and brief.
* Scene form: section select, "Fast travel point" checkbox and its unlock mode. Exit form:
  travel minutes and label, offered for all exits and highlighted for gateway exits.
* Bulk action "move scenes to section" for restructuring existing adventures.
* List filters (`components/editor/filters/`): the Scenes list filters by region, the
  Characters and Items lists by region and scene (the scene select narrows to the chosen
  region; "No region" keeps scenes without a section, entries without a known scene show only
  under "All regions" or their own scene option). The choice is kept per adventure and list.
* CRUD in a new `editing/section_crud.py`, not in `world_crud.py`.
* The change-set tool (`scripts/edit_adventure.py`, skill `taleweaver-adventure-editor`)
  learns sections and the new exit fields.

## 9. Generation (phase 3)

### 9.1 Campaign outline

Stored in `AdventureTemplate.world_outline`. Text only, cheap to generate, and the reason
section 1 can plant things that section 4 needs.

```json
{
  "premise": "…",
  "arc": ["act 1 …", "act 2 …", "act 3 …"],
  "sections": [
    {
      "id": "GLOOM_PEAKS",
      "purpose": "Reveal who sabotaged the lighthouse.",
      "gating": "Needs the harbormaster's pass from HARBOR_TOWN.",
      "plants": ["rumour about the drowned bell"],
      "resolves": ["the missing surveyor"]
    }
  ],
  "threads": [
    { "id": "MISSING_SURVEYOR", "opened_in": "HARBOR_TOWN", "resolved_in": "GLOOM_PEAKS", "status": "open" }
  ]
}
```

The author can edit the outline in the editor. Thread `status` is updated after each
section generation.

### 9.2 World ledger

`engine/world/section_ledger.py` builds it from the database on every generation; it is
never stored and never written by an LLM. Contents:

* all scene ids and labels, grouped by section
* all entity ids with name, type and section
* quest, award and sequence ids with titles
* items that unlock something, with where they are found and what they open
* the `summary` of every built section

It is the validation reference in 9.5 and is always built in full. The prompt context is
built separately, one block per context option the author chose (`engine/world/
section_context.py`, `section_context_world.py`; see [region_builder.md](region_builder.md),
section 5), so leaving a list out of the prompt never weakens the checks.

### 9.3 Planning regions

Implemented as an editor action instead of a toggle in the creation wizard, so it also works
for adventures that already exist: **Regions → Plan regions** (`POST
/{template_id}/editor/sections/plan {count, direction}`, `section_generator.plan_sections`,
schema `CampaignPlan`). One call proposes the outline and `count` planned regions with
description, map position, brief and planned links to the existing regions. Nothing is
stored: the proposal goes into the page's draft, and the author reviews and saves it. A new
adventure that should become a campaign is generated as usual (it becomes the first region
when its scenes are assigned to one), then planned here.

### 9.4 Section generation in the editor

> The UI is the Region Builder ([region_builder.md](region_builder.md)): **Build region...**
> on a planned region opens a page with Simple / Advanced options and the context options;
> it starts the job described below and returns to the Regions page. Blueprint input
> follows in phase C.

The author selects a planned region, saves and clicks **Build region...**, which opens the
Region Builder; its **Build region** starts the job (`POST /{template_id}/editor/sections/{section_id}/generate`
with brief, mode, context and options, stored as the region's `generation_settings`). The job runs
as a background task with its own database session (`section_generation.run_generation`,
which calls `apply_global_settings`). The section is `generating` meanwhile and the Regions
page polls the editor data; a failed job puts it back to `stub` with `generation_error`.
With the builder's media options the region's images are drawn during the merge and its new
characters get voices; *Validate & fix afterwards* fixes the findings the region introduced, and
**Discard region...** takes a region the builder built out again ([region_builder.md](region_builder.md), 7.3).

Prompt (`section_prompt.region_blocks`): adventure frame, the chosen context blocks
(outline, other regions, plot, world rules, chapters with walkthroughs, quests, scenes,
characters, items), the gateway scenes (always; `section_gateways.py`), the region with its
id prefix and brief, and the REGION REQUIREMENTS (`section_requirements.py`: counts, feature
switches, strictness). The request body may carry `context` and `options`
([region_builder.md](region_builder.md), 8.1); a body with only `brief` uses the defaults
(all context on). `POST .../sections/{section_id}/generate/preview` returns the blocks with
token estimates without an LLM call.

Output schema `SectionManifest` (`engine/world/section_schemas.py`, `extra="forbid"`):
scenes, exits, NPCs, objects, quests, awards, sequences, scripts, `summary`, and the
outline thread updates. The prompt asks for one or two fast travel points per section, one
of them at the arrival scene. The init script is off limits: section setup goes into
`on_enter_scene` scripts or scene `helpers_script`, because `on_init` has already run in
existing sessions (9.7). Exits may connect new scenes to each other and to gateway scenes
of built neighbours. Everything else must be new.

### 9.5 Validation and apply

Deterministic, before anything is written:

* no id collides with the ledger
* every referenced id exists in the output or the ledger
* every new scene is reachable from a gateway exit
* at least one gateway exit per planned link to a built neighbour
* items required by locks are obtainable in this section or already exist
* scripts pass `script_validator`

Before the checks, `prepare_section` fixes what needs no retry: ids that already exist in the
adventure are renamed to the next free `<ID>_2` with all references in the region
(`section_id_renames.py`), every scene gets the region's `section_id`, new chapters are numbered after the existing ones, `on_init`
scripts are dropped. On any error the job retries once with the errors in the prompt, then
gives up: nothing is applied and the section returns to `stub`. On success the region is
merged, the section becomes `built` with its `summary`, `planned_links` is cleared and the
outline threads are updated. Then the whole-template validators run once more; the findings
the region introduced and the fix-ups are stored in the section's `generation_notes` and
shown on the Regions page until the author dismisses them.

**Apply path: a merge into the template** (`engine/manifest_apply/section_merge.py`), not
the change-set applier as planned. The change-set request models cover only part of what the
generator writes for characters and items (combat profiles, companions, conversations,
switch states, ...); the manifest applier's `persist_scenes`, `persist_exits`,
`persist_npcs` and `persist_objects` handle all of it. `merge_section` runs them without
clearing the world, then appends quests, awards, chapters and scripts to the template and
its `original_manifest` (incl. the scene entries, from which sessions read scene helpers).

### 9.6 Blueprint

The blueprint tables are keyed in lowercase snake case with aliases, and durations already
have a converter (`converters.time_amount`: `90`, `2h 30m`, `1d`). The additions:

| Where | Key (aliases) | Target | Converter |
| --- | --- | --- | --- |
| `SCENE_KEYS` | `section` (`region`) | `section_id` | `_ref` |
| `SCENE_KEYS` | `fast_travel` (`waypoint`) | `is_fast_travel_point` | `boolean` |
| `SCENE_KEYS` | `fast_travel_unlock` | `fast_travel_unlock` | `visit` / `script` |
| `EXIT_KEYS` | `travel` (`travel_time`) | `travel_minutes` | `time_amount` |
| `EXIT_KEYS` | `travel_label` | `travel_label` | – |
| `SEQUENCE_KEYS` | `fast_travel` | `fast_travel_allowed` | `boolean` |
| `WORLD_KEYS` | `fast_travel` | `fast_travel_enabled` | `boolean` |
| new `SECTION_KEYS` | `description`, `position` (`x, y`), `status`, `brief`, `links` | section fields | – |

New kind `section` (alias `region`) in `parser.py` (kind table and name key `label`), in
the kind table at the end of `field_specs.py`, in `models.py` (`id_kinds`) and with a
default builder in `merge.py`.

```
[Section: HARBOR_TOWN] Harbor Town
Position: 20, 65

[Section: GLOOM_PEAKS] Gloom Peaks
Status: stub
Brief: Dwarven ruins, cold, few NPCs.
Links: HARBOR_TOWN 8h

[Scene: HARBOR_SQUARE] Harbor Square
Section: HARBOR_TOWN
Fast travel: yes

[Exit: HARBOR_GATE -> COAST_ROAD] the coast road
Travel: 2h 30m
Travel label: a windy walk along the cliffs
```

Examples in the docs must pass `analyze_blueprint`.

### 9.7 Adding a new section to running sessions

Finding: sessions own a full copy of the world (`session_materializer`: scenes, exits,
entities) plus a manifest snapshot in the session state (quests, sequences, scripts).
`adventure_updates.update_single_adventure` states it outright: existing sessions are not
updated, only re-linked to the new template. Without extra work, a player who started
before a section was built never sees it.

Solution: **session expansion**, module `api/routes/adventures/session_expansion.py` (it
reuses the session cloning helpers of the API layer), endpoints `GET` / `POST
/{game_id}/expansion` (`expansion_routes.py`).

* `pending_sections(db, state)`: `built` sections of the template that have no rows in
  the session.
* `expand_session(db, state, section_ids)` copies, for each section: its entry
  in the snapshot's `world_sections`, its scenes and entities (same cloning and asset copy as the materializer), all
  exits that touch one of its scenes (this includes the gateway exits on the old side),
  and the quests, awards, sequences and scripts whose ids the session snapshot does not
  know yet.
* It only adds. No existing row, no `entity_states` entry and no avatar field is touched.
  That is safe because section generation is additive (decision 8) and may not change the
  init script.
* Trigger: when a session is opened and `pending_sections` is not empty, the play view asks
  ("New region: Gloom Peaks", `useRegionExpansion.ts`). A declined region is remembered in
  the browser and not offered again. The owner check uses
  `resolve_session_state(..., user_id=...)`; both endpoints are in
  `tests/test_session_ownership.py`.
* Checkpoints written before the expansion do not contain the section. Loading one makes
  it pending again and the offer reappears; nothing breaks.
* It also works after an `.adz` update, because the update re-links the sessions to the
  new template.

Limits, to be stated in the docs:

* Manual edits to existing content (a changed NPC, a rewritten quest) still do not reach
  running sessions. Only whole new sections do.
* A campaign with stubs must not be winnable before its last section exists. The outline
  fixes the final goal from the start; when a session has finished every available
  sequence while the template still has stubs, the player gets a "to be continued" notice
  instead of an ending (`campaign_continuation.py`: while the template has planned
  regions or regions the session has not taken in yet, finishing the last known chapter
  shows the notice once, `entity_states["__to_be_continued__"]`, and the session stays
  active; a win guard and `tw.game.win()` still end it).

Effort: moderate. The cloning code exists; the new parts are the id-based merge of the
snapshot lists and the offer in the client. It belongs to phase 3, since without it
per-section generation only helps authors who have not published yet.

## 10. Play-Agent

* `agent_known_map.format_known_map` groups places by region and shows travel time on exit
  lines.
* The prompt lists the unlocked fast travel points with their duration, and `/fast_travel`
  is added to `AGENT_PLAYER_TURN_SYSTEM_PROMPT`. `/travel` stays for scene-level walking
  and uses the shared weighted route finder.
* `docs/play-agent.md` is updated.

## 11. Engine propagation checklist

| # | Area | Work |
| --- | --- | --- |
| 1 | World generation | `world_schemas.py` (`WorldSectionSchema`, `section_id`, `travel_minutes`, `travel_label`, `fast_travel_allowed`, manifest `sections`), `core/prompts.py`, `world_prompt_builder.py`, `world_scripting_prompt.py` (`tw.game.set_fast_travel`) |
| 2 | Blueprint | `field_specs.py`, `parser.py` (kind `Section`), `converters.py`, `prompt.py` |
| 3 | Import/export | `manifest_apply/` (new `sections.py`, `scenes.py` for exit fields), `adventure_exporter.py`, `manifest_export.py`, cloner, session import/export |
| 4 | Editor / AI fix | `world_builder_prompts.py`, `validators_prompts.py` (`FIX_PATCH_FIELD_RULES`), `ai_fix_*` allowlists, `editing/schemas.py`, `entity_update/scene_exit.py` |
| 5 | Validators | new `core/world_validation/sections.py`: unknown `section_id`, built section without scenes, built section without a fast travel point (warning), `fast_travel_unlock: script` without any script that unlocks the point (warning), section unreachable, gateway exit without travel time (warning), negative travel time |
| 6 | Docs and skills | `docs/world-builder-syntax.md`, `world-builder-blueprint-manual.md`, `scripting_engine.md`, `specs/adventure_format.md`, `play-agent.md`, `README.md`, `.claude/rules/architecture.md`, skills `taleweaver-adventure-concept-creator`, `taleweaver-adventure-editor`, `taleweaver-inspector`; then `scripts/bundle_skill.py` |
| 7 | Autocomplete | `twScriptApiDefinitions.ts` |
| 8 | Tests | see section 13 |

`scripts/inspect_state.py` gets a `--sections` view.

## 12. Known limits and open points

The three open points of the first draft are analysed and settled: running sessions (9.7),
the apply path (9.5) and the blueprint keys (9.6). What remains:

* **A script-unlocked point without a walked route is unavailable.** Fast travel walks
  known scenes. An author who wants "the ferryman takes you to an island you have never
  seen" uses a gateway exit with travel time, not a fast travel point.
* **Time-of-day effects** (NPC schedules, visibility at night) are not part of this
  concept. Travel time only becomes meaningful through `on_time_reached` scripts, timers
  and whatever the narration makes of the clock.
* **Quests across sections** work because quests are global, but the Play-Agent's
  objectives do not say in which region a quest continues. Consider a `section_id` hint on
  quests in phase 4.
* **Fast travel starts anywhere.** A stricter "only from point to point" mode would be one
  adventure setting on top; not planned.

## 13. Phases and acceptance

### Phase 1: structure

Scope: `world_sections`, `WorldScene.section_id`, manifest `1.5.0` (sections and
`section_id` only), session snapshot, editor section CRUD, Regions page with world map, Map
region filter, validators, map API fields, `Region:` line in CURRENT STATE. Done.

Accepted when:

* an adventure without sections behaves and exports exactly as before
* export → import → export keeps sections, stubs and `section_id`
* a session of an adventure with one stub contains no trace of the stub (rows, map API)
* the editor shows one section at a time and the world level with planned links

### Phase 2: travel and fast travel

Scope: exit travel fields, `apply_travel_time` at the three call sites, fast travel point
fields and unlocking, shared weighted route finder, traversal core extraction,
`/fast_travel`, options endpoint, script API, sequence field, player world map,
Play-Agent.

Accepted when:

* using an exit with 480 minutes advances the clock by 480, fires a timer due after 200
  minutes on arrival, and adds no narration tick
* clock off or paused: no time added, the trip still works
* entering a `visit` point unlocks it once and shows the notice; a `script` point stays
  locked until `tw.game.unlock_fast_travel`; `lock_fast_travel` removes it; a checkpoint
  restores the unlocked list
* an unmarked scene and a locked point are refused as destinations
* fast travel works in an adventure without sections
* fast travel over three hops runs every `on_enter_scene` once, produces one narration and
  one checkpoint
* a choice dialog opened by an intermediate scene stops the trip in that scene
* fast travel is refused during combat, with an open dialog, with the sequence field off,
  and after `tw.game.set_fast_travel(False)`
* another user's session id gets 404 from the options endpoint
* `tests/test_game_loop.py` and the Play-Agent travel tests still pass

### Phase 3: generation

Scope: outline, ledger, campaign toggle, `SectionManifest`, section generation job,
validation, apply through the change-set applier (new operations), session expansion,
blueprint tags.

Accepted when:

* a generated section with an id collision or a dangling reference is rejected and leaves
  the template untouched
* a successful generation yields a built section that is reachable from its neighbour and
  passes all world validators
* a session started before a section was built gets it through the expansion, with
  inventory, quest progress and `entity_states` unchanged; loading an older checkpoint
  makes the section pending again
* a session that finished all available sequences while stubs remain gets the "to be
  continued" notice and no ending
* the ledger for a 100-scene fixture stays under a fixed token budget
* blueprint examples in the docs pass `analyze_blueprint`

### Phase 4: extras

`on_enter_section` / `on_leave_section` triggers, a generated world map background image,
quest region hints, several travel points per section, random travel events as a documented
`on_exit_used` recipe.
