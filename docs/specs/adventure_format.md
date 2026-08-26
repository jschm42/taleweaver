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
  "version": "1.3",
  "adventure": { ... },
  "protagonist": { ... },
  "scenes": [ ... ],
  "npcs": [ ... ],
  "objects": [ ... ],
  "exits": [ ... ],
  "quests": [ ... ],
  "awards": [ ... ]
}
```

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
| `walkthrough` | `string` | Recommended walkthrough and puzzle solution steps for the GM / agent modes. |
| `completed_condition` | `string` | Custom condition defining game victory (defaults to all main quests in RPG mode). |
| `gameover_condition` | `string` | Custom condition defining game over (defaults to player HP <= 0 in RPG mode). |
| `original_prompt` | `string` | The original prompt used during generation (for documentation purposes). |
| `image_url` | `string` | Relative path (`assets/...`) or canonical URL (`/data/...`) to the cover visual. |
| `rule_enforcement_mode` | `string` | `"rpg"` (strict mechanics & dice checks), `"story"` (streamlined mechanics), or `"chat"` (pure narrative). |
| `time_per_turn` | `number` | In-game minutes elapsed per player turn (default: 5). |
| `pacing_minutes` | `number` | Frequency of world background heartbeats / scheduled events. |
| `clock_enabled` | `boolean` | Whether to track and display in-game time / calendar. |
| `ingame_timestamp` | `string` | Formatted starting in-game timestamp (e.g. `"Day 1, 08:00"`). |
| `selected_tone` | `string` | Narrative tone identifier or description (e.g. `"Dark Fantasy"`, `"Cyberpunk"`). |
| `selected_image_styles`| `array` | List of visual style IDs from the style catalog. |
| `min_scenes` / `max_scenes` | `number` | Constraints defining world generation scope. |
| `container_generation_enabled` | `boolean` | Enables generation of containers with nested loot. |
| `max_containers` | `number` | Hard cap for container objects generated in the world (`0..30`). |
| `award_generation_enabled`| `boolean` | Whether custom achievements/awards are generated for this adventure. |
| `creator` | `string` | Optional author / creator identifier (max 100 chars). |
| `copyright` | `string` | Optional copyright notice (max 100 chars). |
| `license` | `string` | Optional license string or identifier (max 100 chars). |

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
| `starting_equipment` | `object` | Mapping of equipment slots (e.g. `"MainHand"`, `"Body"`) to starting items. |

---

### 2.3 Scenes (`scenes`)

The physical locations composing the world map.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique uppercase slug (e.g., `"DUNGEON_CELL"`, `"TAVERN_MAIN"`). |
| `label` | `string` | Human-readable scene name displayed in the UI. |
| `description` | `string` | Sensory, atmospheric description of the location. |
| `image_url` | `string` | Path or URL to the background scenery image. |

---

### 2.4 Exits (`exits`)

Connections and passageways between scenes.

| Field | Type | Description |
| :--- | :--- | :--- |
| `from_scene_id` | `string` | Origin scene ID. |
| `to_scene_id` | `string` | Destination scene ID. |
| `label` | `string` | Descriptive name of the exit (e.g., `"Heavy Iron Portcullis"`). |
| `is_locked` | `boolean` | Whether the exit is initially locked/blocked. |
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

---

### 2.6 Objects (`objects`)

Interactive elements, items, containers, and state machines.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique uppercase slug (e.g., `"CHEST_GOLD"`, `"LEVER_GATE"`). |
| `name` | `string` | Item or object display name. |
| `item_type` | `string` | Classification: `"WEAPON"`, `"WEARABLE"`, `"CONSUMABLE"`, `"KEY"`, `"READABLE"`, `"CONTAINER"`, `"SWITCH"`, or `"CONSTRUCTABLE"`. |
| `description` | `string` | Physical and visual description. |
| `is_portable` | `boolean` | `true` for portable inventory items; `false` for static scene objects. |
| `spatial_position` | `string` | Location in scene (e.g., `"resting on the wooden pedestal"`). |
| `wearable_slots` | `array` | Valid equipment slots (e.g., `["Head"]`, `["MainHand"]`, `["Body"]`). |
| `stat_modifiers` | `object` | Attribute buffs/debuffs (e.g., `{"strength": 2, "armor_class": 1}`). |
| `inventory` | `array` | Nested items contained inside `CONTAINER` objects. |
| `is_locked` | `boolean` | Lock state for `CONTAINER` objects. |
| `unlock_code` | `string \| null` | Secret code or combination required to open the container. |
| `unlock_item` | `string \| null` | Item ID required to unlock the container. |
| `unlock_rule` | `string \| null` | Narrative condition or requirement to open the container. |
| `switch_state` | `string \| null` | Current active state for `SWITCH` objects (e.g., `"OFF"`). |
| `switch_states` | `array \| null` | List of valid states for `SWITCH` objects (e.g., `["OFF", "ON"]`). |
| `switch_actions` | `array \| null` | Action definitions triggered upon state transitions. |
| `combination_ingredients`| `array` | Item IDs required to craft/assemble `CONSTRUCTABLE` objects. |
| `reveals_item_id` | `string` | Item spawned or revealed upon interaction/use. |

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

## 3. Best Practices & Guidelines

1. **Identifiers**: Always use alphanumeric uppercase slugs separated by underscores (e.g. `TEMPLE_ALTAR`, `KEY_RUSTY`).
2. **Relative Assets**: When exporting or creating `.adz` packages, keep image references relative to `assets/` (e.g. `assets/chest.png`).
3. **Container Nesting**: Containers should contain valid item objects with appropriate portability and metadata.
4. **Validation**: All manifests are validated against graph connectivity (every scene reachable via exits) before game session startup.
