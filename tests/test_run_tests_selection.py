"""Test selection of scripts/run_tests.py: import graph, change classification, suites."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from import_graph import ImportGraph, imported_names, module_name  # noqa: E402
from run_tests import (  # noqa: E402
    all_test_files,
    load_suites,
    pre_push_changed_files,
    select_tests,
    suite_files,
    suites_for_source,
    unassigned_files,
)

SOURCES = {
    "backend/__init__.py": "",
    "backend/engine/__init__.py": "",
    "backend/engine/dice.py": "import random\n",
    "backend/engine/combat.py": "from backend.engine import dice\n",
    "backend/api/routes.py": "def handler():\n    from backend.engine.combat import attack\n",
    "backend/engine/rel.py": "from . import dice\nfrom .combat import attack\n",
    "tests/test_combat.py": "from backend.engine.combat import attack\n",
    "tests/test_routes.py": "import backend.api.routes\n",
    "tests/test_dice_rolls.py": "import json\n",
    "tests/test_other.py": "import json\n",
}
EXISTING = {path for path in SOURCES if path.startswith("tests/test_")}
SUITES = {
    "core": {"tests": ["test_other.py"], "sources": ["backend/main.py"]},
    "combat": {"tests": ["test_combat.py"], "sources": ["backend/engine/combat*"]},
}


def _select(changed: list[str]):
    return select_tests(changed, ImportGraph(SOURCES), EXISTING, SUITES)


def test_module_name_strips_init_and_suffix():
    assert module_name("backend/engine/__init__.py") == "backend.engine"
    assert module_name("backend/engine/dice.py") == "backend.engine.dice"


def test_relative_and_function_level_imports_resolve():
    names = imported_names(SOURCES["backend/engine/rel.py"], "backend.engine.rel")
    assert {"backend.engine.dice", "backend.engine.combat"} <= names
    graph = ImportGraph(SOURCES)
    assert "backend.api.routes" in graph.dependents({"backend.engine.combat"})


def test_depth_limit_stops_at_direct_importers():
    graph = ImportGraph(SOURCES)
    assert graph.test_files_for({"backend.engine.combat"}, max_depth=1) == {"tests/test_combat.py"}
    assert graph.test_files_for({"backend.engine.combat"}) == {
        "tests/test_combat.py",
        "tests/test_routes.py",
    }


def test_source_change_runs_its_suite_importers_and_name_matches():
    selection = _select(["backend/engine/dice.py"])
    assert selection.suites == {"core"}
    assert "tests/test_dice_rolls.py" in selection.tests
    assert selection.reasons


def test_source_in_a_suite_selects_that_suite():
    selection = _select(["backend/engine/combat.py"])
    assert selection.suites == {"combat"}
    assert selection.tests == {"tests/test_combat.py"}


def test_changed_test_file_runs_itself_only():
    selection = _select(["tests/test_other.py"])
    assert selection.tests == {"tests/test_other.py"}
    assert not selection.suites


def test_shared_infrastructure_selects_the_full_suite():
    selection = _select(["tests/conftest.py"])
    assert selection.full


def test_frontend_and_docs_changes():
    selection = _select(["frontend/src/App.vue", "docs/model-selection.md"])
    assert selection.frontend
    assert not (selection.tests or selection.suites)


def test_docs_only_change_selects_nothing():
    assert _select(["README.md"]).empty


def test_pre_push_skips_branch_deletions(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "run_tests._push_range_names", lambda local, remote: calls.append((local, remote)) or []
    )
    zero = "0" * 40
    pre_push_changed_files([f"refs/heads/x {zero} refs/heads/x {'a' * 40}"])
    assert calls == []


def test_every_test_file_belongs_to_a_suite():
    assert unassigned_files(load_suites(), all_test_files()) == []


def test_every_suite_matches_files():
    files = all_test_files()
    empty = [name for name, suite in load_suites().items() if not suite_files(suite, files)]
    assert empty == []


def test_most_backend_modules_belong_to_a_suite_area():
    suites = load_suites()
    modules = [
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "backend").rglob("*.py")
        if p.name != "__init__.py"
    ]
    uncovered = [path for path in modules if not suites_for_source(path, suites)]
    assert len(uncovered) <= len(modules) // 10, uncovered
