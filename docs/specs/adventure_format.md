# TaleWeaver Adventure Format Specification

This document defines the structure and requirements for `.adv` (JSON) and `.adz` (Compressed) adventure files used in TaleWeaver.

## 1. File Formats

- **.adv**: A single JSON file containing the full adventure manifest.
- **.adz**: A ZIP archive containing:
  - `adventure.adv`: The main manifest file (JSON).
  - `assets/`: A directory containing image assets referenced in the manifest (e.g., `cover.jpg`, `scene_1.png`).

---

## 2. Manifest Structure (`adventure.adv`)

The manifest is a JSON object with the following top-level structure:

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

Contains general information and configuration for the adventure.

| Field | Type | Description |
| :--- | :--- | :--- |
| `title` | `string` | **Required.** The name of the adventure. |
| `teaser` | `string` | A short summary shown in the library. |
| `context` | `string` | The world-building background for the AI. |
| `image_url` | `string` | Relative path to the cover image or absolute URL. |
| `strict_rules` | `boolean` | Whether the AI should strictly follow mechanics. |
| `selected_tone` | `string` | The narrative tone (e.g., "Dark Fantasy", "Heroic"). |
| `time_per_turn` | `number` | Minutes passed in-game per player action. |
| `pacing_minutes`| `number` | Frequency of world heartbeat events. |

### 2.2 Protagonist (`protagonist`)

Defines the starting state of the player character.

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Character name. |
| `role` | `string` | Character class or role. |
| `description` | `string` | Visual and background description. |
| `starting_inventory` | `array` | List of item IDs or full object definitions. |
| `starting_equipment` | `object` | Mapping of slots (e.g., "Hands") to item IDs or objects. |

### 2.3 Quests (`quests`)

A list of objectives for the player.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique identifier. |
| `title` | `string` | Quest name. |
| `goal` | `string` | What needs to be achieved. |
| `is_main` | `boolean` | If `true`, this is a primary story quest. |
| `status` | `string` | Initial state (`"open"` or `"completed"`). |

### 2.4 Awards (`awards`)

Achievements that can be earned.

| Field | Type | Description |
| :--- | :--- | :--- |
| `key` | `string` | Unique identifier. |
| `title` | `string` | Award name. |
| `tier` | `string` | `"bronze"`, `"silver"`, or `"gold"`. |
| `requirement` | `string` | Description of how to earn it. |

---

## 3. Best Practices for Agents

- **Always populate `adventure_title`**: When creating a `GameSession`, ensure this field is set to prevent UI crashes if the template is deleted.
- **Normalize Protagonist Items**: During import, check if `starting_inventory` contains strings (IDs) or objects, and handle accordingly.
- **Relative Asset Paths**: Image paths in an `.adz` should be relative to the ZIP root (e.g., `assets/scene_1.jpg`).
