---
description: Enforces naming conventions, strict typing, and best practices for TypeScript files.
trigger: glob
globs: "**/*.ts, **/*.tsx"
---

# TypeScript Guidelines

1. Always use `const` instead of `let`, unless the variable must be reassigned.
2. Explicitly type all function return values.
3. Use `camelCase` for variables and functions, and `PascalCase` for interfaces and types.
4. Avoid `any` — use precise types or generics.
5. Keep components and composables/hooks modular, cleanly typed, and reusable.
