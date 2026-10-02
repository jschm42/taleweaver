# TaleWeaver Agent Guidelines

Welcome to the TaleWeaver workspace! This project uses the **Antigravity Customization System** with progressive disclosure rules and on-demand skills.

> [!IMPORTANT]
> **Language Rule**: All texts, UI labels, buttons, tooltips, documentation, comments, and agent communications must be kept strictly in **English** until the user explicitly specifies otherwise.

---

## 1. Workspace Rules (`.agents/rules/`)

Specific project rules are located in `.agents/rules/` and triggered contextually to optimize context usage:

* [architecture.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/architecture.md) (`type: model_decision`) — Complete architectural breakdown of the Game Turn Loop (Pass 1, Pass 1.5, Pass 2), World Manifest (`adventure.adv`/`.adz`), state mutations, and scripting engine.
* [typescript.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/typescript.md) (`type: glob`, `**/*.{ts,tsx}`) — TypeScript code formatting, naming conventions, and strict typing.
* [python.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/python.md) (`type: glob`, `**/*.py`) — Python conventions, type hinting, error handling, and Alembic migrations.
* [testing.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/testing.md) (`type: glob`, `tests/**/*.py`) — AAA pattern, mocking requirements, and mandatory adventure lifecycle verification.
* [security.md](file:///d:/DEV/repositories/git/taleweaver/.agents/rules/security.md) (`type: model_decision`) — Path traversal prevention (CWE-22) and secure filesystem handling.

---

## 2. On-Demand Skills (`.agents/skills/`)

* [taleweaver-inspector](file:///d:/DEV/repositories/git/taleweaver/.agents/skills/taleweaver-inspector/SKILL.md) — Inspect database state, session inventories, entity overrides, and manifests via `python scripts/inspect_state.py`.
* [taleweaver-adventure-creator](file:///d:/DEV/repositories/git/taleweaver/.agents/skills/taleweaver-adventure-creator/SKILL.md) — Generates structured adventure concepts using sequence, scene, and entity tags.
* [taleweaver-dev-tools](file:///d:/DEV/repositories/git/taleweaver/.agents/skills/taleweaver-dev-tools/SKILL.md) — Developer toolkit for admin credential resets, security keys, and thumbnail regeneration.
* [taleweaver-telemetry](file:///d:/DEV/repositories/git/taleweaver/.agents/skills/taleweaver-telemetry/SKILL.md) — LLM telemetry, latency percentiles (p50/p90/p95), and token analysis.

---

## 3. Agent-Friendly Command Execution

To prevent terminal commands from hanging or consuming excessive tokens:

* **Avoid Terminal Pagers:** Always run Git commands with `--no-pager` (e.g. `git --no-pager diff`, `git --no-pager log -n 5`).
* **Prevent Token Flooding:** Never dump huge files directly to terminal output; use `head -n 50 <file>` or targeted views.
