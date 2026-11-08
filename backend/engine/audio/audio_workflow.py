"""Fills the placeholders of an uploaded ComfyUI audio workflow.

Supported placeholders, written into node inputs of the API-format graph:

* ``{{prompt}}`` / ``{{negative_prompt}}``: replaced inside any text input.
* ``{{seed}}`` / ``{{duration}}``: an input whose whole value is the placeholder becomes a number;
  inside longer text the number is inserted as text.

The graph is walked value by value, so prompt text can never change the graph structure
(no string replacement on serialized JSON).
"""

from __future__ import annotations

import copy
from typing import Any

NUMERIC_PLACEHOLDERS = ("seed", "duration")
TEXT_PLACEHOLDERS = ("prompt", "negative_prompt")


def _fill_text(value: str, values: dict[str, Any]) -> Any:
    for key in NUMERIC_PLACEHOLDERS:
        if value.strip() == f"{{{{{key}}}}}":
            return values[key]
    for key in (*TEXT_PLACEHOLDERS, *NUMERIC_PLACEHOLDERS):
        value = value.replace(f"{{{{{key}}}}}", str(values[key]))
    return value


def _fill_value(value: Any, values: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return _fill_text(value, values)
    if isinstance(value, list):
        # Two-item lists like ["4", 0] are links to other nodes and stay untouched.
        return [_fill_value(item, values) for item in value]
    return value


def fill_audio_workflow(
    workflow: dict[str, Any],
    *,
    prompt: str,
    negative_prompt: str = "",
    seed: int = 0,
    duration: int = 30,
) -> dict[str, Any]:
    """Return a copy of ``workflow`` with all placeholders replaced."""
    values = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": int(seed),
        "duration": int(duration),
    }
    graph = copy.deepcopy(workflow)
    for node in graph.values():
        inputs = node.get("inputs") or {}
        for key, value in list(inputs.items()):
            inputs[key] = _fill_value(value, values)
    return graph
