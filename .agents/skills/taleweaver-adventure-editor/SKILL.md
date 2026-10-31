---
name: taleweaver-adventure-editor
description: Modify an existing TaleWeaver adventure template directly in the database - add or change scenes, exits, NPCs, items, containers, scripts, the init script, quests and awards - via scripts/edit_adventure.py change sets. Use when the user asks you to add a scene, build a scripted puzzle, wire a trigger or otherwise edit an adventure that already exists in the DB. Not for writing a new adventure from scratch (use taleweaver-adventure-concept-creator) and not for images.
---

# TaleWeaver Adventure Editor (Change Sets)

Use this skill when the user wants an **existing adventure in the database** changed, for example
"add a crypt scene behind the hall with a moon-altar puzzle". You write a JSON **change set**, dry-run
it, fix what the validator reports, and commit it.

The CLI is [scripts/edit_adventure.py](../../../scripts/edit_adventure.py); the engine behind it is
[change_set.py](../../../backend/api/routes/adventures/editing/change_set.py).
Always run it as `poetry run python scripts/edit_adventure.py <command>` from the repo root
(PowerShell: set `$env:PYTHONPATH="."` first).

## How it works

- Every operation calls the **same endpoint code as the Adventure Editor** (ID checks, field
  limits, manifest sync, renames), as the adventure's owner. Nothing bypasses the editor rules.
- All operations of one change set run in **one transaction**. If any operation fails, nothing is
  kept. `apply` is a **dry run** (rollback) unless you pass `--commit`.
- The structural validator (the one behind the editor's Validation tab) runs before and after.
  Only the findings **your change set introduced** are printed. New `error` findings block the
  commit (`--allow-errors` overrides; do not use it without the user's consent).
- Script and guard fields are syntax-checked in the sandbox before they are stored.
- The DB can stay in use by the running server. Already running game sessions keep their manifest
  snapshot; **new games** see the changes.
- Images are not generated. New scenes/entities have no image; the `*_image_coverage` warnings are
  expected - the user adds images later in the editor.

## Workflow

1. **Find the adventure and read it.**
   ```bash
   poetry run python scripts/inspect_state.py list-adventures
   poetry run python scripts/edit_adventure.py summary "<id or title>"
   poetry run python scripts/edit_adventure.py export "<id>" --scene <SCENE_ID>
   ```
   `summary` gives the ID index (scenes, exits with `FROM->TO` routes, NPCs, objects, scripts,
   quests). `export --scene` gives one scene with its exits, neighbours and entities; `export`
   without `--scene` dumps everything (large - use `--out <file>` in your scratchpad and read parts).
2. **Save a backup** of what you are about to change: `export "<id>" --out <scratchpad>/before.json`.
3. **Design** the change. Reuse existing IDs, flags and script variables (check the init script in
   the full export). Scripting API: [docs/scripting_engine.md](../../../docs/scripting_engine.md).
4. **Write the change set** in your scratchpad (never in the repo). Long scripts go into separate
   `.py` files next to it and are referenced with `{"$file": "name.py"}`.
5. **Dry run**: `poetry run python scripts/edit_adventure.py apply <scratchpad>/changes.json`.
   Fix rejected operations and new findings, re-run until clean.
6. **Commit** with `--commit` once the dry run is clean and the task (or the user) calls for the
   change to be saved. Report what was added, the IDs, and any remaining warnings.
7. Optionally confirm with `summary` / `validate`.

## Change set format

```json
{
  "adventure": "<template id, origin_id or unique title substring>",
  "operations": [
    {"op": "create_scene", "scene_id": "CRYPT", "label": "Moon Crypt", "description": "..."}
  ]
}
```

Run `poetry run python scripts/edit_adventure.py ops [<op>]` for the exact field names. Unknown
fields are rejected (no silent typos).

| op | Purpose | Key fields |
|---|---|---|
| `create_scene` | New scene | `scene_id`, `label`, `description`, `decorative_objects` |
| `create_exit` | New exit | `from_scene_id`, `to_scene_id`, `label`, `exit_type` (`one_way`/`bidirectional`), `is_locked`, `lock_description`, `code_to_unlock`/`item_to_unlock`/`rule_to_unlock`, `ref` |
| `create_entity` | New NPC or object | `entity_id`, `entity_type` (`NPC`/`OBJECT`), `scene_id`, `name`, `description`, `item_type`, `is_portable`, `is_hidden`, `inventory`, `metadata_json`, ... |
| `update` | Change any editor field (incl. all trigger scripts) | `target_type` (`scene`/`exit`/`npc`/`object`/`protagonist`/`cover`), `target_id`, fields |
| `set_script` | Add/replace a global script | `id`, `name`, `trigger`, `target`, `code`, `priority`, `is_active` |
| `set_init_script` / `append_init_script` | Replace / extend the global init script (helpers, dialog handlers, dialogue trees) | `code` |
| `create_quest` / `create_award` | Quest / award | see `ops` |
| `set_start_scene` | Start scene | `scene_id` |
| `update_adventure` | Adventure settings (plot, rules, sequences, ...) | see `ops` |
| `delete_scene` / `delete_exit` / `delete_entity` / `delete_script` / `delete_quest` / `delete_award` | Remove | the one ID field |

### Field mapping of `update` (editor naming)

- **scene**: `name` sets the label; `description`, `decorative_objects`, `on_enter_scene_script/_text`,
  `on_leave_scene_script/_text`, `helpers_script`; `new_id` renames.
- **exit**: `name` sets the label, `description` sets the **lock description**, `locked`,
  `exit_type`, `code_to_unlock`/`item_to_unlock`/`rule_to_unlock`, `unlock_expression`,
  `on_open_exit_*`, `on_exit_used_*`, `on_unlock_success_*`, `on_unlock_failure_*`.
  A code/item/rule lock needs a lock description (set `description` in the same or an earlier update,
  or `lock_description` on `create_exit`).
- **object**: scripts such as `on_interact_*`, `on_pickup_*`, `on_read_*`, `unlock_expression`,
  container `on_unlock_success_*`, `on_items_added_script/_text`, `inventory` (container contents),
  switch fields, `is_hidden`, `reveal_rule`, `current_scene_id`, ...
- **npc**: `goal`, `character`, `inventory`, `on_interact_*`, `on_defeat_*`,
  `on_protagonist_enters_scene_*`, ...

### Referencing exits

Exits have generated IDs. In `update` (`target_type: "exit"`) and `delete_exit` use:
- `"$<ref>"` - an exit created earlier in the same change set with `"ref": "<ref>"`,
- `"FROM->TO"` - the unique existing exit on that route (see `summary`),
- or the plain exit ID.

Scripts address exits by route, e.g. `tw.exits.unlock('HALL', 'CRYPT')`.

## Worked example: an offering-altar puzzle behind a new scene

`changes.json`:
```json
{
  "adventure": "Moon Temple",
  "operations": [
    {"op": "create_scene", "scene_id": "MOON_CRYPT", "label": "Moon Crypt",
     "description": "A low crypt lit by pale light falling through a crack in the ceiling."},
    {"op": "create_exit", "ref": "crypt_gate", "from_scene_id": "HALL", "to_scene_id": "MOON_CRYPT",
     "label": "Crescent gate", "exit_type": "bidirectional", "is_locked": true,
     "lock_description": "A stone gate with a crescent-shaped seal. It does not move."},
    {"op": "create_entity", "entity_id": "MOON_ALTAR", "entity_type": "OBJECT", "item_type": "CONTAINER",
     "is_portable": false, "scene_id": "HALL", "name": "Moon Altar",
     "description": "A waist-high altar with a shallow, crescent-shaped bowl."},
    {"op": "create_entity", "entity_id": "SILVER_CRESCENT", "entity_type": "OBJECT", "scene_id": "MOON_CRYPT",
     "name": "Silver Crescent", "description": "A cold silver crescent, heavy for its size."},
    {"op": "update", "target_type": "object", "target_id": "MOON_ALTAR",
     "on_items_added_script": {"$file": "altar.py"}}
  ]
}
```

`altar.py` (next to `changes.json`; `added_item_ids` is provided by the container trigger):
```python
if 'SILVER_CRESCENT' in added_item_ids:
    tw.objects.destroy('SILVER_CRESCENT')
    tw.exits.unlock('HALL', 'MOON_CRYPT')
    tw.narrate("The crescent sinks into the altar. The gate's seal cracks open.")
else:
    for item_id in added_item_ids:
        tw.objects.take_from_container('MOON_ALTAR', item_id, to='player')
    tw.narrate("The altar stays cold. Your offering rolls back into your hands.")
```

(In a real adventure the key item would lie somewhere the player can reach before the gate.)

The dry run of this example reports `exit_locked_without_key` for the gate: the validator cannot see
that a script unlocks it. That warning is expected for script-unlocked exits; mention it to the user.

## Rules

- Dry run first, every time. Never `--commit` a change set you have not dry-run successfully.
- Keep change sets focused on the requested task; do not "fix" unrelated content on the way.
- Do not delete scenes, entities or scripts unless the user asked for it.
- Never edit the SQLite file or tables directly (SQL, `inspect_state.py`); the change set path keeps
  the manifest and the world tables in sync.
- All adventure content and scripts follow the adventure's language; code comments stay English.
- Puzzles must be enforceable by the engine (locks, guards, scripts) - see the
  [taleweaver-adventure-concept-creator](../taleweaver-adventure-concept-creator/SKILL.md) skill for puzzle design.
