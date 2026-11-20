---
description: Testing standards, AAA pattern, lifecycle verification, and mocking guidelines for TaleWeaver.
trigger: glob
globs: "tests/**/*.py"
paths:
  - "tests/**/*.py"
---

# Testing Guidelines

1. **Test Structure**:
   * Structure tests following the **Arrange, Act, Assert** (AAA) pattern.
   * Write automated tests for all new endpoints and core mechanics (dice rolls, rule validations, pass logic).
2. **Frameworks**:
   * Use `pytest` for test suites.
   * For asynchronous routes, use `pytest-asyncio` and `httpx.AsyncClient`.
3. **Mocking Standards**:
   * **Never make real external network calls or LLM API calls in automated tests.** Always mock LLM endpoints to eliminate latency and cost.
   * Use isolated in-memory SQLite instances or mocked DB sessions for unit tests.
4. **Mandatory Lifecycle Tests**:
   * Whenever modifying `AdventureExporter`, `AdventureTemplateImporter`, or `WorldGenerator` data structures, run:
     ```bash
     pytest tests/test_adventure_lifecycle.py
     ```
   * Ensures adventures can be imported/exported between systems without data corruption.
5. **Suites & Affected Tests** ([docs/testing.md](../../docs/testing.md)):
   * The full suite takes 10–15 minutes. Run the affected tests with `poetry run python scripts/run_tests.py affected` (or `run <suite>`); the pre-push hook does the same.
   * Every new test file must be added to a suite in `tests/suites.toml` (`tests` globs); new backend modules outside the existing `sources` globs must be added to a suite's `sources`. `tests/test_run_tests_selection.py` enforces both.
6. **Game Loop Regressions**:
   * When altering gameplay intent-routing, guardrails, or pass logic, execute:
     ```bash
     pytest tests/test_game_loop.py
     ```
