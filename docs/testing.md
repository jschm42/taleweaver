# Running the Tests

The full Python suite has about 2,400 tests and takes 10 to 15 minutes. Most of that is the
per-test setup (in-memory database, app client), so the time grows with the number of tests
rather than with a few slow ones. For day-to-day work, run a suite or only the tests your
change can affect: `scripts/run_tests.py`.

```bash
poetry run python scripts/run_tests.py list                  # suites, and test files in no suite
poetry run python scripts/run_tests.py run turn npc          # one or more suites
poetry run python scripts/run_tests.py run all               # the full suite
poetry run python scripts/run_tests.py affected              # tests for your branch's changes
poetry run python scripts/run_tests.py affected --staged     # tests for the staged changes
poetry run python scripts/run_tests.py affected --dry-run    # only print the selection
poetry run python scripts/run_tests.py run core -- -x        # pytest options after `--`
```

## Suites

Suites are defined in [`tests/suites.toml`](../tests/suites.toml). Each suite has:

- `tests`: file-name globs inside `tests/`. A file may sit in several suites.
- `sources`: repo-relative path globs (`*` also matches `/`). A change to a matching file
  selects the whole suite.

| Suite | Covers |
| --- | --- |
| `core` | The critical paths (game loop, guardrails, security, lifecycle, manifest round trip); also the fallback for changes no suite covers |
| `security` | Path security, session ownership, auth, keys, script sandbox |
| `turn` | Turn pipeline: Pass 1/1.5/2, guardrails, narration, quests, clock |
| `items` | Items, containers, switches, exits, crafting |
| `npc` | NPCs, companions, memory, conversations, talents |
| `combat` | Combat rules, encounters, party in combat |
| `scripting` | Scripting engine, `tw` API, triggers, sequence scripts |
| `world` | World generation, blueprints, manifests, validation, AI fix |
| `editor` | Adventure editor routes |
| `adventures` | Library, import/export, sessions, saves, maps |
| `agent` | Play-Agent |
| `llm` | LLM providers, routing, model tests, server settings, setup |
| `media` | Images, ComfyUI, audio, TTS, voices, STT |
| `tooling` | Developer scripts |

**A new test file must be added to a suite.** `tests/test_run_tests_selection.py` fails
while a test file is in no suite or a backend module is in no suite's `sources` area
(a small remainder is tolerated).

## What `affected` selects

| Change | Runs |
| --- | --- |
| A test file | That file |
| A source file (`backend/`, `scripts/`, `alembic/`) | The suites whose `sources` match it (else `core`), the tests that import it directly, and the tests whose name contains the module name (`guardrails/handovers.py` → `test_item_handovers.py`) |
| `tests/conftest.py`, test helpers, `pytest.ini`, `pyproject.toml`, `poetry.lock` | The full suite |
| `frontend/` | The frontend tests (`npm --prefix frontend test`) |
| Docs and other files | Nothing |

The import check only follows **direct** imports. Following them transitively would select
most of the suite, because the turn pipeline and `backend.main` import nearly everything.
The suites cover the area around a change instead. The selection is a fast check before
opening a pull request, not a replacement for the full suite.

## CI: the gate before a merge

Every pull request into `main` runs [`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

| Job | Runs |
| --- | --- |
| `backend-lint-test` | Ruff on the changed files, mypy (informational), the full pytest suite |
| `frontend-test` | `npm ci`, `npm test`, `npm run build` |

A failing job fails the check. A branch ruleset on `main` (Settings → Rules → Rulesets)
makes both jobs required status checks, so a pull request can only be merged when they
pass.

## Git hooks

`setup.ps1` / `setup.sh` link the hooks; with a manual setup run:

```bash
git config core.hooksPath .githooks
```

- `pre-commit` runs Ruff on the staged Python files.
- `pre-push` is **opt-in**: it runs `affected` for the pushed commits and blocks the push on
  failures only when `TW_PRE_PUSH_TESTS=1` is set. Without it the hook does nothing, because
  CI checks every pull request anyway.
