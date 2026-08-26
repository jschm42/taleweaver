# LLM Injection & Turn Pipeline Specification

This document specifies the exact structure of Large Language Model (LLM) prompts, context injection mechanisms, and the multi-pass execution pipeline used during TaleWeaver gameplay turns.

---

## 1. Multi-Pass Turn Pipeline Overview

TaleWeaver processes each player turn through a **3-phase structured pipeline** (`GameTurnManager`):

```
Player Message ──► [Pass 1: Mechanics LLM] ──► Proposed GameEvent
                                                      │
                                                      ▼
                                           [Pass 1.5: Rule Validation & Reversion]
                                           (Validates Exits, Containers, Switches, Visibility)
                                                      │
                                           ┌──────────┴──────────┐
                                      Valid Actions         Violations / Reverts
                                           │                     │
                                           ▼                     ▼
                                    Standard Prompt      Failure Override Prompt
                                           │                     │
                                           └──────────┬──────────┘
                                                      │
                                                      ▼
                                           [Pass 2: Narration LLM] ──► Streamed Prose & Audio
```

1. **Pass 1 (Mechanics Pass):** Evaluates player input against rules, stats, and world state; proposes structured state changes (`GameEvent`).
2. **Pass 1.5 (Rule Validation & Reversion Gates):** Server-side authoritative validation of all proposed state mutations against database rules, key items, secret codes, and visibility boundaries. Illegal actions are reverted and recorded as `rule_violations`.
3. **Pass 2 (Story / Narration Pass):** Generates atmospheric narration. When `rule_violations` are present, narration is instructed to narrate the failure reason accurately rather than hallucinating success.

---

## 2. Context Injection Components

Every turn, `GameTurnManager` builds a comprehensive prompt context depending on the configured `rule_enforcement_mode`.

### 2.1 Character Sheet (`sheet_json`)

| Attribute | Source | Injected in Modes | Description |
| :--- | :--- | :--- | :--- |
| `name` | `Avatar` | All Modes | Protagonist character name. |
| `role` | `Avatar` | All Modes | Character class or narrative role (e.g. `"Mage"`, `"Scout"`). |
| `description` | `Avatar` | All Modes | Physical appearance and backstory. |
| `hp` / `max_hp` | `Avatar` | RPG, Story | Current and maximum health points. |
| `stamina`, `mana` | `Avatar` | RPG | Secondary physical and magical resource pools. |
| `stats` | `Avatar` + Equipment | RPG | Core attributes: Strength, Dexterity, Intelligence, Wisdom, Charisma, Armor Class. |
| `equipment` | `Avatar` | RPG, Story | Equipped items mapped to body slots. |
| `inventory` | `Avatar` | RPG, Story | List of carried items, descriptions, and quantities. |
| `status_effects` | `Avatar` | RPG, Story | Active conditions (e.g. `"Poisoned"`, `"Blessed"`). |

---

### 2.2 Location Context (`location_context`)

| Attribute | Source | Description |
| :--- | :--- | :--- |
| `NAME` | `WorldScene` | Label of the current location. |
| `ID` | `WorldScene` | Unique scene identifier. |
| `DESCRIPTION` | `WorldScene` | Sensory description of the current room/environment. |
| `PRESENT NPCs` | `WorldEntity` | NPCs currently located in the scene, including HP, resources, demeanor, and `spatial_position`. |
| `OTHER NPCs` | `WorldEntity` | NPCs located elsewhere in the world (for off-scene movement reference). |
| `OBJECTS` | `WorldEntity` | Interactable items, containers (and visible contents), and switches (with `switch_state`). |
| `AVAILABLE EXITS` | `WorldExit` | All exits connected to the scene with destinations, lock status, and lock clues. |

---

### 2.3 World & Narrative State

| Attribute | Source | Description |
| :--- | :--- | :--- |
| `world_context` | `AdventureTemplate` | Foundational lore, story premise, and atmospheric guidelines. |
| `plot` | `AdventureTemplate` | Core plot summary and story milestones. |
| `rules` | `AdventureTemplate` | Special world laws and universal constraints. |
| `walkthrough` | `AdventureTemplate` | Intended puzzle solutions and quest progression steps. |
| `tone` | `AdventureTemplate` | Selected tone instructions (e.g., vocabulary, grit, dark fantasy). |
| `CURRENT GAME TIME` | `SessionState` | In-game clock formatted as `Day X, HH:MM`. |
| `quests_json` | `SessionState` | All active and completed quests with completion criteria. |
| `awards_json` | `SessionState` | Available achievements and unlock conditions. |

---

## 3. Pass 1: Mechanics Evaluation

In Pass 1, the LLM operates as the **Logic & Rules Engine** (typically using a fast, instruction-focused model).

### Dynamic Item Generation Guardrail
- Spontaneous item generation is permanently disabled in Pass 1 prompts.
- The LLM may only transfer existing pre-defined items from the adventure library or NPC inventories into the player's inventory or scene.

### Output Structure (`GameEvent`)
The LLM outputs structured JSON matching the `GameEvent` schema:

| Field | Mechanical Effect |
| :--- | :--- |
| `hp_change`, `stamina_change`, `mana_change` | Numerical adjustments to player resource pools. |
| `new_inventory_items` | Items moved into the protagonist's inventory. |
| `new_status_effects` | Status conditions added to the character sheet. |
| `new_scene_id` | Navigation: changes protagonist's current location. |
| `requested_skill_checks` | Triggers dice roll evaluations (e.g. `Strength DC 15`). |
| `updated_entities` | State/stat updates for scene NPCs and objects. |
| `moved_entities` | Repositions NPCs or objects across scenes. |
| `updated_exits` | Changes exit lock states (`is_locked: false`). |
| `completed_quest_ids` | Marks completed quest milestones. |
| `earned_award_keys` | Unlocks achievement keys for the player. |
| `extra_time_minutes` | Additional in-game time elapsed for complex actions. |
| `game_over` / `game_completed` | Ends the session with a specific `status_note`. |

---

## 4. Pass 1.5: Server-Side Rule Validation & Reversion

Before generating the narrative in Pass 2, `GameTurnManager` systematically validates all state mutations against authoritative database gates:

1. **Exit Lock Validation:**
   - **Item-Gated Exits:** Checks that the required key item is in player inventory AND referenced in the turn message (language-agnostic intent check).
   - **Code-Gated Exits:** Verifies the required passcode/secret word was supplied.
   - If invalid: Reverts `is_locked` back to `true`, cancels `new_scene_id`, and adds a violation notice.
2. **Container Lock Validation:**
   - Evaluates required unlock codes, items, or keys for container entities.
   - If invalid: Reverts `is_locked` to `true`, blocks access to nested loot, and adds a violation notice.
3. **Switch State Validation:**
   - Validates prerequisites for state transitions on `SWITCH` entities.
   - If invalid: Reverts `switch_state` to its pre-turn state and adds a violation notice.
4. **Visibility & Target Guardrails:**
   - Inspect and search commands are blocked if target entities are off-scene and not within the player's or present NPCs' accessible inventories.

---

## 5. Pass 2: Atmospheric Narration Generation

In Pass 2, the LLM acts as the **Storyteller & Game Master** (typically using a larger, creative model).

### Handling Rule Violations
- If `rule_violations` is non-empty, the system overrides `game_event.narrative_description` with the list of failed preconditions.
- Pass 2 is explicitly commanded to narrate the **failure** (e.g., door remaining locked, chest resisting attempts, lack of required tools) and provide atmospheric narrative feedback without breaking immersion.

### Vocal Tags for TTS
- Narration supports bracketed vocal directives (e.g. `[whispers]`, `[shouts]`, `(softly)`).
- The TTS engine strips these tags before speech synthesis while matching character dialogue to configured NPC voices.
