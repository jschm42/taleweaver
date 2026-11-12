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
  "version": "1.4.0",
  "adventure": { ... },
  "protagonist": { ... },
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
| `1.4.0` (current) | Current format. Adds companions: NPC `companion`, exit and sequence `companions_allowed`. |
| `1.3.1` up to below `1.4.0` | Supported: importable and playable without restrictions; such adventures simply have no companions. |
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
| `on_enter_scene_script` / `on_enter_scene_text` | `string` | Inline script / message when the player enters the scene. |
| `on_leave_scene_script` / `on_leave_scene_text` | `string` | Inline script / message when the player leaves the scene. |
| `helpers_script` | `string` | Optional scene helper block: functions and constants loaded into every script run after `init_script` and the sequence helpers, like its definitions. Sequences carry the same optional `helpers_script` field. See *Scene Helpers* in the [Scripting Engine guide](../scripting_engine.md). |

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
| `code_to_unlock` | `string \| null` | Code/word required to unlock (case-insensitive in gameplay). |
| `item_to_unlock` | `string \| null` | Key item ID required in player inventory to open the exit. |
| `rule_to_unlock` | `string \| null` | Special rule or puzzle description required for unlocking. |
| `lock_description` | `string` | Narrative clue or description when encountering the lock. |

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
| `npc_type` | `string` | `"HUMANOID"`, `"ANIMAL"`, `"MONSTER"`, or `"BEING"`. |
| `movement_type` | `string` | `"STATIONARY"` or `"MOVABLE"`. |
| `voice` | `string \| null` | Google / ElevenLabs TTS voice identifier for dialogue. |
| `hp` / `mana` / `stamina` | `number` | NPC combat and interaction resources. |
| `inventory` | `array` | Items currently held or dropped by the NPC. |
| `is_hidden` | `boolean` | If true, NPC is not immediately visible without inspecting/searching. |
| `reveal_rule` | `string \| null` | Condition under which the Game Master reveals the hidden NPC. Empty: revealed when the protagonist searches the scene or the NPC starts speaking. The reserved value `script` means only scripts reveal it. |
| `companion` | `object \| null` | Optional (top level or inside `metadata_json`). Makes the NPC a companion (sidekick) who can travel with the protagonist: `{recruitable, starts_in_party, tactics, banter, downed_recovery}`. `tactics`: `BALANCED` (default), `OFFENSIVE`, `DEFENSIVE`, `SUPPORT`; `banter`: `NORMAL` (default), `QUIET`, `CHATTY`; `downed_recovery`: share of max HP (0.01-1, default `0.25`) after being downed. `starts_in_party: true` puts the NPC into the party when a session starts; with several such NPCs the first one is the active companion. `null` (default): an ordinary NPC. See [Companions](#companions). *(since 1.4.0)* |

#### Companions

One companion can be active at a time. While it follows, the engine moves it into every scene the protagonist enters (exit, Game Master transition or script teleport), before `on_enter_scene` runs. It stays behind when it is not in the scene the protagonist left, when it is defeated, or when the exit or the active sequence has `companions_allowed: false`; once the protagonist returns, it follows again from there. The Game Master cannot move the active companion to another scene. The player tells it to stay behind or to come along again (context menu **Stay here** / **Follow me**, `/companion wait|follow`, or in their own words, reported by Pass 1 as `companion_order`); both passes get a COMPANION line in the CURRENT STATE, so the narration knows who travels along and how talkative it is (`banter`). The hero dialog switches between the protagonist and the companion (its **Inspect** opens the companion's page): there the player sees its vitals, attributes and the items it carries, and hands items over with **Give to <companion>** / **Take from <companion>** (`/companion_give`, `/companion_take`; no Game Master turn, no `on_receive_item` trigger). **Combat** (`rpg` mode): a companion standing in the fight scene fights on the protagonist's side (`combat["party"]`, its own initiative turn) and is never an enemy or a fight target. `tactics`: `OFFENSIVE` attacks the weakest enemy, `DEFENSIVE` draws more enemy attacks (60 % instead of 30 %), `SUPPORT` heals a protagonist below half HP with a healing consumable it carries, `BALANCED` attacks the current target. At 0 HP it is downed, not killed, and gets `downed_recovery` of its max HP back after the fight; the fight is lost when the protagonist falls. The session party lives in `entity_states["__party__"]` (`active_id`, `recruited`, `following`, `tactics`) and is part of every checkpoint.

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
    "archetype": "reactive_npc",
    "memory_depth": 5
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

---

## 3. Best Practices & Guidelines

1. **Identifiers**: Always use alphanumeric uppercase slugs separated by underscores (e.g. `TEMPLE_ALTAR`, `KEY_RUSTY`).
2. **Relative Assets**: When exporting or creating `.adz` packages, keep image references relative to `assets/` (e.g. `assets/chest.png`).
3. **Container Nesting**: Containers should contain valid item objects with appropriate portability and metadata.
4. **Validation**: All manifests are validated against graph connectivity (every scene reachable via exits) before game session startup.
