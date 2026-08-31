---
name: taleweaver-inspector
description: Diagnostic tool and cheatsheet for inspecting TaleWeaver adventures, session states, avatar inventory, runtime entity overrides, hidden objects, and manifests directly from the backend database.
---

# TaleWeaver State & Manifest Inspector

Use this skill when you need to inspect or debug TaleWeaver game data, active sessions, player inventories, entity visibility, or adventure templates.

The CLI inspector is located at: [scripts/inspect_state.py](file:///c:/Users/jschmitz/DEV/git-repositories/taleweaver/scripts/inspect_state.py).

---

## Quick Reference Commands

### 1. List All Available Adventures
List all templates with their IDs, titles, versions, languages, and creation statuses:
```bash
python scripts/inspect_state.py list-adventures
```
*Tip: Append `--json` for machine-readable JSON.*

### 2. Inspect an Adventure Template
Inspect scenes, entities/items, exits, quests, and rules for a template (search by ID, origin_id, or title):
```bash
python scripts/inspect_state.py show-adventure "Kitchen Crisis"
```
Filter specific aspects:
```bash
# Show only world entities & items (reveals hidden flags, combination ingredients, rules)
python scripts/inspect_state.py show-adventure "Kitchen Crisis" --entities

# Show only scenes
python scripts/inspect_state.py show-adventure "Kitchen Crisis" --scenes

# Show only exits & lock rules
python scripts/inspect_state.py show-adventure "Kitchen Crisis" --exits

# Dump the full original manifest JSON
python scripts/inspect_state.py show-adventure "Kitchen Crisis" --manifest
# Or directly:
python scripts/inspect_state.py dump-manifest "Kitchen Crisis"
```

### 3. List Active & Recent Game Sessions
List recently updated game sessions across all users:
```bash
# Show last 10 sessions (default)
python scripts/inspect_state.py list-sessions

# Show last 20 sessions
python scripts/inspect_state.py list-sessions --limit 20

# Show all sessions
python scripts/inspect_state.py list-sessions --all
```

### 4. Deep-Inspect a Game Session State
Inspect the full runtime state of a specific session (player inventory, current scene, entity overrides, quests):
```bash
python scripts/inspect_state.py show-session <session_id_or_prefix>
```
*Example:*
```bash
python scripts/inspect_state.py show-session kitchen-crisis-f5277864
```

Focused Session Inspections:
```bash
# Focus only on the player's current inventory
python scripts/inspect_state.py show-session <session_id> --inventory

# Focus only on world entities and their runtime overrides
python scripts/inspect_state.py show-session <session_id> --entities

# Show only hidden items in this session
python scripts/inspect_state.py show-session <session_id> --hidden-only

# Output complete session snapshot as JSON
python scripts/inspect_state.py show-session <session_id> --json
```

---

## Diagnostic Scenarios & Workflows

### Scenario A: *"Item X was not added to inventory / disappeared"*
1. Run `python scripts/inspect_state.py show-session <session_id> --inventory` to see if the item is present in `avatar.inventory`.
2. Run `python scripts/inspect_state.py show-session <session_id> --entities` to check if `is_in_inventory: True` or `is_hidden: False` is set in `entity_states`.

### Scenario B: *"Item was combined or revealed but is not visible in-game"*
1. Run `python scripts/inspect_state.py show-adventure <template_id> --entities` to check its defined `item_type` (`CONSTRUCTABLE`, `PICKABLE`), `combination_ingredients`, or `reveal_rule`.
2. Run `python scripts/inspect_state.py show-session <session_id> --entities` to verify whether the session has overridden `is_hidden` to `False` and what `current_scene_id` it was moved to.

### Scenario C: *"Exit won't unlock / lock state mismatch"*
1. Run `python scripts/inspect_state.py show-adventure <template_id> --exits` to inspect `item_to_unlock`, `code_to_unlock`, and `rule_to_unlock`.
2. Run `python scripts/inspect_state.py show-session <session_id>` to check `exit_states` overrides.
