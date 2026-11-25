# TaleWeaver Adventure Format Specification

This document defines the structure, schema, and field definitions for `.adv` (JSON) and `.adz` (ZIP Bundle) adventure formats used in TaleWeaver.

---

## 1. File Formats

- **.adv**: A standalone UTF-8 JSON file containing the complete adventure manifest (`WorldManifesto`).
- **.adz**: A ZIP archive containing:
  - `adventure.adv`: The core manifest file (JSON).
  - `assets/`: A directory containing all localized image assets referenced by relative paths in the manifest (e.g., `assets/cover.png`, `assets/scene_1.webp`).

---

## 2. Manifest Structure (`adventure.adv`)

The manifest represents the complete blueprint of a generated or exported world.

```json
{
  "format": "TaleWeaver",
  "version": "1.5.0",
  "adventure": { ... },
  "protagonist": { ... },
  "sections": [ ... ],
  "scenes": [ ... ],
  "npcs": [ ... ],
  "objects": [ ... ],
  "exits": [ ... ],
  "quests": [ ... ],
  "awards": [ ... ],
  "scripts": [ ... ],
  "extensions": { ... }
}
```

`format` and `version` (the manifest **format** version, not the adventure's own version in
`adventure.version`) must be the first two keys: the adventure library reads them from the
first 512 bytes of each `adventure.adv` without downloading the whole file.

**Version policy** (`backend/core/adventure_format.py`):

| Manifest version | Status |
| --- | --- |
| `1.5.0` (current) | Current format. Adds world sections (regions: top-level `sections`, scene `section_id`), travel time on exits (`travel_minutes`, `travel_label`), fast travel (scene `is_fast_travel_point` / `fast_travel_unlock`, adventure `fast_travel_enabled`, sequence `fast_travel_allowed`) and cut-scenes (adventure `cutscenes`, sequence `start_cutscene_id`). |
| `1.4.0` up to below `1.5.0` | Supported: importable and playable without restrictions (no world sections). Adds dynamic scenes (`dynamic_generation` / `dynamic_zone`), item visuals, companions (NPC `companion`, exit and sequence `companions_allowed`), and respawning (`game_over_rules.on_zero_hp`, scene `is_respawn_point`, sequence `respawn_allowed`). |
| `1.3.1` up to below `1.4.0` | Supported: importable and playable without restrictions (predates optional `dynamic_generation` / `dynamic_zone` fields, companions, and respawning). |
| `1.3` up to below `1.3.1` | **Deprecated**: still importable and playable, shown with a *Deprecated* badge on imported adventures and in the adventure library dialog (listed by default after all current adventures; unticking *Show deprecated* hides them for the rest of the browser session). `CONSTRUCTABLE` recipes from these versions lack `result_item_ids` / `kept_ingredients`, so crafting may not work. |
| `1.0` up to below `1.3` | **Legacy**: importable, but must be migrated before it can be played (*Migrate adventure*). Only the version decides: an adventure without sequences stays playable. |
| below `1.0` | Rejected on import. |

---

### 2.1 Adventure Metadata (`adventure`)

General configuration, narrative constraints, and gameplay settings.

| Field | Type | Description |
| :--- | :--- | :--- |
| `title` | `string` | The title of the adventure. |
| `teaser` | `string` | A short, atmospheric hook/summary (max 300 chars). |
| `context` | `string` | Foundational world-building lore and background for the AI Game Master. |
| `plot` | `string` | Compact plot overview and story milestones for AI narrative consistency. |
| `rules` | `string` | Special world rules (e.g. "Magic requires physical sacrifice", "NPCs cannot be harmed"). |
| `completed_condition` | `string` | Custom condition defining game victory (defaults to all main quests in RPG mode). |
| `gameover_condition` | `string` | Custom condition defining game over (defaults to player HP <= 0 in RPG mode). |
| `original_prompt` | `string` | The original prompt used during generation (for documentation purposes). |
| `image_url` | `string` | Relative path (`assets/...`) or canonical URL (`/data/...`) to the cover visual. |
| `rule_enforcement_mode` | `string` | `"rpg"` (strict mechanics & dice checks), `"story"` (streamlined mechanics), or `"chat"` (pure narrative). |
| `time_per_turn` | `number` | In-game minutes that pass after every narrated player message (the narration tick, default: 5). Scripts can override it per session with `tw.time.set_minutes_per_tick()`. |
| `max_time_per_turn` | `number \| null` | Optional cap for the narration tick plus the GM's extra time of one message. |
| `gm_time_control` | `boolean` | Whether the Game Master may change the in-game time (`extra_time_minutes`, time overrides). Default: `true`; missing in older files means `true`. Scripts can override it per session with `tw.time.allow_gm_time()`. |
| `pacing_minutes` | `number` | Frequency of world background heartbeats / scheduled events. |
| `clock_enabled` | `boolean` | Whether to track and display in-game time / calendar. |
| `ingame_timestamp` | `string` | Formatted starting in-game timestamp (e.g. `"Day 1, 08:00"`). |
| `selected_tone` | `string` | Narrative tone identifier or description (e.g. `"Dark Fantasy"`, `"Cyberpunk"`). |
| `audio_tracks` | `array` | Optional audio library: `[{"id", "name", "prompt", "url", "source", "reference_scene_id", "created_at"}]`. `id` is a slug (`A-Z a-z 0-9 _ -`, max 50, accepted on import); IDs set in the editor use upper-case letters, digits and underscores, max 30 (e.g. `CRYPT_THEME`). `url` is an `assets/` path in `.adz` bundles and a `/data/` URL into the adventure's own library folder in the database; anything else (other adventures' files, external URLs, `.adv` uploads without the file) is dropped, leaving a *planned* track that the editor can render from its `prompt`. `source`: `generated`, `uploaded` or `planned`. |
| `title_track_id` | `string` \| `null` | Optional title track: `id` of a `audio_tracks` entry, played while the adventure's library tile is hovered. Without it the tile stays silent. |
| `audio_enabled` | `boolean` | Default `true`. `false` switches scene audio off (script audio via `tw.audio` still plays). |
| `cutscenes` | `array` | Optional cut-scenes: `[{"id", "title", "image_style", "audio_track_id", "slides": [{"id", "passages", "image_url", "image_prompt"}]}]`. `passages` are 1-6 texts shown one after another over the slide's picture (a single `text` is read as the first passage). `id` is upper case (`A-Z 0-9 _`, max 40); at most 100 cut-scenes with 12 slides each. `image_style` overrides the adventure's image style for the slide images (catalog id or name, or a free description; empty = the adventure's style). `audio_track_id` names an `audio_tracks` entry. Slide `image_url` is an `assets/` path in `.adz` bundles and a `/data/` URL in the database; other URLs are dropped on import. A chapter shows one with `start_cutscene_id`, scripts with `tw.cutscene.play(id)`. See [Cut-scenes](cutscenes.md). *(since 1.5.0)* |
| `intro_cutscene_id` | `string` \| `null` | Optional `id` of a `cutscenes` entry shown right after a new session starts, before the first chapter's cut-scene. *(since 1.5.0)* |
| `win_cutscene_id` | `string` \| `null` | Optional `id` of a `cutscenes` entry shown when the adventure is won, before the victory card. |
| `game_over_cutscene_id` | `string` \| `null` | Optional `id` of a `cutscenes` entry shown on game over, before the game-over card. |
| `world_map_layout` | `object \| null` | Optional drawn world map shown behind the regions: `{cols, rows, tiles: [{col, row, url}]}`, a grid of up to 6 x 6 images in 16:9 (each `url` an `assets/` path in `.adz` bundles). Region `map_x` / `map_y` are percent of the whole map. *(since 1.5.0)* |
| `fast_travel_enabled` | `boolean` | Default `true`. `false` switches fast travel off for the whole adventure (see [Fast travel](#fast-travel)). *(since 1.5.0)* |
| `narrator_voice` | `object` \| `null` | Optional voice of the Game Master: how the narration is worded (diction, sentence rhythm, attitude), not how long it is. `{"id": "noir-detective", "name": "Hardboiled Noir Detective", "description": "...", "instruction": "Narrate like ...", "sample": "Rain hit the neon sign ..."}`. `instruction` is required (max. 1500 characters); `sample` is an optional style sample (max. 500). `id` is the catalog voice the author picked, or `"custom"` for a voice written in the editor. The full voice is stored, so an import works without the admin's voice catalog. Without it, the GM narrates in the neutral default voice. |
| `ui_theme` | `object` \| `string` | Optional in-game dialog skin: `{"skin": "chronicle", "accent": "#8a2b1a"}`. `skin` is one of `classic`, `chronicle`, `noir`, `terminal`, `grimoire`, `eldritch`, `toon`, `ancient`, `starship`, `pixel`, `thriller`, `sitcom`; `accent` is a `#rrggbb` color. A bare string is shorthand for the skin. Any other key or value is dropped on import (no custom CSS). Without it, the skin is derived from `selected_tone`. The skin also styles the combat dialog (ability cards, item tiles, chronicle, and the arena's player/accent colors). |
| `selected_image_styles`| `array` | List of visual style IDs from the style catalog. |
| `min_scenes` / `max_scenes` | `number` | Constraints defining world generation scope. |
| `container_generation_enabled` | `boolean` | Enables generation of containers with nested loot. |
| `scripts_generation_enabled` | `boolean` | Enables generation of custom event scripts by the World-Builder. |
| `max_containers` | `number` | Hard cap for container objects generated in the world (`0..30`). |
| `award_generation_enabled`| `boolean` | Whether custom achievements/awards are generated for this adventure. |
| `creator` | `string` | Optional author / creator identifier (max 100 chars). |
| `copyright` | `string` | Optional copyright notice (max 100 chars). |
| `license` | `string` | Optional license string or identifier (max 100 chars). |
| `init_script` | `string \| null` | Optional global Python initialization script executed when a new game session starts. Sets up starting variables, narrative messages, and shared helper functions. |
| `dynamic_generation` | `object \| null` | Optional configuration for Dynamic Scenes: `{"scene_image_mode": "off" \| "inherit" \| "simple" \| "hq", "npc_image_mode": "off" \| "simple" \| "hq", "item_image_mode": "off" \| "simple" \| "hq", "audio_mode": "inherit" \| "empty" \| "generate", "generation_model": "mechanics" \| "narration" \| "world_builder", "max_npcs": 0..5, "npc_type_caps": {"humanoid": 0..5, "being": 0..5, "animal": 0..5, "monster": 0..5}, "spawn_chances": {"npc": 0..100, "enemy": 0..100, "humanoid": 0..100, "being": 0..100, "animal": 0..100, "monster": 0..100, "item": 0..100, "container": 0..100, "switch": 0..100}, "interlude_quote_enabled": boolean}`. Defaults to `simple` scene/NPC/item images, `inherit` audio, `mechanics` LLM tier (`small_model`), `2` max NPCs, per-type caps `2`, balanced spawn percentages, and `true` for interlude quotes (a short line of a known HUMANOID / BEING NPC while a dynamic scene is generated, spoken in that NPC's cast TTS voice). *(since 1.4.0)* |
| `game_over_rules` | `object \| null` | Optional. What happens when the protagonist falls to 0 HP: `{on_zero_hp: "game_over" \| "respawn", respawn_hp_percent: 1-100}`. Default (`null` or `game_over`): the adventure ends. See [Respawn](#respawn). *(respawn since 1.4.0)* |
| `npc_conversations` | `object \| null` | Optional. NPCs talking with each other: `{chatter: "OFF" \| "RARE" \| "NORMAL" \| "LIVELY", gossip: bool}`. `null` = chatter off, no gossip. Session state (player switch, quiet counter, heard topics, script relation changes) lives in `entity_states["__conversations__"]`. See [NPC conversations](../world-builder-syntax.md#npc-conversations). *(since 1.4.0)* |

#### Respawn

With `game_over_rules.on_zero_hp: "respawn"` a protagonist who falls to 0 HP is knocked out instead of dying. They wake up at the last **revival point** they reached (a scene with `is_respawn_point: true`), or at the start scene when they have not reached one yet, with `respawn_hp_percent` (default `25`) of their max HP. All status effects are cleared; inventory, quests, the clock and the world stay as they are. In a fight the battle ends with the outcome `knocked_out` (no loot); the enemies keep their HP, and a downed companion gets its `downed_recovery` back and follows if it was at the protagonist's side. The revival scene's `on_enter_scene` scripts run, then the global and sequence scripts with the trigger `on_respawn` (the place for penalties, e.g. losing EXP, or for healing the enemies). The draft narration of the turn is replaced, so the Game Master tells of the knockout and the awakening.

Only falling to 0 HP respawns. `tw.game.game_over()`, the defeat condition (`gameover_condition` / `gameover_guard_expression`) and a Game Master `game_over` always end the adventure. A sequence with `respawn_allowed: false` keeps 0 HP deadly while it is active. Scripts read and move the revival point with `tw.game.respawn_point` / `tw.game.set_respawn_point(scene_id)` and read the count with `tw.game.respawns`. The session record lives in `entity_states["__respawn__"]` (`point`, `count`) and is part of every checkpoint.

---

### 2.2 Protagonist (`protagonist`)

The baseline state and attributes of the player character.

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Character name. |
| `role` | `string` | Character class or narrative role (e.g., `"Rogue"`, `"Arcane Scholar"`). |
| `description` | `string` | Physical description, personality, and backstory. |
| `profile_image` | `string` | Path or URL to the protagonist character portrait. |
| `hp` / `max_hp` | `number` | Starting and maximum health points (default: 200). |
| `stamina` / `mana` | `number` | Secondary resources for physical/magical actions. |
| `stats` | `object` | Core RPG attributes: `strength`, `dexterity`, `intelligence`, `wisdom`, `charisma`, `armor_class`. |
| `starting_inventory` | `array` | Initial list of item objects or item IDs carried by the protagonist. |
| `starting_equipment` | `object` | Mapping of equipment slots (e.g. `"MainHand"`, `"Body"`) to starting items. An item is either carried or equipped, never both: an equipped item is left out of `starting_inventory` when a session starts. In the editor, equipping an item removes it from the starting inventory, and adding an equipped item to the inventory clears its slot. |

---

### 2.2a World sections (`sections`)

Regions that group the scenes of a large world on a world map (a town, a mine, a mountain
range). Every adventure has at least one built region: a manifest without `sections` (or with
`[]`) gets the default region on import (id `MAIN`, named after the adventure), and scenes
without a known built region are placed in the first built one. With a single region the
adventure plays without a world map; it appears from two built regions on. Regions are purely
spatial: they gate nothing; locks stay on exits. Spec and phases:
[World sections](world_sections.md).

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique uppercase slug (e.g. `"HARBOR_TOWN"`, max 50). |
| `label` | `string` | Region name shown to the player. |
| `description` | `string` | One paragraph. While the player is in the region, the Game Master sees `Region: <label>: <description>` in the location block. |
| `map_x`, `map_y` | `number` | Position on the world map in percent (0-100; 0/0 = top left). |
| `order_index` | `number` | List order in the editor. |
| `status` | `"built"` \| `"stub"` \| `"generating"` | `built` (default): the region holds scenes. `stub`: a planned region without scenes, visible to authors only. Sessions never receive stub regions or the author fields below. |
| `brief` | `string` | Optional author directions for building a planned region. |
| `summary` | `string` | Optional short summary of the region's content, used by later generation steps. |
| `planned_links` | `array` | Planned routes of a planned region, whose exits do not exist yet: `[{"to_section_id", "travel_minutes", "note", "gateway_scene_ids"}]` (`gateway_scene_ids`: up to 8 scenes of the target region a generated region connects to first). Links between built regions come from exits whose two scenes lie in different regions. |
| `generated` | `object` \| `null` | What the Region Builder added to a region it built (`scene_ids`, `entity_ids`, `quest_ids`, `award_keys`, `sequence_ids`, `script_ids`, old `planned_links`), so the editor can discard it. Author field. |
| `generation_settings` | `object` \| `null` | The Region Builder's last settings of a planned region (`{mode, context, options}`), so the region can be built again the same way. Author field. |

Exports always contain all regions, planned ones included, so a campaign can be continued
from the file. A session copies the built regions into its adventure snapshot at start.

---

### 2.2b Fast travel

Scenes with `is_fast_travel_point: true` become destinations once unlocked: on first entry
(`fast_travel_unlock: "visit"`, also for the start scene) or by a script
(`tw.game.unlock_fast_travel`). The player then travels there from any scene with
`/fast_travel <place>` or the map's travel strip. Fast travel walks the cheapest known route
(open exits between visited scenes, least travel time, avoiding solo passages while a
companion follows) exit by exit with every hook (`on_exit_used`, companion follow, travel
time, `on_enter_scene`, due time events) and narrates once on arrival. It stops early when
something happens on the way (a hook or time event writes a message, a choice opens, a fight
starts, a script moves the player, the next exit is locked). It is refused during a fight, with
an open choice, when `fast_travel_enabled` is `false`, while the active sequence has
`fast_travel_allowed: false`, or after `tw.game.set_fast_travel(False, reason)`. The session
record lives in `entity_states["__travel__"]` (`unlocked`, `disabled`, `reason`) and is part
of every checkpoint. `GET /api/adventures/{game_id}/travel/options` lists the unlocked points
with route time.

---

### 2.3 Scenes (`scenes`)

The physical locations composing the world map.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique uppercase slug (e.g., `"DUNGEON_CELL"`, `"TAVERN_MAIN"`). |
| `label` | `string` | Human-readable scene name displayed in the UI. |
| `description` | `string` | Sensory, atmospheric description of the location. |
| `image_url` | `string` | Path or URL to the background scenery image. |
| `decorative_objects` | `array` | Up to 7 static background details (max 100 chars each). |
| `audio_track_id` | `string` \| `null` | Optional `id` of the `adventure.audio_tracks` entry that plays in this scene. Scenes sharing a track keep it playing across a scene change; without one the audio fades out. |
| `is_respawn_point` | `boolean` | Optional, default `false`. A revival point: in respawn mode a protagonist who falls to 0 HP wakes up at the last one reached (see [Respawn](#respawn)). *(since 1.4.0)* |
| `section_id` | `string` \| `null` | `id` of the `sections` entry (region) the scene lies in. Missing, `null` or unknown: the first built region on import. A scene may not belong to a planned (`stub`) region. *(since 1.5.0)* |
| `is_fast_travel_point` | `boolean` | Optional, default `false`. A fast travel point: once unlocked, the player can travel here from anywhere (see [Fast travel](#fast-travel)). *(since 1.5.0)* |
| `fast_travel_unlock` | `"visit"` \| `"script"` | Optional, default `"visit"`: the point unlocks on first entry; `"script"`: only `tw.game.unlock_fast_travel(scene_id)` unlocks it. *(since 1.5.0)* |
| `on_enter_scene_script` / `on_enter_scene_text` | `string` | Inline script / message when the player enters the scene. |
| `on_leave_scene_script` / `on_leave_scene_text` | `string` | Inline script / message when the player leaves the scene. |
| `helpers_script` | `string` | Optional scene helper block: functions and constants loaded into every script run after `init_script` and the sequence helpers, like its definitions. Sequences carry the same optional `helpers_script` field. See *Scene Helpers* in the [Scripting Engine guide](../scripting_engine.md). |
| `dynamic_zone` | `object \| null` | Optional pre-mapped Dynamic Scene configuration using the same schema as exit `dynamic_zone` (`zone_id`, `theme`, `instructions`, `instructions_scope`, `cluster_consistency`, `danger_level`, `max_npcs`, `npc_type_caps`, `spawn_chances`, `audio_mode`, `generation_model`, `allowed_entity_types`, `on_after_generated_script`). When present, the scene keeps all authored exits and static entities, while narrative details, visuals/audio, and procedural entities are materialized in-place on first player entry. *(since 1.4.0)* |

---

### 2.4 Exits (`exits`)

Connections and passageways between scenes.

| Field | Type | Description |
| :--- | :--- | :--- |
| `from_scene_id` | `string` | Origin scene ID. |
| `to_scene_id` | `string` | Destination scene ID. |
| `label` | `string` | Required. Names the passage itself, the same from both sides (e.g., `"Heavy Iron Portcullis"`, not `"Way to the Crypt"`); the game adds `→ Target` below it once the target was visited. Older files without a label still load; such exits are shown under their target scene's name. |
| `exit_type` | `string` | `"one_way"` or `"bidirectional"` (default: `"bidirectional"` for normal passages). |
| `is_bidirectional` | `boolean` | Whether the passage can be traversed in both directions (convenience boolean, matches `exit_type == "bidirectional"`). |
| `is_locked` | `boolean` | Whether the exit is initially locked/blocked. |
| `is_revealed` | `boolean` | Optional, default `false`. The target scene is known from the start: the exit tile shows its image and `→ Target`, and the map shows the scene, before the player has visited it. |
| `companions_allowed` | `boolean` | Optional, default `true`. `false` makes a solo passage: the protagonist's active companion stays behind when the exit is used. *(since 1.4.0)* |
| `travel_minutes` | `integer` \| `null` | Optional in-game minutes the way takes (a long road, a ship passage). Using the exit advances the clock by this time instead of the narration tick, uncapped by `max_time_per_turn`; a paused clock stays put. `null`/`0`: no travel time. *(since 1.5.0)* |
| `travel_label` | `string` \| `null` | Optional description of the journey (max 100 chars), shown as "The journey (two days by ship) takes 2 d." *(since 1.5.0)* |
| `code_to_unlock` | `string \| null` | Code/word required to unlock (case-insensitive in gameplay). |
| `item_to_unlock` | `string \| null` | Key item ID required in player inventory to open the exit. |
| `rule_to_unlock` | `string \| null` | Special rule or puzzle description required for unlocking. |
| `lock_description` | `string` | Narrative clue or description when encountering the lock. |
| `dynamic_zone` | `object \| null` | Optional procedural expansion zone configuration: `{"zone_id": string, "theme": string, "instructions": string \| null, "instructions_scope": "once" \| "first_scene" \| "max_depth" \| "all_scenes", "cluster_consistency": boolean, "depth": number, "max_depth": number, "danger_level": "peaceful" \| "low" \| "medium" \| "high" \| "deadly" \| "random", "max_npcs": number \| null, "npc_type_caps": object \| null, "spawn_chances": object \| null, "audio_mode": "inherit" \| "empty" \| "generate" \| null, "generation_model": "mechanics" \| "narration" \| "world_builder" \| null, "allowed_entity_types": array, "cul_de_sac_on_max_depth": boolean, "on_after_generated_script": string \| null, "required_entities": string \| null}`. Optional `npc_type_caps`, `spawn_chances`, and `generation_model` override the adventure-level `dynamic_generation` defaults per exit (`null` inherits), `instructions_scope` (default `"once"`) controls whether freeform/Blueprint instructions run once per cluster or per depth, `cluster_consistency` (default `true`) passes global theme, root exit theme, instructions, and existing cluster scenes/NPCs/items into subsequent cluster scene generation, `on_after_generated_script` runs right after materialization with access to `generated_scene` / `tw.generated_scene`, and `required_entities` holds Blueprint `[NPC]` / `[Item]` blocks (optional `depth: 1-10 | max`) that every cluster of the zone contains exactly once, in the first generated room of their depth (without depth: the first room), beyond `max_npcs` and the object limit (written by the blueprint for entities with `in: ZONE_ID`). When set, entering the exit plans the whole cluster once as a small in-game adventure: a session-scoped cluster blueprint (mini-story arc, antagonist, key item, room nodes, and converging passage graph) in which every room gets its own sub-theme and generation instructions. Each room's session `dynamic_zone` then carries that room's `theme` and `instructions` (`instructions_source: "cluster_blueprint"`); the authored values stay in `root_theme` / `root_instructions` / `root_instructions_scope`. Loose author instructions are folded into the room instructions according to `instructions_scope`; Blueprint-block instructions stay unchanged and the room brief is added to the prompt. Scenes are materialized in-place as they are visited without mutating the base manifest. *(since 1.4.0)* |

---

### 2.5 NPCs (`npcs`)

Non-Player Characters inhabiting the world.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique uppercase slug (e.g., `"NPC_BLACKSMITH"`). |
| `name` | `string` | Character name. |
| `description` | `string` | Appearance, demeanor, and dialogue style. |
| `current_scene_id` | `string` | Initial location scene ID where the NPC is positioned. |
| `spatial_position` | `string` | Placement in scene (e.g., `"behind the counter"`, `"near the fireplace"`). |
| `npc_type` | `string` | `"HUMANOID"`, `"BEING"`, `"ANIMAL"`, or `"MONSTER"`. `HUMANOID` and `BEING` speak intelligible sentences in narration and can deliver dynamic transition quotes; `ANIMAL` and `MONSTER` use non-verbal sounds and gestures only. |
| `movement_type` | `string` | `"STATIONARY"` or `"MOVABLE"`. |
| `voice` | `string \| null` | Google / ElevenLabs TTS voice identifier for dialogue. |
| `hp` / `mana` / `stamina` | `number` | NPC combat and interaction resources. |
| `inventory` | `array` | Items currently held or dropped by the NPC. |
| `is_hidden` | `boolean` | If true, NPC is not immediately visible without inspecting/searching. |
| `reveal_guard_expression` | `string \| null` | Optional (top level or inside `metadata_json`). Sandboxed Python condition; while the NPC is hidden in the protagonist's scene the engine checks it after every player message and reveals the NPC once it is True. Hidden NPCs are never discovered by the Game Master; without a guard only scripts reveal them. |
| `memory_slots` | `number \| null` | Optional (top level or inside `metadata_json`). NPC memory: how many facts about the protagonist the character keeps (1-8; `null`/`0` = no memory; `true` = 4). The Game Master stores them during play in `entity_states["__npc_memory__"]` (`{npc_id: [{key, text}]}`, oldest first, part of every checkpoint); both passes see them only while the character is in the protagonist's scene. *(since 1.4.0)* |
| `relations` | `array \| null` | Optional (top level or inside `metadata_json`). How this NPC sees other NPCs: `[{npc_id, kind, note?}]`, `kind` one of `FRIEND`, `FAMILY`, `PARTNER`, `ALLY`, `COLLEAGUE`, `SUPERIOR`, `SUBORDINATE`, `RIVAL`, `ENEMY`, note max. 80 characters. Script changes live in `entity_states["__conversations__"]["relations"]`. *(since 1.4.0)* |
| `chatty` | `boolean \| null` | Optional. `false` keeps the NPC out of conversations NPCs start on their own; only `false` is stored. *(since 1.4.0)* |
| `conversation_topics` | `array \| null` | Optional. Topics the NPC discusses with another NPC while the protagonist can overhear them: `[{id, topic, with_npc_id?, must_convey?, guard_expression?, repeatable?, on_heard_script?, on_heard_text?}]`. Heard topic ids are stored in `entity_states["__conversations__"]["heard"]`. *(since 1.4.0)* |
| `reveal_rule` | `string \| null` | Legacy, kept for round trips only: hidden NPCs ignore it (the validator warns, `npc_reveal_rule_ignored`). |
| `companion` | `object \| null` | Optional (top level or inside `metadata_json`). Makes the NPC a companion (sidekick) who can travel with the protagonist: `{recruitable, starts_in_party, tactics, banter, downed_recovery, recruit_mode, recruit_item_id, recruit_hint}`. `recruit_mode`: `SCRIPT` (default; only `tw.party.recruit`), `INSTANT` (the player's **Recruit** action, `/recruit <npc>`) or `ITEM` (the Recruit dialog wants `recruit_item_id`, which the NPC keeps; `ITEM` without an item is stored as `INSTANT`); `recruit_hint`: text of the Recruit dialog (max. 300 characters). NPC hooks `on_recruit_success_script` / `_text` and `on_recruit_failure_script` / `_text` narrate the outcome. `tactics`: `BALANCED` (default), `OFFENSIVE`, `DEFENSIVE`, `SUPPORT`; `banter`: `NORMAL` (default), `QUIET`, `CHATTY`; `downed_recovery`: share of max HP (0.01-1, default `0.25`) after being downed. `starts_in_party: true` puts the NPC into the party when a session starts; with several such NPCs the first one is the active companion. `null` (default): an ordinary NPC. See [Companions](#companions). *(since 1.4.0)* |

#### Companions

One companion can be active at a time. While it follows, the engine moves it into every scene the protagonist enters (exit, Game Master transition or script teleport), before `on_enter_scene` runs. It stays behind when it is not in the scene the protagonist left, when it is defeated, or when the exit or the active sequence has `companions_allowed: false`; once the protagonist returns, it follows again from there. The Game Master cannot move the active companion to another scene. The player tells it to stay behind or to come along again (context menu **Stay here** / **Follow me**, `/companion wait|follow`, or in their own words, reported by Pass 1 as `companion_order`); both passes get a COMPANION line in the CURRENT STATE, so the narration knows who travels along and how talkative it is (`banter`). The hero dialog switches between the protagonist and the companion (its **Inspect** opens the companion's page): there the player sees its vitals, attributes and the items it carries, and hands items over with **Give to <companion>** / **Take from <companion>** (`/companion_give`, `/companion_take`; no Game Master turn, no `on_receive_item` trigger). Only `HUMANOID` and `BEING` companions have equipment slots; `ANIMAL` and `MONSTER` companions fight with their main attack and special actions, only carry items, and their page has no **Equipped** tab (`can_equip: false`; equipment stored for them is ignored). A humanoid or being companion has the protagonist's equipment slots: on its **Equipped** tab the player equips items it carries (`/companion_equip <item>[ | <slot>]`, `/companion_unequip <slot>`); equipped items stay in its inventory (`entity_states[<npc>]["equipment"]`, slot -> item ID), add their attribute and armor bonuses, and the `MainHand` item is its weapon in combat. Its abilities are the NPC's `special_actions`; on its **Abilities** tab the player switches each one on or off for combat (`/companion_ability <id> on|off`, stored in `__party__.disabled_abilities`). **Combat** (`rpg` mode): a companion standing in the fight scene fights on the protagonist's side (`combat["party"]`, its own initiative turn) and is never an enemy or a fight target. `tactics`: `OFFENSIVE` attacks the weakest enemy, `DEFENSIVE` draws more enemy attacks (60 % instead of 30 %), `SUPPORT` heals a protagonist below half HP with a healing consumable it carries, `BALANCED` attacks the current target. The protagonist can **Mark** an enemy (free action, only with a fighting companion; `mark <enemy>`, `mark` lifts it): the companion then attacks only that enemy until it falls or flees. It uses its active single-target and self abilities on its own (heals the protagonist below half HP with an `ally` ability, itself below 40 % HP, others with the NPC's `special_chance`). Special-action effects take `target: "target" | "self" | "ally"`: `ally` is the caster's party partner (the companion when the protagonist casts, the protagonist when the companion casts; nothing without one). A `HEAL` action without `effects` can use `heal_target: "ally"` (blueprint `heals: ally`). Weapon on-hit effects only take `target` / `self`. At 0 HP it is downed, not killed, and gets `downed_recovery` of its max HP back after the fight; the fight is lost when the protagonist falls. The session party lives in `entity_states["__party__"]` (`active_id`, `recruited`, `following`, `tactics`) and is part of every checkpoint. **Recruiting**: NPCs whose `recruit_mode` is `INSTANT` or `ITEM` carry `is_recruitable`, `recruit_mode` and `recruit_hint` in the scene payload (never the wanted item); the play view frames their card and offers **Recruit** in the context menu. `/recruit <npc> [| <item>]` (`api/routes/adventures/companion_recruit.py`) recruits through the scripting changeset (`tw.party.recruit`; in `ITEM` mode the item moves into the NPC's inventory first), then runs `on_recruit_success_*`; without a success hook it chains a `[COMPANION_RECRUITED]` Game Master turn. A wrong or missing item runs `on_recruit_failure_*` (default line: the NPC is not convinced). Former party members rejoin for free (`engine/party/recruit_state.py`): a companion replaced by another one stays in `recruited`, and an NPC that accepted its item gets `entity_states[<npc>]["recruit_paid"] = true`; both are offered **Recruit** as `INSTANT`, also script-recruited ones, and rejoin without hooks.

---

### 2.6 Objects (`objects`)

Interactive elements, items, containers, and state machines.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique uppercase slug (e.g., `"CHEST_GOLD"`, `"LEVER_GATE"`). |
| `name` | `string` | Item or object display name. |
| `item_type` | `string` | Classification: `"WEAPON"`, `"WEARABLE"`, `"CONSUMABLE"`, `"KEY"`, `"READABLE"`, `"CONTAINER"`, `"SWITCH"`, or `"CONSTRUCTABLE"`. |
| `description` | `string` | Physical and visual description. |
| `is_portable` | `boolean` | `true` for portable inventory items; `false` for static scene objects. When omitted: `false` for `STATIC` and `SWITCH`, `true` otherwise. A portable `SWITCH` can be taken and flipped from the inventory. |
| `spatial_position` | `string` | Location in scene (e.g., `"resting on the wooden pedestal"`). |
| `wearable_slots` | `array` | Valid equipment slots (e.g., `["Head"]`, `["MainHand"]`, `["Body"]`). |
| `stat_modifiers` | `object` | Attribute buffs/debuffs (e.g., `{"strength": 2, "armor_class": 1}`). |
| `inventory` | `array` | Nested items contained inside `CONTAINER` objects. |
| `is_locked` | `boolean` | Lock state for `CONTAINER` objects. |
| `quest_item` | `boolean` | `true` marks an item the story depends on: the player can never give it to an NPC or companion, and the Game Master cannot take it away (scripts still can). Stored as `metadata_json.quest_item`; exported only when `true`. Shown with a gold frame and a *Quest* tag in-game. |
| `unlock_code` | `string \| null` | Secret code or combination required to open the container. |
| `unlock_item` | `string \| null` | Item ID required to unlock the container. |
| `unlock_rule` | `string \| null` | Narrative condition or requirement to open the container. |
| `switch_state` | `string \| null` | Current active state for `SWITCH` objects (e.g., `"OFF"`). |
| `switch_states` | `array \| null` | State IDs of `SWITCH` objects (e.g., `["OFF", "HALF-OPEN", "ON"]`). Each ID is 1-15 characters: upper-case letters, digits, `_` or `-`. Scripts, transitions and gates use the IDs. |
| `switch_state_labels` | `object` | Optional in-game text per state ID, max. 20 characters (e.g., `{"HALF-OPEN": "Half open"}`). States without a label show their ID. *(since 1.3.1)* |
| `switch_actions` | `array \| null` | Action definitions triggered upon state transitions. |
| `combination_ingredients`| `array` | `CONSTRUCTABLE` recipes: all item IDs that must be combined (at least 2). |
| `result_item_ids` | `array` | `CONSTRUCTABLE` recipes: IDs of the regular items that crafting reveals (at least 1, any item type except `CONSTRUCTABLE`). Results always start hidden. *(since 1.3.1)* |
| `kept_ingredients` | `array` | `CONSTRUCTABLE` recipes: ingredient IDs that are not consumed by crafting. *(since 1.3.1)* |
| `image_url` (recipes) | — | `CONSTRUCTABLE` recipes have no image: exports leave out their `image_url` (and the file), and an imported recipe image is ignored. |
| `craft_guard_expression` | `string` | `CONSTRUCTABLE` recipes: optional guard expression that must hold for crafting. |
| `reveals_item_id` | `string` | Item spawned or revealed upon interaction/use. |
| `reveal_rule` | `string \| null` | Condition under which the Game Master reveals the hidden object. Empty: revealed when the protagonist searches the scene. The reserved value `script` means only scripts, crafting or another item's `reveals_item_id` reveal it. |
| `damage_dice` | `string` | `WEAPON` items: damage formula, e.g. `1d8` or `1d10+2` (default `1d8`). |
| `weapon_cost_type` / `weapon_cost_value` | `string` / `integer` | `WEAPON` items: resource (`stamina` or `mana`) and amount paid per attack (default `stamina` 20). |
| `weapon_category` | `string` | `WEAPON` items: `MELEE` (default), `RANGED` or `MAGIC`. |
| `weapon_hit_stat` | `string` | `WEAPON` items: stat added to the d20 attack roll: `strength`, `dexterity` (default), `intelligence`, `wisdom` or `charisma`. |
| `weapon_effects` | `array` | `WEAPON` items: up to 4 extra effects applied on a hit, in the special-attack effect format `{target: "target" \| "self", stat, amount}` (e.g. poison `{"target": "target", "stat": "stamina", "amount": "-1d4"}`). |

---

### 2.7 Quests (`quests`)

Narrative and mechanical objectives.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique uppercase slug (e.g., `"QUEST_ESCAPE_PRISON"`). |
| `title` | `string` | Quest title shown in the quest tracker. |
| `description` | `string` | Narrative briefing and lore context. |
| `goal` | `string` | Concrete completion requirement for the logic engine. |
| `is_main` | `boolean` | `true` for main story objectives; `false` for side quests. |
| `exp_reward` | `number` | Experience points granted to the protagonist upon completion. |

---

### 2.8 Awards (`awards`)

Achievements players can unlock through specific actions.

| Field | Type | Description |
| :--- | :--- | :--- |
| `key` | `string` | Unique identifier (e.g., `"AWARD_MASTER_THIEF"`). |
| `title` | `string` | Achievement display title. |
| `tier` | `string` | Achievement rank: `"bronze"`, `"silver"`, or `"gold"`. |
| `requirement` | `string` | Exact trigger condition evaluated during turn execution. |

---

### 2.9 Scripts (`scripts` & `init_script`)

Custom sandboxed event scripts reacting to game hooks and global initialization logic. For full syntax, API references, and examples, see the [Scripting Engine Guide](../scripting_engine.md).

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique uppercase slug (e.g., `"SCRIPT_LEVER_PUZZLE"`). |
| `name` | `string` | Human-readable title for the script. |
| `trigger` | `string` | Event hook: `"on_init"`, `"on_turn_start"`, `"on_enter_scene"`, `"on_interact"`, `"on_logic_pass_done"`, `"on_narration_done"`, `"on_turn_end"`, or `"on_time_reached"` (its `target_id` is the elapsed in-game time, e.g. `"90"` or `"2h 30m"`). |
| `target_id` | `string \| null` | Optional target scene ID or entity ID that filters when this script fires. |
| `code` | `string` | Safe Python script utilizing the sandboxed `tw` GameContext API. |
| `description` | `string \| null` | Optional narrative/technical description of the script logic. |

---

### 2.10 Extensions (`extensions`)

An optional top-level object where forks, feature runtimes, and external tools store their
own data without changing the core format. TaleWeaver never interprets it. It keeps the
block on import, keeps it while the adventure is edited, and writes it back on export, so
data from other forks and shared runtimes is not lost.

```json
"extensions": {
  "agent_runtime": {
    "schema_version": 1,
    "fallback": "core",
    "required_features": ["npc.autonomy.v1"],
    "autonomy": { "enabled": true, "max_active_npcs": 3 }
  },
  "comfyui-scenes": {
    "schema_version": 1,
    "checkpoint": "illustrious-xl"
  },
  "my_fork": {
    "presentation": "visual_novel",
    "portraits": { "NPC_GUARD": "assets/guard_vn.png" }
  }
}
```

| Rule | Detail |
| :--- | :--- |
| Namespaces | Each key is a lower-case namespace identifying a specific fork, tool, or shared feature runtime (e.g. `agent_runtime`, `visual_novel`, `my_fork`). It must be 1-64 characters and start with a letter or digit; it may contain `a-z`, `0-9`, `_`, `.` and `-`. Shared feature namespaces should be chosen neutrally so multiple implementations can adopt the same schema. |
| Values | Each namespace value must be a JSON object. Inside it, any JSON is allowed. |
| Schema Versioning | It is recommended that extension objects declare an explicit `schema_version` (e.g. `"schema_version": 1`) so consuming runtimes can detect schema evolutions reliably. |
| Limits | At most 32 namespaces and 256 KB (UTF-8 JSON) in total. |
| Invalid entries | Namespaces with an invalid key, a non-object value, or past the limits are dropped on import and export. The rest of the manifest is not affected. |
| Assets | Asset paths inside `extensions` are passed through as plain strings. They are not packed into or extracted from `.adz` bundles. |
| Export | The key is omitted when there are no valid namespaces. |

Implementations that do not recognize an extension namespace ignore it. Put fork- or
feature-specific data here rather than adding new top-level keys: unknown top-level keys
are ignored on import but are not written back on export. For per-entity data, NPCs and
objects also accept a free-form `metadata_json` object that survives import and export.

`agent_runtime` is the namespace of a shared contract for NPC-side runtime behavior
(autonomous NPCs, NPC psychology, retrieval, a living world), specified in the
[Portable agent runtime contract, version 1](https://github.com/Gam1409/taleweaver/blob/5cd0453db6f24c5068dd5d09dce2527366c2aca7/docs/specs/agent_runtime.md).
It is unrelated to the Play-Agent, which plays an adventure for the player. TaleWeaver
keeps the block but does not run it, and does not evaluate its `fallback` setting.

#### NPC extension namespaces (`npcs[].metadata_json.<namespace>`)

Per-NPC data of a fork or shared runtime goes into the NPC's `metadata_json`, under its
namespace and next to the engine's own NPC settings:

```json
{
  "id": "NPC_GUARD",
  "metadata_json": {
    "agent_runtime": {
      "schema_version": 1,
      "autonomy": "reactive",
      "initial_state": { "situation": "Guards the gate since dawn." }
    }
  }
}
```

| Rule | Detail |
| :--- | :--- |
| Detection | A `metadata_json` key is an extension namespace when its value is a JSON object with a `schema_version`. Engine settings never carry one, so the field is required here. |
| Namespaces | Same key pattern as top-level `extensions` (lower case, 1-64 characters, `a-z`, `0-9`, `_`, `.`, `-`). |
| Preservation | The object is kept unchanged on import, while the adventure is edited and on export, including unknown fields and `null` values. |
| Limits | At most 32 namespaces and 64 KB (UTF-8 JSON) per NPC. |
| Invalid entries | Namespaces with an invalid key or past the limits are dropped on import and export. The NPC and the rest of the manifest are not affected. |
| References | IDs inside a namespace (other NPCs, items) are opaque. Renaming an entity in the editor does not update them. |

---

## 3. Best Practices & Guidelines

1. **Identifiers**: Always use alphanumeric uppercase slugs separated by underscores (e.g. `TEMPLE_ALTAR`, `KEY_RUSTY`).
2. **Relative Assets**: When exporting or creating `.adz` packages, keep image references relative to `assets/` (e.g. `assets/chest.png`).
3. **Container Nesting**: Containers should contain valid item objects with appropriate portability and metadata.
4. **Validation**: All manifests are validated against graph connectivity (every scene reachable via exits) before game session startup.
