---
name: taleweaver-commit-message
description: Write a TaleWeaver commit message (Conventional Commits, project scopes) for the current staged or working-tree changes. Use when asked for a commit message, before committing, or to split mixed changes into several commits.
---

# TaleWeaver Commit Message

Writes a commit message that explains **why** a change was made and **what changed in
behavior**, in the style of this repository. It does not commit unless the user asks.

---

## 1. Collect the Changes

Run these (never with a pager, never dump whole diffs at once):

```bash
git --no-pager status --short
git --no-pager diff --cached --stat          # staged changes
git --no-pager diff --stat                   # unstaged changes
git --no-pager log --format=%s -n 20         # recent subjects, for style and scopes
```

* **Something staged** → the message covers the staged changes only. Mention unstaged or
  untracked files that look related, so the user can add them.
* **Nothing staged** → describe the working tree and say so; suggest which files to stage.
* Read the actual diff per file, largest first, limited in size
  (`git --no-pager diff --cached -- <file> | head -n 200`). New files: read the top of the
  file (module docstring) instead of the whole content.
* Look for signals that must appear in the message:
  * new files under `alembic/versions/` → a migration (name what it does to the data),
  * changed request/response models or routes in `backend/api/routes/` → API change,
  * `backend/engine/scripting/` or `docs/scripting_engine.md` → scripting API change,
  * `docs/`, `README.md`, `.claude/rules/`, `.claude/skills/` → docs updated,
  * removed or renamed modules, settings keys, manifest fields → possible breaking change.

## 2. One Commit or Several?

A commit should hold **one** logical change. If the diff mixes unrelated work (e.g. a bug fix
plus a new feature, or a refactor plus a UI redesign), propose separate commits: list each
message with the files that belong to it. Changes that only make sense together (a feature
with its migration, tests and docs) stay in one commit.

## 3. Subject Line

```
<type>(<scope>): <summary>
```

* **type**: `feat` (new behavior), `fix` (bug fix), `refactor` (no behavior change), `perf`,
  `docs`, `test`, `build`, `ci`, `chore`.
* **scope** (optional, one word, from the touched area): e.g. `engine`, `scripting`, `editor`,
  `gameplay`, `tts`, `stt`, `settings`, `profile`, `portal`, `world-builder`, `skills`, `api`,
  `db`. Prefer scopes already used in `git log`. Omit it when the change spans many areas.
* **summary**: imperative, lower case, no trailing period, at most 72 characters. Name the
  effect, not the files: `fix(tts): keep auto-speak preferences across settings saves`,
  not `fix: update tts_api.py`.

## 4. Body

Leave one blank line after the subject. Wrap at 72 characters. In English.

1. **Why**: the problem or goal in one or two sentences (what was wrong or missing).
2. **What changed**: the behavior a player, admin or developer notices. Group related points;
   bullet points are fine for three or more. Do not list every file.
3. **Notes that reviewers need**: migrations (what happens to existing data, downgrade
   support), changed endpoints or response shapes, new settings, follow-ups left open.

Skip the body only for trivial changes (typo, formatting, single-line fix that the subject
fully explains).

## 5. Footers

* `BREAKING CHANGE: <what breaks and how to migrate>` when an API response, file format,
  manifest field, setting or scripting function changes incompatibly.
* `Refs #<n>` / `Closes #<n>` when the user names an issue or PR.
* Attribution trailers (e.g. `Co-Authored-By:`) only as the agent's own harness or the user
  instructs. Never invent them.

## 6. Before Committing (only when the user asks to commit)

* The pre-commit hook (`.githooks/pre-commit`) runs Ruff on staged Python files. Never skip
  it with `--no-verify`; fix the findings instead.
* Pass the message with a heredoc or `-F -` so newlines and quotes survive:
  `git commit -F - <<'EOF' ... EOF`.
* Commit on a feature branch, not directly on `main`, unless the user says otherwise.

---

## Examples

Feature with migration and API change:

```
feat(settings): store server-wide settings once in server_settings

API keys, model settings and catalogs were copied into every user row,
so users created after the last admin save had no keys at all.

- New single-row table server_settings, managed by admins.
- Users read the values at runtime; nothing is written back per user.
- Admins can be demoted or deleted without losing the settings.

Migration b8d4f0a2c6e1 copies the values from the oldest admin and
drops the per-user columns; downgrade restores the copies.

BREAKING CHANGE: User no longer has settings columns; seed
ServerSettings in tests (tests/server_settings_helpers.py).
```

Small fix:

```
fix(profile): show the last played date in session cards
```

Refactor without behavior change:

```
refactor(gameplay): extract the turn clock into turn_pass_flow

gameplay_logic.py was over 2000 lines. The clock handling moves into
its own module; behavior and tests are unchanged.
```
