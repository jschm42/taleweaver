# Copilot Instructions

This file contains the fundamental coding and architectural guidelines for all developers (AI-driven and human) working on **TaleWeaver**.

Please adhere to the following rules for all implementations to ensure high code quality.

> [!IMPORTANT]
> **Language Rule**: All texts, UI labels, buttons, tooltips, documentation, comments, and agent communications must be kept strictly in **English** until the user explicitly specifies otherwise.

---

## 1. Clean Code, Architecture & Modularity

* **Naming Conventions:**
  * Python: `PascalCase` for classes, `snake_case` for methods, variables, and modules. Constants in `UPPER_SNAKE_CASE`.
  * JavaScript/TypeScript: `PascalCase` for classes/components, `camelCase` for functions and variables.
  * Always use descriptive names (e.g., `calculate_damage` instead of `calc_dmg`).

* **Module & File Size Thresholds (Combating Monster Files):**
  * **Target Size:** Python modules should ideally remain under **400 lines**, with a hard warning threshold at **600 lines**.
  * **Legacy Monster Files Policy:** Certain existing modules have grown excessively large (e.g., `backend/api/routes/adventures/editor.py`, `gameplay_logic.py`, `templates.py`, `turn_guardrails.py`, `turn_combat.py`, `backend/core/llm_router.py`).
    * **Strict Rule:** **Do NOT add new monolithic blocks or extensive methods directly into these files!**
    * When introducing new features, refactoring, or extending functionality in these domains, extract logic into dedicated sub-packages, service classes, or handler modules (e.g., `backend/api/routes/adventures/services/`, `backend/engine/handlers/`).
    * Separate route definitions (HTTP mapping, input validation) from business logic, database queries, and external service calls.

* **Control Flow & Anti-Nesting Guidelines (No Deep `if` Pyramids):**
  * **Maximum Nesting Depth:** Strict limit of **2 nesting levels** (at most 3 in rare algorithmic scenarios). Deeply nested code is a primary source of bugs and poor maintainability.
  * **Guard Clauses / Early Returns:** Always invert conditions and exit early rather than wrapping the rest of the function in an indented block.
    * *Anti-Pattern (Avoid):*
      ```python
      if session is not None:
          if session.is_active:
              if user.id == session.user_id:
                  # 60 lines of logic indented 4 times
      ```
    * *Clean Code (Required):*
      ```python
      if session is None:
          raise HTTPException(status_code=404, detail="Session not found")
      if not session.is_active:
          raise HTTPException(status_code=400, detail="Session is inactive")
      if user.id != session.user_id:
          raise HTTPException(status_code=403, detail="Forbidden")
      # Flat, linear execution follows...
      ```
  * **Eliminate Redundant Nesting (`SIM102`):** Combine contiguous checks using boolean operators (`if a and b:` instead of `if a: if b:`).
  * **Dispatch / Strategy Pattern Over Long `if-elif` Chains:** Replace sprawling `if/elif/elif/...` ladders (e.g. for entity types, action triggers, event types) with dictionary dispatch tables, handler classes, or Python 3.10 `match / case`.
  * **No Single-Line Compound Statements (`E701`):** Never write statements like `if not avatar: return None` on a single line. Always write clear, multi-line conditionals.
  * **Function Size & Statement Limits:** Functions should not exceed 30–40 statements (`PLR0915`). If a function requires comments like `# Step 1`, `# Step 2`, extract each step into a private helper function (`_validate_prerequisites()`, `_apply_state_mutations()`).

* **Typing (Type Hints):**
  * **Python:** Use type hinting consistently throughout the codebase (e.g., `str`, `int`, `dict`, `list`, `Optional`). This facilitates linting (with `mypy`) and makes the code self-documenting.
  * **Frontend:** Use JSDoc in JavaScript wherever possible, or TypeScript for clear interfaces.

* **Error Handling & Exception Hygiene:**
  * Handle errors where they occur. Never use empty catch blocks (`except Exception: pass` / `S110`); always log or handle exceptions meaningfully.
  * In FastAPI, use `HTTPException` with explicit status codes (400, 401, 403, 404, 500) and informative error messages.

---

## 1.1 Mandatory Linter & Quality Execution Protocol

To ensure codebase quality, security, and prevent regression:

* **Automated Pre-Commit Hooks:** A Git pre-commit hook is active in `.githooks/pre-commit`. It automatically runs Ruff on all staged Python files before each commit.
* **Developer / Agent Lint Command:**
  * Quick check: `poetry run python scripts/lint.py` (or `poetry run ruff check <paths>`)
  * Auto-fix & format: `poetry run python scripts/lint.py --fix` (or `poetry run ruff check --fix <paths>` and `poetry run ruff format <paths>`)
  * Pre-commit staged check: `poetry run python scripts/lint.py --staged`
* **Agent Requirement:** Before marking any implementation task complete, AI agents **must**:
  1. Run `poetry run ruff check <modified_paths>` and verify that 0 errors are reported.
  2. Run `poetry run ruff format --check <modified_paths>` to ensure clean formatting.
  3. Never silence complexity (`C901`, `PLR0912`, `PLR0915`), nested blocks, or security (`S`) warnings with `# noqa`. Resolve the underlying structure instead.

## 2. Testing

* **Principles:**
  * Every new endpoint and core function (e.g., the D20 dice roll or evaluating the LLM result) must be covered by automated unit tests.
  * Structure tests according to the **Arrange, Act, Assert** (AAA) pattern.
* **Tools & Frameworks:**
  * **Backend:** Use `pytest`. For asynchronous routes, use `pytest-asyncio` and the `AsyncClient` from `httpx`.
* **Mocking:**
  * Network requests (especially LLM API calls to OpenAI/Anthropic/etc.) **must** be mocked in unit tests. We do not want to incur actual API costs or latencies when running the test suite.
  * Database access in isolated tests should also be mocked or use a dedicated in-memory SQLite test database.
* **Mandatory Lifecycle Tests:**
  * Whenever you modify `AdventureExporter`, `AdventureTemplateImporter`, or the `WorldGenerator` data mapping, you **must** run the lifecycle tests: `pytest tests/test_adventure_lifecycle.py`.
  * These tests ensure that adventures can be correctly moved between systems without data loss (especially protagonist and assets).

---

## 3. Comments & Documentation

* **Code Documentation (Docstrings):**
  * The "Why" and "What" are more important than the "How". The code itself should reveal the "How" through good naming.
  * In Python, use docstrings (`"""..."""`) at the module, class, and function levels, ideally in Google or Sphinx format.
* **Inline Comments:**
  * Use them sparingly. They only make sense if a specific algorithm is extremely complex, a surprising fix was implemented, or an obscure workaround needs documentation.
* **TODOs:**
  * Use `TODO: [Short Description]` for pending tasks in the code. These tasks should be tracked in issue trackers.
* **Project Documentation Stays in Sync (Mandatory):**
  * Every change to user-facing behavior, syntax, settings, APIs, scripting functions or file formats must update the affected documentation in the same change. This covers `docs/`, `README.md`, in-app help texts (popovers, tooltips, placeholders), `.agents/skills/` and `.agents/rules/`.
  * Documented examples (blueprints, scripts, commands) must match the current code. Validate them with the real parser or validator where one exists.
  * New features get a docs entry. Removed or renamed features leave no stale references behind.
  * Documentation is written in **English only**, regardless of the conversation language.

---

## 4. Workflows & Diagrams

To understand the internal processes of TaleWeaver, refer to the following Mermaid diagrams:

* **Adventure Generation:** [adventure_generation.mermaid](docs/diagrams/adventure_generation.mermaid) | [Activity Diagram](docs/diagrams/adventure_generation_activity.mermaid) - Detailed workflow of how worlds are created.
* **Adventure Import/Export:** [adventure_import.mermaid](docs/diagrams/adventure_import.mermaid) | [adventure_export.mermaid](docs/diagrams/adventure_export.mermaid) - Logic for .adz and .adv portability.
* **Game Session Loop:** [game_session_loop.mermaid](docs/diagrams/game_session_loop.mermaid) | [Activity Diagram](docs/diagrams/game_session_loop_activity.mermaid) - Detailed flow of a single chat turn (user input to GM response).
* **Data Formats:** [Adventure Format Specification](docs/specs/adventure_format.md) - Standardized structure for `.adv` and `.adz` files.

---

## 5. Database & Migrations

* **Alembic Migrations:**
  * For **any** change to the database schema (adding columns, creating tables, changing types), a corresponding Alembic migration script **must** be created.
  * Use `alembic revision --autogenerate -m "description"` to generate the script and review it before applying.
  * Avoid manual migrations via `ALTER TABLE` in the application code (e.g., in `database.py`), unless there is a very specific technical reason.
  * Always verify the migration by running `alembic upgrade head`.

---

## 6. Security & Input Validation (Path Traversal Prevention)

* **Preventing "Uncontrolled data used in path expression" (CWE-22):**
  * When handling file operations, never directly concatenate or trust user-supplied input (like usernames, template IDs, or filenames) to construct file paths.
  * **Mandatory Central Helper:** For new code and refactors, use `backend.utils.path_security` (`ensure_within_data_dir`, `safe_data_path`, `data_url_to_local_path`, `local_path_to_data_url`) instead of ad-hoc path validation.
  * **No Direct Sink Calls With Untrusted Paths:** `open`, `shutil.copy*`, `os.makedirs`, `os.remove`, and similar filesystem sinks must only receive paths returned by validated helper functions.
  * **Use Path Verification Helpers:** Any resolved target path must be verified to reside within the intended base directory (e.g., `settings.DATA_DIR`).
    * Use `os.path.realpath` and `os.path.commonpath` to ensure the target remains inside the base directory, including symlink-safe resolution:
      ```python
      def _ensure_within_data_dir(path: str) -> str:
          data_root = os.path.realpath(settings.DATA_DIR)
          resolved = os.path.realpath(path)
          try:
              if os.path.commonpath([resolved, data_root]) != data_root:
                  raise ValueError("Resolved path escapes DATA_DIR.")
          except ValueError as exc:
              raise ValueError("Invalid path: cannot resolve against DATA_DIR.") from exc
          return resolved
      ```
  * **Input Sanitization & Validation:**
    * Use alphanumeric regex validation for any variable path components (e.g. `re.match(r"^[A-Za-z0-9_-]{1,128}$", template_id)`).
    * Strip path separators (`/`, `\`) or traversal sequences (`..`) from parameters.
    * Use `os.path.basename` to extract only the filename when referencing uploaded files, or generate a random/UUID filename (e.g., `f"{uuid.uuid4()}.{ext}"`) rather than trusting the original name.
  * **Agent Compliance Rule (Required):** If an agent touches path-building/file-write code, it must run and pass the security-focused tests (`tests/test_security_hardening.py`) and include a short note in the PR/summary stating which helper functions were used.

---

## 7. Gameplay Guardrails (Scene Visibility & Language-Agnostic Intents)

* **No Language-Keyword Gating For Core Mechanics:**
  * Do **not** gate gameplay-critical decisions (inspect/search target validation, scene transition, generation confirmation/retry) behind hardcoded language keywords.
  * Prefer intent classification (LLM or parser abstraction) that works across languages and phrasing variants.
* **Server-Side Visibility Authority (Required):**
  * The backend must be the final authority on what the GM can act on.
  * For inspect/search, only allow targets that are currently visible/accessible: current scene entities, protagonist inventory, and inventory of NPCs present in the current scene.
  * If a target is outside this scope, block the action before downstream GM/mechanics processing.
* **Fail-Safe Behavior:**
  * If intent extraction is uncertain or unavailable, fall back to deterministic safeguards and prefer the safe outcome (no state-advancing side effects).
* **Systematic State-Based Enforcements (Pass 1.5) Over Text Parsing:**
  * Do **not** try to pre-parse or guess which entity (such as a container or switch) the player is interacting with by searching for their exact name/ID in the raw user message text.
  * Instead, systematically inspect any state updates requested by the LLM in Pass 1 (e.g., `update.locked = False` for containers, or `update.switch_state` changes for switches).
  * Validate these updates directly against the DB rules/gates (required items, codes, story flags) and the player's inventory/state. Revert any illegal changes back to their pre-turn state, and pass these revert notifications to the Pass 2 narration prompt as `rule_violations` to ensure the narration describes the failure accurately.
* **Agent Compliance Rule (Required):**
  * If an agent changes gameplay intent-routing or visibility guard logic, it must run targeted regression tests in `tests/test_game_loop.py` that cover:
    * blocking off-scene inspect/search exploits,
    * not blocking unrelated mention-only text,
    * preserving hypothetical (non-explicit) scene-transition behavior,
    * preserving generator confirmation/retry behavior.

---

## 8. Agent-Friendly Command Execution (Avoiding Terminal Hangs)

To prevent terminal commands executed by AI agents (like the Gemini agent in Antigravity IDE) from hanging or consuming excessive resources, adhere to these guidelines:

* **Avoid Terminal Pagers (Standard Trap):**
  * When running interactive commands that paginate output (like `git diff` or `git log`), Git automatically invokes `less`, which blocks the terminal and waits for human input (like spacebar or `q`). Because the agent is not a human, it will hang indefinitely on `"Working"`.
  * **Solution:** Always run Git commands with the `--no-pager` flag, or limit output explicitly.
    * Use: `git --no-pager diff <file>` instead of `git diff <file>`.
    * Use: `git --no-pager log -n 5` instead of `git log`.
  * *Tip:* You can also permanently disable the pager for the local repository by running `git config core.pager ''`.
* **Prevent Token Flooding:**
  * Avoid spitting out huge amounts of raw text into the console (e.g., dumping a massive JSON file or a huge diff). The agent has to read, process, and compress this context, which consumes massive amounts of computation time and tokens, slowing down response times.
  * **Solution:** Limit commands to only the necessary output.
    * Use: `head -n 50 <file>` instead of `cat <file>` for large files.
* **Use IDE Features Instead of Terminal Output:**
  * Instead of asking the agent to read raw terminal diffs, leverage Antigravity's native visual "Review Changes" area in the agent panel to review changes visually.

### Quick Command Guide:

| Command (The Trap) | Agent-Friendly Alternative | Reason |
| :--- | :--- | :--- |
| `git diff <file>` | `git --no-pager diff <file>` | Prevents the terminal from blocking/waiting for key presses. |
| `git log` | `git --no-pager log -n 5` | Bypasses the pager and prevents endless output. |
| `cat huge_file.json` | `head -n 50 huge_file.json` | Protects the agent from immediate token overload. |

## 9. Game Turn Loop & Mechanics Pipeline

TaleWeaver processes each gameplay turn through a structured pipeline in [GameTurnManager](file:///c:/Users/jschmitz/DEV/git-repositories/taleweaver/backend/api/routes/adventures/gameplay_logic.py):

* **Pass 1 (Mechanics Check)**:
  * The LLM mechanics model processes the user prompt and suggests state changes (e.g. changing exit locks, switch states, opening containers, updating inventories).
* **Pass 1.5 (Rule Validation & Reversion)**:
  * Database state updates requested by the LLM are evaluated against game configuration rules/gates (required items, codes, story flags) and player state.
  * If a state update violates a rule (e.g. unlocking a chest without referencing the key item in the chat message, or flipping a switch without having the necessary tool), the update is **reverted** to its pre-turn state.
  * Reverted violations are gathered into a `rule_violations` list.
* **Pass 2 (Narration Generation)**:
  * If `rule_violations` list is not empty, the system overrides `game_event.narrative_description` with the violations list.
  * This overrides the LLM-generated narrative description, forcing the narration LLM to narrate a failure instead of hallucinating a successful action.
* **Key Concepts**:
  * **WorldEntity**: Objects or NPCs in the game. Objects can be `CONTAINER`, `SWITCH`, etc., and have specific lock metadata.
  * **WorldExit**: A connection between scenes (directional or bidirectional).
  * **Exit Resolution**: Always resolve session-scoped exits by preferring the session row (via mapping from_scene_id/to_scene_id) over the template-scoped exit to respect dynamic in-game unlocking.
  * **Key Item Mentions**: Enforced state-based validation checks to verify if key items or codes are mentioned or utilized in the player's turn to prevent automatic/implicit unlocking. The game is designed to be language-independent.
  * **Dynamic Item Generation**: Spontaneous item generation is permanently disabled. Items spawned or added must exist in the adventure's predefined databases.

---

## 10. Backend Data Inspection & Debugging Guidelines

When debugging game mechanics, missing items, entity visibility issues, scene transitions, or adventure configurations:
* **Mandatory CLI Inspector:** Use `python scripts/inspect_state.py` (or refer to the `taleweaver-inspector` skill) instead of writing one-off ad-hoc database queries or raw SQL scripts.
* **Inspecting Adventures & Manifests:**
  * `python scripts/inspect_state.py list-adventures` — List all templates with versions, languages, and statuses.
  * `python scripts/inspect_state.py show-adventure "<title_or_id>" [--entities|--scenes|--exits|--manifest]` — Detailed breakdown of scenes, entities, combination ingredients, reveal/unlock rules, and exits.
  * `python scripts/inspect_state.py dump-manifest "<title_or_id>"` — Dump raw original adventure manifest JSON.
* **Inspecting Active Game Sessions:**
  * `python scripts/inspect_state.py list-sessions [--limit 10]` — List recent game sessions and their current scenes.
  * `python scripts/inspect_state.py show-session <session_id> [--inventory|--entities|--hidden-only]` — Deep-inspect the runtime state (Avatar inventory, stats, current scene, entity state overrides, quest progress, and world memories).
* **Agent Rule:** Always inspect the actual database state and manifest before altering turn-pipeline logic or assuming state behavior.
* **Modifying Adventures in the DB:** Use `python scripts/edit_adventure.py` (see the `taleweaver-adventure-editor` skill): `summary` / `export --scene` to read, then `apply <changes.json>` (dry run) and `apply ... --commit`. Change sets run through the editor endpoints in one transaction; never edit adventure rows with raw SQL.
