---
name: taleweaver-inspector
description: Comprehensive diagnostic tool and cheatsheet for inspecting TaleWeaver database status, adventures, runtime session states, player inventories, entity overrides, dialogue turns, and manifests.
---

# TaleWeaver State, Database & Manifest Inspector

Use this skill whenever you need to inspect or debug TaleWeaver game data, active sessions, player inventories, entity visibility, dialogue turns, disk adventures, or database statistics.

The CLI inspector is located at: [scripts/inspect_state.py](file:///c:/Users/jean/DEV/repositories/taleweaver/scripts/inspect_state.py).

Always execute commands using `poetry run python scripts/inspect_state.py <command>`.

---

## Quick Reference Commands

### 1. Database Health & Storage Overview
Check database location, file sizes (DB, WAL, SHM), journal mode, record counts across all tables, and disk storage usage across `data/` subdirectories:
```bash
poetry run python scripts/inspect_state.py db-status
```
*Tip: Append `--json` for machine-readable JSON.*

---

### 2. Adventure Management & Inspection

#### List All Adventures in Database
List all imported templates with their IDs, titles, versions, languages, and statuses:
```bash
poetry run python scripts/inspect_state.py list-adventures
```

#### Scan Adventures on Disk
Discover all `.adv`, `.adz`, and manifest files in `adventures/` and `data/imports/` and check whether they are already imported into the database:
```bash
poetry run python scripts/inspect_state.py list-disk-adventures
```

#### Import an Adventure File or Directory
Import any `.adv`, `.adz`, or manifest directly into the database, automatically assigning ownership to the administrator (or specified `--user`):
```bash
# Import a specific adventure file (e.g. sample or test adventure)
poetry run python scripts/inspect_state.py import-adventure adventures/samples/Kitchen_Crisis.adz

# Import with overwrite enabled
poetry run python scripts/inspect_state.py import-adventure adventures/default/combat_test_adventure.adv --overwrite

# Import for a specific user
poetry run python scripts/inspect_state.py import-adventure adventures/samples/The_Alchemists_Folly.adz --user admin
```

#### Inspect an Adventure Template
Inspect scenes, entities/items, exits, quests, and rules for a template (searched by ID, origin_id, or title):
```bash
poetry run python scripts/inspect_state.py show-adventure "Kitchen Crisis"
```
Filter specific aspects:
```bash
# Show only world entities & items (reveals hidden flags, combination ingredients, rules)
poetry run python scripts/inspect_state.py show-adventure "Kitchen Crisis" --entities

# Show only scenes
poetry run python scripts/inspect_state.py show-adventure "Kitchen Crisis" --scenes

# Show only exits & lock rules
poetry run python scripts/inspect_state.py show-adventure "Kitchen Crisis" --exits

# Dump the full original manifest JSON
poetry run python scripts/inspect_state.py show-adventure "Kitchen Crisis" --manifest
# Or directly:
poetry run python scripts/inspect_state.py dump-manifest "Kitchen Crisis"
```

---

### 3. Session State & Gameplay Inspection

#### List Active & Recent Game Sessions
List recently updated game sessions across all users:
```bash
# Show last 10 sessions (default)
poetry run python scripts/inspect_state.py list-sessions

# Show last 20 sessions
poetry run python scripts/inspect_state.py list-sessions --limit 20

# Show all sessions
poetry run python scripts/inspect_state.py list-sessions --all
```

#### Deep-Inspect a Game Session State
Inspect the full runtime state of a specific session (avatar stats, inventory, current scene, entity overrides, quests, active conditions):
```bash
poetry run python scripts/inspect_state.py show-session <session_id_or_prefix>
```
*Example:*
```bash
poetry run python scripts/inspect_state.py show-session sledge-and-order-4178bfd5
```

#### Focused Session Inspections
```bash
# Focus only on the player's current inventory and equipment
poetry run python scripts/inspect_state.py show-session <session_id> --inventory

# Focus only on world entities and their runtime overrides
poetry run python scripts/inspect_state.py show-session <session_id> --entities

# Show only hidden items in this session
poetry run python scripts/inspect_state.py show-session <session_id> --hidden-only

# Display dialogue history and conversational turns (User, Assistant, System)
poetry run python scripts/inspect_state.py show-session <session_id> --chat
poetry run python scripts/inspect_state.py show-session <session_id> --chat --limit-messages 50

# Display saved checkpoints for this session
poetry run python scripts/inspect_state.py show-session <session_id> --checkpoints

# Output complete session snapshot as JSON
poetry run python scripts/inspect_state.py show-session <session_id> --json
```

---

## Diagnostic Scenarios & Workflows

### Scenario A: *"Item was not added to inventory or disappeared"*
1. Run `poetry run python scripts/inspect_state.py show-session <session_id> --inventory` to see if the item is present in `avatar.inventory`.
2. Run `poetry run python scripts/inspect_state.py show-session <session_id> --entities` to check if `is_in_inventory: True` or `is_hidden: False` is recorded in `entity_states` overrides.

### Scenario B: *"Item was combined or revealed but is not visible in-game"*
1. Run `poetry run python scripts/inspect_state.py show-adventure <template_id> --entities` to inspect its defined `item_type` (`CONSTRUCTABLE`, `PICKABLE`), `combination_ingredients`, and `reveal_rule`.
2. Run `poetry run python scripts/inspect_state.py show-session <session_id> --entities` to verify whether the session has overridden `is_hidden` to `False` and what `current_scene_id` it was relocated to.

### Scenario C: *"Exit won't unlock / lock state mismatch"*
1. Run `poetry run python scripts/inspect_state.py show-adventure <template_id> --exits` to inspect `item_to_unlock`, `code_to_unlock`, and `rule_to_unlock`.
2. Run `poetry run python scripts/inspect_state.py show-session <session_id>` to check `exit_states` overrides.

### Scenario D: *"The game master / LLM generated an unexpected scene or turn"*
1. Run `poetry run python scripts/inspect_state.py show-session <session_id> --chat` to inspect the exact prompt and message sequence passed between User, Assistant, and System.
2. Review the latest System entries to verify location announcements, status changes, and injected context.
