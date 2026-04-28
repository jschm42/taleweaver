# Agent Guidelines & Best Practices

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
  * Network requests (especially LLM API calls to OpenAI/Anthropic/etc.) **must** be mocked in unit tests. We do not want to incur actual API costs or latencies when running the test suite!
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
