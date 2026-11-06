"""Write a turn's working copy of ``entity_states`` back without losing interim changes.

The turn applier copies ``SessionState.entity_states`` once, edits the copy, and writes it
back at the end. In between, quest, award and sequence evaluation replace keys on the
state directly (e.g. ``__script_vars__`` with ``__seq_completed_<ID>__``). Writing the copy
back as a whole would drop those keys, so a completed sequence could start again.
"""

from typing import Any

_MISSING = object()


def merge_entity_states(
    base: dict[str, Any], working: dict[str, Any], current: dict[str, Any] | None
) -> dict[str, Any]:
    """Merge the turn's working copy onto the current state.

    ``base`` is the dict the working copy was made from. A key the working copy left
    untouched keeps the current state's value; every other key takes the working copy's
    value (as before, the turn's own edits win).
    """
    merged = dict(current or {})
    for key in set(base) | set(working):
        own = working.get(key, _MISSING)
        if own is base.get(key, _MISSING):
            continue
        if own is _MISSING:
            merged.pop(key, None)
            continue
        merged[key] = own
    return merged
