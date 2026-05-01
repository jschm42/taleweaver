# TaleWeaver Adventure Format Specification

This document defines the structure and requirements for `.adv` (JSON) and `.adz` (Compressed) adventure files used in TaleWeaver.

---

## 1. File Formats

- **.adv**: A single JSON file containing the full adventure manifest.
- **.adz**: A ZIP archive containing:
  - `adventure.adv`: The main manifest file (JSON).
  - `assets/`: A directory containing image assets referenced in the manifest (e.g., `cover.jpg`, `scene_1.png`).

---

## 2. Manifest Structure (`adventure.adv`)

The manifest is a JSON object containing the complete blueprint of a generated world.

```json
{
  "format": "TaleWeaver",
  "version": "1.1",
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

### 2.1 Adventure Metadata (`adventure`)

General configuration and world-building constraints.

| Field | Type | Description |
| :--- | :--- | :--- |
| `title` | `string` | The title of the adventure. |
| `teaser` | `string` | A short, atmospheric summary (max 300 chars). |
| `context` | `string` | The foundational world-building background for the AI. |
| `image_url` | `string` | Path/URL to the cover image. |
| `strict_rules` | `boolean` | If true, enables the two-pass mechanics engine. |
| `rule_enforcement_mode` | `string` | `"rpg"` (strict), `"story"` (loose), or `"chat"` (no mechanics). |
| `time_per_turn` | `number` | In-game minutes passed per action. |
| `pacing_minutes` | `number` | Frequency of world heartbeat events. |
| `clock_enabled` | `boolean` | Whether to display and track a real-time calendar. |
| `selected_tone` | `string` | The narrative tone (e.g., "Dark Fantasy", "Cyberpunk"). |
| `selected_image_styles`| `array` | List of style IDs used for image generation. |
| `min_scenes` / `max_scenes` | `number` | Constraints for world generation size. |
| `award_generation_enabled`| `boolean` | Whether the system generated custom awards for this adventure. |

### 2.2 Protagonist (`protagonist`)

The starting state of the player character.

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Character name. |
| `role` | `string` | Narrative role or class (e.g., "Exiled Prince"). |
| `description` | `string` | Detailed backstory and physical appearance. |
| `profile_image` | `string` | Path/URL to the character portrait. |
| `hp` / `max_hp` | `number` | Starting health (default 200). |
| `stamina` / `mana` | `number` | Starting secondary resources. |
| `stats` | `object` | Core attributes: `strength`, `dexterity`, `intelligence`, `wisdom`, `charisma`, `armor_class`. |
| `starting_inventory` | `array` | List of initial item objects or IDs. |
| `starting_equipment` | `object` | Mapping of slots (e.g. "Head") to initial item objects. |

### 2.3 Scenes (`scenes`)

The physical locations of the world.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique slug (e.g., `"DUNGEON_CELL"`). |
| `label` | `string` | Human-readable name. |
| `description` | `string` | Rich sensory description of the location. |
| `image_url` | `string` | Path/URL to the scene background. |

### 2.4 Exits (`exits`)

Connections between scenes.

| Field | Type | Description |
| :--- | :--- | :--- |
| `from_scene_id` | `string` | Source scene ID. |
| `to_scene_id` | `string` | Destination scene ID. |
| `label` | `string` | Description of the path (e.g., `"a creaky wooden door"`). |
| `is_locked` | `boolean` | Whether the path is initially blocked. |
| `lock_description` | `string` | Explanation for the lock (e.g., `"requires a silver key"`). |

### 2.5 NPCs (`npcs`)

Non-Player Characters inhabiting the world.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique slug. |
| `name` | `string` | Character name. |
| `description` | `string` | Appearance and demeanor. |
| `current_scene_id` | `string` | Where the NPC starts. |
| `spatial_position` | `string` | Precise location (e.g., `"leaning against the fountain"`). |
| `npc_type` | `string` | `"HUMANOID"`, `"ANIMAL"`, `"MONSTER"`, or `"BEING"`. |
| `movement_type` | `string` | `"STATIONARY"` or `"MOVABLE"`. |
| `hp` / `mana` / `stamina` | `number` | NPC resources for combat/interactions. |
| `is_hidden` | `boolean` | If true, the NPC is not immediately visible. |

### 2.6 Objects (`objects`)

Items and interactable elements.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique slug. |
| `name` | `string` | Item name. |
| `item_type` | `string` | `"WEAPON"`, `"WEARABLE"`, `"CONSUMABLE"`, `"KEY"`, `"READABLE"`, etc. |
| `description` | `string` | Physical description. |
| `is_portable` | `boolean` | If false, the item is `"STATIC"` (e.g., a heavy altar). |
| `spatial_position` | `string` | Where it is found (e.g., `"on the pedestal"`). |
| `wearable_slots` | `array` | Valid slots (e.g., `["Head"]`, `["MainHand"]`). |
| `stat_modifiers` | `number` | Modifiers for core attributes (e.g., `stat_modifier_strength`). |
| `combination_ingredients`| `array` | List of IDs needed to craft/unlock this item. |
| `reveals_item_id` | `string` | Item revealed when this one is used/triggered. |

### 2.7 Quests (`quests`)

Objectives for the adventure.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique slug. |
| `title` | `string` | Quest name. |
| `description` | `string` | Narrative hook for the quest. |
| `goal` | `string` | Technical completion requirement. |
| `is_main` | `boolean` | Primary vs. Side objectives. |
| `exp_reward` | `number` | Experience granted upon completion. |

### 2.8 Awards (`awards`)

Achievements players can earn.

| Field | Type | Description |
| :--- | :--- | :--- |
| `key` | `string` | Unique identifier. |
| `title` | `string` | Achievement name. |
| `tier` | `string` | `"bronze"`, `"silver"`, or `"gold"`. |
| `requirement` | `string` | Condition to earn the award. |

---

## 3. Best Practices

- **IDs**: Use upper-case slugs with underscores (e.g., `ROYAL_TREASURY`) for consistency.
- **Assets**: Always use relative paths (`assets/filename.png`) in the manifest when bundling into an `.adz`.
- **Normalization**: Ensure all resources (HP, Mana) are within expected RPG ranges (default cap is 200).
