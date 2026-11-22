---
name: taleweaver-adventure-builder
description: Build a complete, playable TaleWeaver adventure (manifest, scripts, validation, and visuals) from a blueprint or story idea directly against a running TaleWeaver server via scripts/adventure_api.py. Use when the user wants you to generate and import a full adventure end-to-end without the interactive generation wizard. Not for editing an already-imported adventure (use taleweaver-adventure-editor) or writing only a blueprint (use taleweaver-adventure-concept-creator).
---

# TaleWeaver Adventure Builder (Server API)

Use this skill when the user gives you a blueprint (or story idea) and wants a **complete, immediately playable TaleWeaver adventure** imported into a running TaleWeaver server—including scenes, exits, NPCs, items, quests, awards, `init_script` / trigger scripts, validation, and generated visuals.

The CLI client is [scripts/adventure_api.py](../../../scripts/adventure_api.py). Run it with:
`poetry run python scripts/adventure_api.py <command>`

## Prerequisites

The target TaleWeaver server must be running, with credentials provided via environment variables or `.env` in the repo root (never hardcode passwords in tracked files):
- `TW_API_URL` (default `http://localhost:8000`)
- `TW_USERNAME` and `TW_PASSWORD` (or `TW_TOKEN` for a pre-fetched Bearer JWT)

## Workflow

1. **Validate the blueprint (if tagged).**
   Save the user's blueprint in your scratchpad and check it via the server:
   ```bash
   poetry run python scripts/adventure_api.py validate-blueprint <scratchpad>/blueprint.txt
   ```
   Fix any syntax or reference errors before expanding it.

2. **Expand the blueprint into a complete `adventure.adv` manifest (Format `1.5.0`).**
   Read [docs/specs/adventure_format.md](../../../docs/specs/adventure_format.md) and [docs/scripting_engine.md](../../../docs/scripting_engine.md) when unsure about field names or `tw.*` APIs.
   Key manifest rules:
   - `"format": "TaleWeaver"` and `"version": "1.5.0"` **must** be the first two keys of the root JSON object.
   - Include `adventure`, `protagonist`, `sections`, `scenes`, `npcs`, `objects`, `exits`, `quests`, `awards`, `scripts`, and `init_script`.
   - Respect sandbox limits in all scripts: no `_`-prefixed function names, max 8 options in `tw.dialog.choose(...)`, and valid `tw.*` calls only.
   - Provide rich `description` and `appearance` fields on scenes, protagonist, NPCs, and non-recipe objects so server-side visual generation produces coherent images.

3. **Import and run structural validation.**
   ```bash
   poetry run python scripts/adventure_api.py import <scratchpad>/adventure.adv --validate
   ```
   - `import` calls `POST /api/adventures/import` and prints `Imported adventure_id=<template_id>`.
   - Note: `/api/adventures/import` uses `overwrite=False` (returns `409 Conflict` if an adventure with the same title already exists for this user).

4. **Fix any validation findings.**
   If `validate` reports errors or unwanted warnings, patch the adventure via `scripts/edit_adventure.py` (see `taleweaver-adventure-editor`) or the editor REST endpoints, then re-verify:
   ```bash
   poetry run python scripts/adventure_api.py validate <template_id>
   ```
   Optionally run `validate <template_id> --include-ai` for an AI logic pass.

5. **Generate visuals through the server.**
   Use the server's configured T2I provider, styles, tones, aspect ratios, and thumbnail pipeline:
   ```bash
   poetry run python scripts/adventure_api.py visuals <template_id> --only-missing
   ```
   - Automatically covers `cover`, `protagonist`, `scenes`, `npcs`, and `objects` (skipping `CONSTRUCTABLE` recipes).
   - If you generated custom images externally (e.g., via `comfy-mcp`), upload them per target instead:
     ```bash
     poetry run python scripts/adventure_api.py upload-visual <template_id> <target_type> <target_id> <image_file>
     ```

6. **Final check & report.**
   Run `poetry run python scripts/adventure_api.py validate <template_id>` after all edits and visual generation, then report the `template_id`, title, asset coverage, and any remaining warnings to the user.
