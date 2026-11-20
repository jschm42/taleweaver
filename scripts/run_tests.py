"""Run TaleWeaver tests by suite or only the tests a change can affect.

Usage:
    python scripts/run_tests.py list
    python scripts/run_tests.py run turn npc [-- -x]
    python scripts/run_tests.py run all
    python scripts/run_tests.py affected [--staged | --base REF] [--dry-run] [-- -x]
    python scripts/run_tests.py pre-push        # used by .githooks/pre-push (reads stdin)

Suites are defined in ``tests/suites.toml``. ``affected`` (and the pre-push hook) picks:
changed test files; for a changed source file the suites whose ``sources`` match it
(else ``core``), the tests importing it directly (``scripts/import_graph.py``) and the
tests named after it; the full suite for shared test infrastructure; the frontend tests
for ``frontend/`` changes. The full suite stays the reference (``run all``).
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from import_graph import ImportGraph, module_name  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUITES_FILE = PROJECT_ROOT / "tests" / "suites.toml"
ZERO_SHA = "0" * 40
FALLBACK_SUITE = "core"
MIN_NAME_MATCH = 4
GENERIC_MODULE_NAMES = frozenset(
    {"__init__", "base", "common", "helpers", "logic", "models", "schemas", "router", "utils"}
)
DEFAULT_BASE = "origin/main"
FULL_RUN_FILES = frozenset(
    {
        "tests/conftest.py",
        "tests/__init__.py",
        "tests/server_settings_helpers.py",
        "pytest.ini",
        "pyproject.toml",
        "poetry.lock",
    }
)


@dataclass
class Selection:
    """Which tests a set of changed files needs."""

    full: bool = False
    tests: set[str] = field(default_factory=set)
    suites: set[str] = field(default_factory=set)
    frontend: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.full or self.tests or self.suites or self.frontend)


# ---------------------------------------------------------------------------
# Suites
# ---------------------------------------------------------------------------


def load_suites(path: Path = SUITES_FILE) -> dict[str, dict]:
    """Suite definitions from ``tests/suites.toml``."""
    with path.open("rb") as handle:
        return tomllib.load(handle).get("suites", {})


def all_test_files(root: Path = PROJECT_ROOT) -> list[str]:
    """Repo-relative paths of every pytest file."""
    return sorted(p.relative_to(root).as_posix() for p in (root / "tests").glob("test_*.py"))


def suite_files(suite: dict, files: list[str]) -> list[str]:
    """Test files matched by a suite's globs (relative to ``tests/``)."""
    patterns = suite.get("tests", [])
    return [f for f in files if any(fnmatch.fnmatch(Path(f).name, p) for p in patterns)]


def unassigned_files(suites: dict[str, dict], files: list[str]) -> list[str]:
    """Test files that belong to no suite."""
    assigned = {f for suite in suites.values() for f in suite_files(suite, files)}
    return [f for f in files if f not in assigned]


# ---------------------------------------------------------------------------
# Selection from changed files
# ---------------------------------------------------------------------------


def _classify(path: str) -> str:
    """Kind of a changed repo-relative path."""
    if path in FULL_RUN_FILES:
        return "full"
    if path.startswith("frontend/"):
        return "frontend"
    if path.startswith("tests/test_") and path.endswith(".py"):
        return "test"
    if path.startswith(("backend/", "tests/", "scripts/", "alembic/")):
        return "source"
    return "other"


def suites_for_source(path: str, suites: dict[str, dict]) -> set[str]:
    """Suites whose ``sources`` globs match a changed repo-relative path."""
    return {
        name
        for name, suite in suites.items()
        if any(fnmatch.fnmatch(path, pattern) for pattern in suite.get("sources", []))
    }


def name_matched_tests(path: str, existing: set[str]) -> set[str]:
    """Test files whose name contains the changed module's name (``handovers`` ->
    ``test_item_handovers.py``)."""
    stem = Path(path).stem
    if len(stem) < MIN_NAME_MATCH or stem in GENERIC_MODULE_NAMES:
        return set()
    return {test for test in existing if stem in Path(test).stem}


def _add_source(
    selection: Selection, path: str, suites: dict[str, dict], existing: set[str]
) -> None:
    matched = suites_for_source(path, suites)
    selection.suites |= matched or {FALLBACK_SUITE}
    if not matched and path.endswith(".py"):
        selection.reasons.append(f"{path} is in no suite's sources; running '{FALLBACK_SUITE}'")
    selection.tests |= name_matched_tests(path, existing)


def select_tests(
    changed: list[str], graph: ImportGraph, existing: set[str], suites: dict[str, dict]
) -> Selection:
    """Pick the tests for a list of changed repo-relative paths.

    A changed test file runs itself. A changed source file runs the suites whose
    ``sources`` match it (else the fallback suite), the tests importing it directly and
    the tests named after it. Shared test infrastructure runs everything.
    """
    selection = Selection()
    modules: set[str] = set()
    for path in changed:
        kind = _classify(path)
        if kind == "full":
            selection.full = True
            selection.reasons.append(f"{path} is shared test infrastructure")
        elif kind == "frontend":
            selection.frontend = True
        elif kind == "test" and path in existing:
            selection.tests.add(path)
        elif kind in {"test", "source"}:
            modules.add(module_name(path))
            _add_source(selection, path, suites, existing)
    selection.tests |= graph.test_files_for(modules, max_depth=1) & existing
    return selection


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
    )


def _diff_names(*diff_args: str) -> list[str] | None:
    result = _git("diff", "--name-only", "--no-renames", *diff_args)
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def default_base() -> str:
    """The upstream branch if one is set, else ``origin/main``."""
    upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode == 0 and upstream.stdout.strip():
        return upstream.stdout.strip()
    return DEFAULT_BASE


def changed_files(staged: bool, base: str | None) -> list[str]:
    """Changed paths: staged, or committed since the merge base with ``base``."""
    if staged:
        return _diff_names("--cached") or []
    names = _diff_names(f"{base or default_base()}...HEAD")
    if names is None:
        raise SystemExit(f"git diff against {base or default_base()} failed.")
    return names


def pre_push_changed_files(stdin_lines: list[str]) -> list[str]:
    """Changed paths of the commits git is about to push (pre-push hook stdin)."""
    changed: set[str] = set()
    for line in stdin_lines:
        parts = line.split()
        if len(parts) != 4 or parts[1] == ZERO_SHA:
            continue
        changed.update(_push_range_names(parts[1], parts[3]))
    return sorted(changed)


def _push_range_names(local_sha: str, remote_sha: str) -> list[str]:
    if remote_sha != ZERO_SHA:
        names = _diff_names(remote_sha, local_sha)
        if names is not None:
            return names
    return _diff_names(f"{DEFAULT_BASE}...{local_sha}") or []


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def run_pytest(targets: list[str], extra: list[str]) -> int:
    cmd = [sys.executable, "-m", "pytest", "-q", *extra, *targets]
    print(f"$ pytest -q {' '.join(extra)} ({len(targets) or 'all'} files)", flush=True)
    return subprocess.run(cmd, cwd=PROJECT_ROOT, check=False).returncode


def run_frontend_tests() -> int:
    npm = shutil.which("npm")
    if not npm:
        print("npm not found: skipping frontend tests.")
        return 0
    print("$ npm --prefix frontend test", flush=True)
    return subprocess.run(
        [npm, "--prefix", "frontend", "test"], cwd=PROJECT_ROOT, check=False
    ).returncode


def _targets_for(selection: Selection, suites: dict[str, dict], files: list[str]) -> list[str]:
    targets = set(selection.tests)
    for name in selection.suites:
        targets.update(suite_files(suites.get(name, {}), files))
    return sorted(targets)


def run_selection(selection: Selection, extra: list[str], dry_run: bool) -> int:
    """Print and run what a selection needs; return the combined exit code."""
    for reason in selection.reasons:
        print(f"- {reason}")
    if selection.empty:
        print("No tests affected.")
        return 0
    targets = [] if selection.full else _targets_for(selection, load_suites(), all_test_files())
    if dry_run:
        print("Full suite." if selection.full else "\n".join(targets))
        print(f"Frontend tests: {'yes' if selection.frontend else 'no'}")
        return 0
    code = 0
    if selection.full or targets:
        code = run_pytest(targets, extra)
    if selection.frontend:
        code = run_frontend_tests() or code
    return code


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_list(_args: argparse.Namespace) -> int:
    suites = load_suites()
    files = all_test_files()
    for name, suite in suites.items():
        print(f"{name:<12} {len(suite_files(suite, files)):>4}  {suite.get('description', '')}")
    missing = unassigned_files(suites, files)
    print(f"\n{len(files)} test files, {len(missing)} in no suite.")
    for path in missing:
        print(f"  {path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if "all" in args.suites:
        return run_pytest([], args.extra)
    suites = load_suites()
    unknown = [name for name in args.suites if name not in suites]
    if unknown:
        print(f"Unknown suite(s): {', '.join(unknown)}. See `list`.")
        return 2
    return run_selection(Selection(suites=set(args.suites)), args.extra, args.dry_run)


def _select_and_run(changed: list[str], args: argparse.Namespace) -> int:
    graph = ImportGraph.from_repo(PROJECT_ROOT)
    selection = select_tests(changed, graph, set(all_test_files()), load_suites())
    return run_selection(selection, args.extra, args.dry_run)


def cmd_affected(args: argparse.Namespace) -> int:
    return _select_and_run(changed_files(args.staged, args.base), args)


def cmd_pre_push(args: argparse.Namespace) -> int:
    if os.environ.get("TW_SKIP_TESTS") == "1":
        print("TW_SKIP_TESTS=1: skipping the pre-push tests.")
        return 0
    return _select_and_run(pre_push_changed_files(sys.stdin.read().splitlines()), args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run TaleWeaver tests by suite or by change.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Show suites and test files in no suite.").set_defaults(
        func=cmd_list
    )
    run = sub.add_parser("run", help="Run one or more suites ('all' for everything).")
    run.add_argument("suites", nargs="+")
    run.set_defaults(func=cmd_run)
    affected = sub.add_parser("affected", help="Run the tests the current changes can affect.")
    affected.add_argument("--staged", action="store_true", help="Use staged changes.")
    affected.add_argument(
        "--base", help="Compare HEAD with this ref (default: upstream or origin/main)."
    )
    affected.set_defaults(func=cmd_affected)
    sub.add_parser("pre-push", help="Git pre-push hook entry (reads stdin).").set_defaults(
        func=cmd_pre_push
    )
    for child in (run, affected):
        child.add_argument("--dry-run", action="store_true", help="Only print the selection.")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    extra: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, extra = argv[:split], argv[split + 1 :]
    args = build_parser().parse_args(argv)
    args.extra = extra
    args.dry_run = getattr(args, "dry_run", False)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
