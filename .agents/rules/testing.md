---
description: Testing standards, AAA pattern, lifecycle verification, and mocking guidelines for TaleWeaver.
trigger:
  type: glob
  pattern: "tests/**/*.py"
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
5. **Game Loop Regressions**:
   * When altering gameplay intent-routing, guardrails, or pass logic, execute:
     ```bash
     pytest tests/test_game_loop.py
     ```
