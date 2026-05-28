# Copilot Instructions

This file contains the fundamental coding and architectural guidelines for all developers (AI-driven and human) working on **TaleWeaver**.

Please adhere to the following rules for all implementations to ensure high code quality.

---

## 1. Clean Code

* **Naming Conventions:**
  * Python: `PascalCase` for classes, `snake_case` for methods, variables, and modules. Constants in `UPPER_SNAKE_CASE`.
  * JavaScript/TypeScript: `PascalCase` for classes/components, `camelCase` for functions and variables.
  * Always use descriptive names (e.g., `calculate_damage` instead of `calc_dmg`).
* **Single Responsibility Principle (SRP):**
  * A function, class, or module should fulfill exactly one purpose. If a function becomes confusingly long, split it into smaller, testable units.
* **Typing (Type Hints):**
  * **Python:** Use type hinting consistently throughout the codebase (e.g., `str`, `int`, `dict`, `list`, `Optional`). This facilitates linting (with `mypy`) and makes the code more readable.
  * **Frontend:** Use JSDoc in JavaScript wherever possible, or ideally TypeScript for clear interfaces.
* **Error Handling:**
  * Handle errors where they occur.
  * In FastAPI, use `HTTPException` to return errors to the frontend with meaningful status codes (400, 404, 500) and clear messages.

---

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
