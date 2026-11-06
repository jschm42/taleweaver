"""The editor autocomplete must only offer tw.exits methods that the engine implements."""

import re
from pathlib import Path

from backend.engine.scripting.context import ExitProxy

DEFINITIONS = Path(__file__).resolve().parents[1] / "frontend/src/utils/twScriptApiDefinitions.ts"


def _autocomplete_exit_methods() -> list[str]:
    source = DEFINITIONS.read_text(encoding="utf-8")
    block = source[source.index("  exits: {") : source.index("  npcs: {")]
    return re.findall(r"name: '(\w+)', kind: 'method'", block)


def test_every_autocompleted_exit_method_exists_on_the_proxy() -> None:
    # Act
    methods = _autocomplete_exit_methods()

    # Assert
    assert methods
    assert [m for m in methods if not callable(getattr(ExitProxy, m, None))] == []
