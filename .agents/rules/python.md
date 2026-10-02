---
description: Enforces Python coding conventions, type hinting, error handling, and Alembic migrations.
trigger:
  type: glob
  pattern: "**/*.py"
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
4. **Error Handling**:
   * Handle errors where they arise.
   * In FastAPI endpoints, raise `HTTPException` with meaningful HTTP status codes (400, 404, 500) and user-safe messages.
5. **Database & Migrations**:
   * Every schema change (new tables, columns, or types) **must** have an Alembic migration script.
   * Use `alembic revision --autogenerate -m "description"` and verify with `alembic upgrade head`.
   * Never execute manual `ALTER TABLE` statements in application startup code.
