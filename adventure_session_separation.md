# Implementation Plan: Adventure & Session Separation

This plan outlines the structural changes to separate the "Adventure Template" (static blueprint) from the "Game Session" (active playthrough) and its "Session State" (mutable progress).

## 1. Domain Model Definition

### AdventureTemplate (Static Blueprint)
*   **Purpose**: Stores the canonical world data, rules, and configuration created by the GM/Editor.
*   **Entity**: `AdventureTemplate` (mapped from current `Adventure`).
*   **Child Entities**:
    *   `TemplateScene`: Static definition of a location.
    *   `TemplateExit`: Static connection between locations.
    *   `TemplateEntity`: Static definition of NPCs and Objects.

### GameSession (Playthrough Instance)
*   **Purpose**: Tracks a specific player's engagement with an adventure.
*   **Fields**: `id`, `user_id`, `avatar_id`, `template_id`, `status` (active/archived).

### SessionState (Runtime Progress)
*   **Purpose**: Stores all mutable data for a session.
*   **Fields**:
    *   `session_id`: Link to `GameSession`.
    *   `current_scene_id`: Where the player is now.
    *   `in_game_time`: Current time in minutes.
    *   `inventory`: List of entity IDs currently held by the player.
    *   `entity_states`: JSON mapping of modified entities (e.g., moved NPCs, reduced HP, removed objects).
    *   `exit_states`: JSON mapping of modified exits (e.g., unlocked doors).
    *   `discovered_nodes`: List of visited scene IDs (for the map).
    *   `is_completed`: Whether the adventure is finished.

---

## 2. Step-by-Step Implementation

### Phase 1: Database & Models (Steps 1-4)
1.  **Rename/Create Models**:
    *   Create `backend/models/adventure_template.py` (copy of `adventure.py` but focused on template data).
    *   Create `backend/models/game_session.py`.
    *   Create `backend/models/session_state.py`.
2.  **Update Related Tables**:
    *   Update `WorldScene`, `WorldExit`, `WorldEntity` to link to `template_id` instead of `adventure_id` (or keep both during transition if needed, but the user said "Start with new DB").
3.  **Generate Migration**: Create a new Alembic migration to initialize these tables.

### Phase 2: Backend Logic & CRUD (Steps 5-8)
1.  **Adventure Service**: Update creation logic to populate `AdventureTemplate`.
2.  **Session Service**:
    *   `create_session(user_id, avatar_id, template_id)`: Initializes a `GameSession` and a default `SessionState`.
    *   `reset_session(session_id)`: Resets `SessionState` back to defaults derived from the template.
3.  **Chat & Engine Integration**:
    *   Update the GM engine to read from `AdventureTemplate` but read/write state to `SessionState`.

### Phase 3: Frontend Integration (Steps 11-12)
1.  **Portal UI**:
    *   **Adventures Tab**: Show available templates. Add "Start New Session" button.
    *   **Sessions Tab**: Show active playthroughs with "Resume", "Delete", and "Reset" options.
2.  **Editor UI**: Ensure it only modifies `AdventureTemplate`.

---

## 3. Detailed Data Flow (Example: Pickup Item)

1.  **Action**: Player runs `/pickup OLD_KEY`.
2.  **Lookup**: Engine checks `AdventureTemplate` for `OLD_KEY` and its initial position.
3.  **Validation**: Engine checks `SessionState.entity_states` to see if `OLD_KEY` was already moved or picked up.
4.  **Mutation**:
    *   Add `OLD_KEY` to `SessionState.inventory`.
    *   Update `SessionState.entity_states["OLD_KEY"]` to mark it as `is_in_inventory = true`.
5.  **Persistence**: Save `SessionState` to DB.

---

## 4. Next Actions
- [ ] Create new model files.
- [ ] Implement `GameSession` and `SessionState` schemas.
- [ ] Update `backend/main.py` to include new routes.
