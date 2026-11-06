---
description: Enforces Python coding conventions, type hinting, error handling, and Alembic migrations.
trigger: glob
globs: "**/*.py"
paths:
  - "**/*.py"
---

# Python Guidelines

1. **Naming Conventions**:
   * `PascalCase` for classes and Pydantic models.
   * `snake_case` for methods, functions, variables, and modules.
   * `UPPER_SNAKE_CASE` for module-level constants.
   * Always use clear, descriptive names.
2. **Type Annotations**:
   * Consistently use Python type hinting (`typing`, `Optional`, `list`, `dict`, `Union`, etc.) to support `mypy` and maintain readability.
3. **Single Responsibility**:
   * Keep functions, services, and routes focused on a single task. Split oversized functions into smaller, testable units.
   * Functions should not exceed 30–40 statements (`PLR0915`). If a function needs `# Step 1`, `# Step 2` comments, extract each step into a private helper (`_validate_prerequisites()`, `_apply_state_mutations()`).
   * Separate route definitions (HTTP mapping, input validation) from business logic, database queries and external service calls.
4. **Error Handling**:
   * Handle errors where they arise. Never use empty catch blocks (`except Exception: pass` / `S110`); always log or handle the exception.
   * In FastAPI endpoints, raise `HTTPException` with meaningful HTTP status codes (400, 404, 500) and user-safe messages.
5. **Database & Migrations**:
   * Every schema change (new tables, columns, or types) **must** have an Alembic migration script.
   * Use `alembic revision --autogenerate -m "description"` and verify with `alembic upgrade head`.
   * Never execute manual `ALTER TABLE` statements in application startup code.
6. **Comments & Docstrings**:
   * The "Why" and "What" matter more than the "How"; good naming should reveal the "How".
   * Use docstrings (`"""..."""`) at module, class and function level (Google or Sphinx style).
   * Use inline comments sparingly: only for complex algorithms, surprising fixes or obscure workarounds.
   * Mark pending work as `TODO: [Short Description]` and track it in the issue tracker.
