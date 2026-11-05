# TaleWeaver Agent Guidelines

Welcome to the TaleWeaver workspace! This project uses the **Antigravity Customization System** with progressive disclosure rules, on-demand skills, and guidelines aligned with [Copilot Instructions](.github/copilot-instructions.md).

> [!IMPORTANT]
> **Language Rule**: All texts, UI labels, buttons, tooltips, documentation, comments, and agent communications must be kept strictly in **English** until the user explicitly specifies otherwise.

---

## Core Engineering Rules

1. **Clean Code & Modularity (No Monster Files)**:
   - Target module size is **< 400 lines** (max warning threshold: 600 lines).
   - **Never dump new features or monolithic code directly into existing oversized files** (`editor.py`, `gameplay_logic.py`, `templates.py`, `turn_guardrails.py`, `llm_router.py`, etc.).
   - Extract domain logic, database operations, or state handlers into separate service modules, subpackages, or helper classes.

2. **Control Flow Complexity & Flat Nesting**:
   - **Maximum nesting depth of 2.** Invert `if` checks and use **Guard Clauses / Early Returns** (`if not condition: return/raise`) to keep execution linear.
   - Combine simple conditions (`SIM102`) and replace long `if/elif` ladders with dispatch dictionaries, strategy handlers, or `match / case`.
   - Never write single-line compound statements (`if x: return y` - `E701`).

3. **Mandatory Linter & Security Protocol**:
   - Before completing ANY task, agents **must** run:
     ```bash
     poetry run ruff check <modified_files>
     poetry run ruff format --check <modified_files>
     ```
   - Ensure **zero errors** before concluding.
   - Never suppress complexity (`C901`, `PLR0912`, `PLR0915`) or security (`S`) warnings with `# noqa`; refactor the code instead.
   - Full check / fix command: `poetry run python scripts/lint.py --fix`.

4. **Documentation Stays in Sync (Mandatory)**:
   - Every change to user-facing behavior, syntax, settings, APIs, scripting functions or file formats **must update the affected documentation in the same task**. A task is not finished while its docs are outdated.
   - Check and update, where affected: `docs/` (e.g. `world-builder-syntax.md`, `world-builder-blueprint-manual.md`, `scripting_engine.md`), `README.md`, in-app help texts (info popovers, tooltips, placeholders), `.agents/skills/` and `.agents/rules/`.
   - Keep the examples in the docs working: a documented blueprint, script or command must match the current code. Run examples through the real validator where one exists (e.g. `backend.engine.blueprint.analyze_blueprint` for Story Idea blueprints).
   - New features get a docs entry. Removed or renamed features are removed or renamed in the docs too, with no stale references left behind.
   - Documentation is written **in English only**, regardless of the language used in the conversation.
   - In the final summary, list the docs that were updated, or state explicitly that none were affected.
   - **Scripting API & Editor Autocomplete Sync**: When scripting functions, methods, proxy properties or namespaces are added, modified or documented in `backend/engine/scripting/` or `docs/scripting_engine.md`, update both `docs/scripting_engine.md` and the frontend Script Editor autocomplete registry (`frontend/src/utils/twScriptApiDefinitions.ts`) in the same task to keep editor IntelliSense in sync.

5. **Engine Change Propagation (Mandatory)**:
   - A change to the engine (item types, entity or manifest fields, triggers/hooks, container/switch mechanics, sequence or progression logic, scripting API) is **not finished** until every place that generates, imports, validates or documents that feature is updated in the same task. Engine support alone is useless if the World-Builder cannot generate it.
   - **Find the consumers**: grep for an existing sibling of the feature (e.g. `on_items_added` when adding a container hook, `SWITCH` when adding an item type). Every hit outside the engine is a candidate that must be checked.
   - Work through this checklist and report each item in the final summary as *updated* or *not affected*:
     1. **World generation (LLM)**: the schemas in `backend/engine/world/` (`world_schemas.py`, `world_object_schema.py`, `switch_schemas.py`). They use `extra="forbid"`, so every field the manifest applier reads must exist there, or generation fails or loses the data. Also the prompts: `backend/core/prompts.py` (`WORLD_GENERATION_SYSTEM_PROMPT`), `backend/engine/world/world_scripting_prompt.py` (trigger catalogue, `TW_API_REFERENCE`, examples) and `backend/engine/world/world_prompt_builder.py`.
     2. **Blueprint / Story Idea**: `backend/engine/blueprint/` (`field_specs.py` keys, `parser.py` kind aliases and implied types, `converters.py`, `prompt.py`).
     3. **Manifest import/export**: `backend/engine/manifest_apply/` and `backend/engine/adventures/adventure_exporter.py`. An export/import round trip must keep the field.
     4. **Editor World-Builder / AI fix**: `backend/core/world_builder_prompts.py`, `backend/core/validators_prompts.py` (`FIX_PATCH_FIELD_RULES`) and `backend/api/routes/adventures/editing/ai_fix_*.py` (field allowlists such as `OBJECT_SCRIPT_FIELDS`).
     5. **Validators**: `backend/core/world_validation/` and `backend/core/script_validator.py` (every new `*_script` field must be syntax-checked).
     6. **Docs and skills**: `docs/world-builder-syntax.md`, `docs/world-builder-blueprint-manual.md`, `docs/scripting_engine.md` and the affected `.agents/skills/*/SKILL.md` (especially `taleweaver-adventure-concept-creator` and `taleweaver-adventure-editor`). Then rebuild the bundled skill docs with `poetry run python scripts/bundle_skill.py` and confirm `poetry run python scripts/bundle_skill.py --check` passes.
     7. **Editor autocomplete**: `frontend/src/utils/twScriptApiDefinitions.ts` for scripting API changes (see rule 4).
     8. **Tests**: add a test that the feature survives the whole path (generation schema → manifest applier, and blueprint key → parsed field), then run `tests/test_world_*.py`, `tests/test_world_builder_*.py` and the tests of the touched engine area.

---

## 1. Workspace Rules (`.agents/rules/`)

Specific project rules are located in `.agents/rules/` and triggered contextually to optimize context usage:

* [architecture.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/architecture.md) (`trigger: model_decision`) — Complete architectural breakdown of the Game Turn Loop (Pass 1, Pass 1.5, Pass 2), World Manifest (`adventure.adv`/`.adz`), state mutations, and scripting engine.
* [typescript.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/typescript.md) (`trigger: glob`, `**/*.ts, **/*.tsx`) — TypeScript code formatting, naming conventions, and strict typing.
* [python.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/python.md) (`trigger: glob`, `**/*.py`) — Python conventions, type hinting, error handling, and Alembic migrations.
* [testing.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/testing.md) (`trigger: glob`, `tests/**/*.py`) — AAA pattern, mocking requirements, and mandatory adventure lifecycle verification.
* [security.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/security.md) (`trigger: model_decision`) — Path traversal prevention (CWE-22) and secure filesystem handling.

---

## 2. On-Demand Skills (`.agents/skills/`)

* [taleweaver-inspector](file:///d:/DEV/repositories/git/taleweaver/.agents/skills/taleweaver-inspector/SKILL.md) — Inspect database state, session inventories, entity overrides, and manifests via `python scripts/inspect_state.py`.
* [taleweaver-adventure-concept-creator](file:///d:/DEV/repositories/git/taleweaver/.agents/skills/taleweaver-adventure-concept-creator/SKILL.md) — Generates structured adventure concepts using sequence, scene, and entity tags.
* [taleweaver-dev-tools](file:///d:/DEV/repositories/git/taleweaver/.agents/skills/taleweaver-dev-tools/SKILL.md) — Developer toolkit for admin credential resets, security keys, and thumbnail regeneration.
* [taleweaver-adventure-editor](file:///d:/DEV/repositories/git/taleweaver/.agents/skills/taleweaver-adventure-editor/SKILL.md) — Modify an existing adventure in the DB (scenes, exits, entities, scripts, init script) via JSON change sets and `python scripts/edit_adventure.py` (dry run by default).
* [taleweaver-telemetry](file:///d:/DEV/repositories/git/taleweaver/.agents/skills/taleweaver-telemetry/SKILL.md) — LLM telemetry, latency percentiles (p50/p90/p95), and token analysis.

---

## 3. Agent-Friendly Command Execution

To prevent terminal commands from hanging or consuming excessive tokens:

* **Avoid Terminal Pagers:** Always run Git commands with `--no-pager` (e.g. `git --no-pager diff`, `git --no-pager log -n 5`).
* **Prevent Token Flooding:** Never dump huge files directly to terminal output; use `head -n 50 <file>` or targeted views.
