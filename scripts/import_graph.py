"""Static import graph of the backend and the test files.

Used by ``scripts/run_tests.py`` to find the tests that import a changed module.
Imports inside functions count too; dynamic imports (``importlib``) are not seen.

Only explicit imports are edges. Following them transitively selects most of the test
suite in this codebase (the turn pipeline and ``backend.main`` import nearly
everything), so callers limit the depth and add suites by source area instead.
"""

from __future__ import annotations

import ast
from collections import defaultdict, deque
from pathlib import Path

GRAPH_ROOTS = ("backend", "tests")


def module_name(rel_path: str) -> str:
    """Dotted module name of a repo-relative ``.py`` path (``a/b/__init__.py`` -> ``a.b``)."""
    parts = list(Path(rel_path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_relative(module: str | None, level: int, current: str, is_package: bool) -> str:
    """Absolute module named by a (possibly relative) ``from ... import`` statement."""
    if level == 0:
        return module or ""
    base = current.split(".")
    if not is_package:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    prefix = ".".join(base)
    if not module:
        return prefix
    return f"{prefix}.{module}" if prefix else module


def imported_names(source: str, current: str, is_package: bool = False) -> set[str]:
    """Every module name a source file may import, incl. ``from pkg import submodule``."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        base = _resolve_relative(node.module, node.level, current, is_package)
        if not base:
            continue
        names.add(base)
        names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


class ImportGraph:
    """Reverse import graph over the given Python files (repo-relative paths)."""

    def __init__(self, sources: dict[str, str]) -> None:
        self.paths: dict[str, str] = {}
        self._importers: dict[str, set[str]] = defaultdict(set)
        for rel_path in sources:
            self.paths[module_name(rel_path)] = rel_path
        for rel_path, source in sources.items():
            self._add_file(rel_path, source)

    def _add_file(self, rel_path: str, source: str) -> None:
        current = module_name(rel_path)
        is_package = rel_path.endswith("__init__.py")
        names = imported_names(source, current, is_package)
        deps = {name for name in names if name.startswith(GRAPH_ROOTS)}
        deps.discard(current)
        for dep in deps:
            self._importers[dep].add(current)

    @classmethod
    def from_repo(cls, root: Path) -> ImportGraph:
        """Build the graph from all ``.py`` files under ``backend/`` and ``tests/``."""
        sources: dict[str, str] = {}
        for top in GRAPH_ROOTS:
            for path in (root / top).rglob("*.py"):
                rel_path = path.relative_to(root).as_posix()
                sources[rel_path] = path.read_text(encoding="utf-8", errors="replace")
        return cls(sources)

    def dependents(self, modules: set[str], max_depth: int | None = None) -> set[str]:
        """The given modules plus their importers, up to ``max_depth`` import hops."""
        depth = dict.fromkeys(modules, 0)
        queue = deque(modules)
        while queue:
            current = queue.popleft()
            if max_depth is not None and depth[current] >= max_depth:
                continue
            for importer in self._importers.get(current, ()):
                if importer in depth:
                    continue
                depth[importer] = depth[current] + 1
                queue.append(importer)
        return set(depth)

    def test_files_for(self, modules: set[str], max_depth: int | None = None) -> set[str]:
        """Repo-relative test files (``tests/test_*.py``) importing the given modules."""
        affected = self.dependents(modules, max_depth)
        return {
            self.paths[name]
            for name in affected
            if name.startswith("tests.test_") and name in self.paths
        }
