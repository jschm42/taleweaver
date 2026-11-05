"""Soft stage directions that scripts give the Game Master (``tw.story.direct``).

A script cannot write the narration of a turn itself, but it can ask the GM for something,
e.g. ``tw.story.direct("Let BRAM sing a sailor song")``. The direction is stored in the
session state and handed to the next GM narration (a regular turn, or a choice dialog that
narrates its outcome), which uses it once and drops it.

A direction can carry a callback (``after="handler"``, ``after_args={...}``): a function of the
global init script that runs once that narration is done, so its system messages and state
changes follow the narrated scene instead of preceding it.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

# Session-state key (inside ``entity_states``) holding directions not yet narrated.
GM_DIRECTIONS_KEY = "__gm_directions__"
# Session-state key holding the callbacks to run after that narration.
AFTER_NARRATION_KEY = "__gm_after_narration__"
MAX_GM_DIRECTIONS = 5
MAX_AFTER_NARRATION = 10
MAX_DIRECTION_LENGTH = 500
MAX_CALLBACK_ARGS_LENGTH = 4000
_HANDLER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def clean_direction(text: Any) -> str:
    """Single-line, length-capped direction text; empty when there is nothing to say."""
    return " ".join(str(text or "").split())[:MAX_DIRECTION_LENGTH]


def pending_gm_directions(entity_states: Any) -> list[str]:
    """Directions waiting for the next GM narration."""
    directions = (entity_states or {}).get(GM_DIRECTIONS_KEY)
    return [str(d) for d in directions] if isinstance(directions, list) else []


def after_narration_callback(after: Any, after_args: Any) -> tuple[Optional[dict], str]:
    """Validated callback entry ``{handler, args}``, or (None, reason) when it is unusable."""
    name = after if isinstance(after, str) else getattr(after, "__name__", "")
    name = str(name or "").strip()
    if not _HANDLER_NAME.match(name):
        return None, "after must name a function of the init script"
    args = {} if after_args is None else after_args
    if not isinstance(args, dict) or not all(isinstance(k, str) for k in args):
        return None, "after_args must be a dict with string keys"
    # The keys become keyword arguments of the call, so they must be plain parameter names.
    if not all(_HANDLER_NAME.match(k) for k in args):
        return None, "after_args keys must be parameter names of the callback"
    try:
        encoded = json.dumps(args)
    except (TypeError, ValueError):
        return None, "after_args must only hold plain values (text, numbers, lists, dicts)"
    if len(encoded) > MAX_CALLBACK_ARGS_LENGTH:
        return None, f"after_args is too large (max {MAX_CALLBACK_ARGS_LENGTH} characters)"
    return {"handler": name, "args": json.loads(encoded)}, ""


def queue_direction(changeset: Any, text: str, after: Any = None, after_args: Any = None) -> None:
    """Adds a direction (and its after-narration callback) to a script changeset.

    An unusable callback is reported as a visible script error (like a missing dialog handler):
    otherwise the author's follow-up silently never happens.
    """
    if not text:
        return
    changeset.gm_directions.append(text)
    if after is None:
        return
    callback, problem = after_narration_callback(after, after_args)
    if callback is None:
        changeset.system_messages.append(f"Script error: direction callback ignored: {problem}.")
        return
    changeset.after_narration.append(callback)


def pending_after_narration(entity_states: Any) -> list[dict[str, Any]]:
    """Callbacks waiting for the next GM narration to finish."""
    callbacks = (entity_states or {}).get(AFTER_NARRATION_KEY)
    if not isinstance(callbacks, list):
        return []
    return [c for c in callbacks if isinstance(c, dict) and c.get("handler")]


def store_gm_directions(
    entity_states: dict[str, Any],
    directions: list[str],
    callbacks: Optional[list[dict[str, Any]]] = None,
) -> None:
    """Queues new directions (and their callbacks) behind the pending ones.

    Only the newest few directions are kept; callbacks are kept in order up to their limit.
    """
    if directions:
        queued = pending_gm_directions(entity_states) + list(directions)
        entity_states[GM_DIRECTIONS_KEY] = queued[-MAX_GM_DIRECTIONS:]
    if callbacks:
        queued_callbacks = pending_after_narration(entity_states) + list(callbacks)
        entity_states[AFTER_NARRATION_KEY] = queued_callbacks[:MAX_AFTER_NARRATION]


def take_gm_directions(state: Any) -> list[str]:
    """Removes and returns the pending directions of a session state."""
    directions = pending_gm_directions(state.entity_states)
    if not directions:
        return []
    entity_states = dict(state.entity_states or {})
    entity_states.pop(GM_DIRECTIONS_KEY, None)
    state.entity_states = entity_states
    flag_modified(state, "entity_states")
    return directions


def take_after_narration(state: Any) -> list[dict[str, Any]]:
    """Removes and returns the callbacks to run now that a narration is done."""
    callbacks = pending_after_narration(state.entity_states)
    if not callbacks:
        return []
    entity_states = dict(state.entity_states or {})
    entity_states.pop(AFTER_NARRATION_KEY, None)
    state.entity_states = entity_states
    flag_modified(state, "entity_states")
    return callbacks


def format_gm_directions(directions: list[str]) -> str:
    """Prompt block asking the GM to work the directions into this narration."""
    if not directions:
        return ""
    return (
        "AUTHOR DIRECTIONS (from the adventure's scripts; work them naturally into this "
        "narration, in character and consistent with the scene; they never override game "
        "rules or the technical outcome):\n" + "\n".join(f"- {d}" for d in directions)
    )
