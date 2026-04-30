# LLM Injection & Interaction Specification

This document details how the **Adventure Manifest** and **World State** are injected into the Large Language Model (LLM) prompts during each game turn, and how the LLM interacts with the game engine via structured outputs.

TaleWeaver uses a **Two-Pass System** for every turn when `strict_rules` are enabled:
1. **Rule-Call (Mechanics Pass):** Evaluates player input against world logic and character stats.
2. **Narrative-Call (Story Pass):** Generates the final atmospheric response based on the mechanical outcome.

---

## 1. Context Injection (Common to both calls)

Every turn, a foundational "System Prompt" is built. The following attributes from the Adventure Manifest and current Session State are injected:

### Character Sheet (`sheet_json`)
| Attribute | Source | Description |
| :--- | :--- | :--- |
| `name` | Avatar | The protagonist's name. |
| `role` | Avatar | The character class or narrative role (e.g., "Rogue", "Scholar"). |
| `description` | Avatar | Background story and physical description. |
| `hp`, `stamina`, `mana` | Avatar | Current resource values. |
| `stats` | Avatar + Equipment | Aggregated Core Attributes: Strength, Dexterity, Intelligence, Wisdom, Charisma, Armor Class. |
| `equipment` | Avatar | Currently equipped items and their slots. |
| `inventory` | Avatar | All items carried by the player. |
| `status_effects` | Avatar | Active conditions (e.g., "Poisoned", "Resting"). |

### Location Context (`location_context`)
| Attribute | Source | Description |
| :--- | :--- | :--- |
| `NAME` | WorldScene | Label of the current location. |
| `ID` | WorldScene | Unique identifier for internal logic. |
| `DESCRIPTION` | WorldScene | The static narrative description of the scene. |
| `PRESENT NPCs` | WorldEntity | List of NPCs in the scene with HP, Mana, Stamina, and `spatial_position`. |
| `OBJECTS` | WorldEntity | List of interactable objects with their `spatial_position`. |
| `AVAILABLE EXITS` | WorldExit | List of exits with `label`, destination `ID`, and lock status (including `lock_description`). |

### World & Time
| Attribute | Source | Description |
| :--- | :--- | :--- |
| `world_context` | Adventure Manifest | The foundational world-building background, story idea, and narrative tone (see Deep Dive below). |
| `CURRENT GAME TIME` | Session State | Current in-game time formatted as `Day X, HH:MM`. |

---

## 2. Deep Dive: `world_context`

The `world_context` (sourced from the `adventure.context` field) serves as the **foundational narrative anchor**. It is injected into every prompt to ensure the Game Master (GM) respects the established "Static Reality" of the world.

It contains:
- **Story Idea & Premise:** The core hook of the adventure (e.g., "A post-apocalyptic desert where water is currency").
- **World Lore:** Societal structures, historical background, and established myths.
- **Narrative Tone:** Derived from the adventure's selected tone (e.g., "Dark Fantasy", "Heroic", "Lovecraftian"), instructing the AI on the appropriate vocabulary and level of grit.
- **Persistent Rules:** Universal truths that do not change (e.g., "Magic requires a physical sacrifice", "The sun never sets in this realm").

---

## 3. Rule-Call (Pass 1: Mechanics)

In this pass, the LLM acts as the **Logic Engine**. It receives the foundation plus specific mechanics-focused instructions.

### Injected Metadata
- **`quests_json`**: A list of all quests (Main and Side) with their current `status` (active/completed).
- **`awards_json`**: A list of all earnable awards and their specific requirements.

### LLM "Tool Calls" (Structured Output)
The LLM responds with a structured `GameEvent` object. It "calls" game logic by setting these fields:

| Field | Effect |
| :--- | :--- |
| `hp_change`, `stamina_change`, `mana_change` | Modifies player resources (positive or negative). |
| `new_inventory_items` | Grants the player new items (with full stats/descriptions). |
| `new_status_effects` | Applies conditions like "Burning" or "Blessed". |
| `new_scene_id` | **Navigation**: Moves the player to a different location ID. |
| `requested_skill_checks` | **Dice Roll**: Triggers a check (e.g., "Strength DC 15 to break door"). |
| `updated_entities` | Updates NPC/Object HP, name, description, or position. |
| `moved_entities` | Moves an NPC or Object to a different scene or position. |
| `updated_exits` | Locks or unlocks doors/paths. |
| `completed_quest_ids` | Marks specific quests as finished. |
| `earned_award_keys` | Grants achievements to the player. |
| `extra_time_minutes` | Adds duration to the current turn (e.g., "Climbing takes 10 mins"). |
| `game_over` / `game_completed` | Ends the session with a specific `status_note`. |

---

## 3. Narrative-Call (Pass 2: Narration)

The LLM now acts as the **Storyteller**. It is instructed to ignore system IDs and focus on atmosphere.

### Injected Metadata
- **`outcome_json`**: The full `GameEvent` produced in Pass 1. 
    - *Example:* If Pass 1 decided the player takes 10 damage and finds a "Rusty Key", the Narrative-Call receives this data to weave it into the story.
- **Contextual Instructions**: Depending on the outcome, the engine appends specific instructions:
    - **New Location**: "Write a rich, atmospheric introduction."
    - **Detailed Request**: "Provide a detailed physical description of the surroundings."
    - **Snappy**: "Keep the response short and punchy."

---

## 4. LLM Selection Strategy

TaleWeaver optimizes performance and quality by using different models for each pass:
- **Rule-Call**: Typically uses a **smaller, faster, instruction-following model** (e.g., GPT-4o-mini) to ensure logical accuracy and low latency.
- **Narrative-Call**: Typically uses a **larger, more creative model** (e.g., GPT-4o or Claude 3.5 Sonnet) for high-quality prose and character voice.
