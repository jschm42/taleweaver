"""Helper blocks of sequences and scenes: functions and constants available to every script run.

A sequence's or scene's ``helpers_script`` works like the global ``init_script`` definitions:
only ``def`` statements and constant assignments are loaded, freshly on every script run, so
nothing is stored in the game state. All blocks are always available, loaded after
``init_script`` in a fixed order (sequences by chapter order, then scenes in manifest order),
regardless of where the player is or which chapter is active. Scoping them would make a
function's existence depend on the player's route.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.scripting.runner import ScriptRunner


def helper_source_id(scene_id: str) -> str:
    """Name used in script error messages for a scene's helper block."""
    return f"helpers_{scene_id}"


def sequence_helper_source_id(sequence_id: str) -> str:
    """Name used in script error messages for a sequence's helper block."""
    return f"helpers_sequence_{sequence_id}"


def _blocks(entries: Any, source_id: Any) -> list[tuple[str, str]]:
    if not isinstance(entries, list):
        return []
    blocks: list[tuple[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("helpers_script") or "").strip()
        if code:
            blocks.append((source_id(str(entry.get("id") or "?")), code))
    return blocks


def _order(sequence: Any) -> int:
    order = sequence.get("order") if isinstance(sequence, dict) else None
    return order if isinstance(order, int) else 0


def scene_helpers(manifest: Optional[dict[str, Any]]) -> list[tuple[str, str]]:
    """``(source_id, code)`` of every scene with a helper block, in manifest order."""
    return _blocks((manifest or {}).get("scenes"), helper_source_id)


def sequence_helpers(sequences: Any) -> list[tuple[str, str]]:
    """``(source_id, code)`` of every sequence with a helper block, in chapter order."""
    ordered = sorted(sequences, key=_order) if isinstance(sequences, list) else []
    return _blocks(ordered, sequence_helper_source_id)


def runner_for_manifest(
    manifest: Optional[dict[str, Any]],
    scripts: Optional[list[dict[str, Any]]] = None,
    init_script: Optional[str] = None,
    sequences: Any = None,
) -> ScriptRunner:
    """A runner that loads ``init_script`` and all sequence and scene helpers before every run.

    ``sequences`` defaults to the manifest's; pass the adventure's own list where it is the
    source of truth (the editor saves sequences on the adventure).
    """
    manifest = manifest or {}
    chapters = sequences if sequences is not None else manifest.get("sequences")
    return ScriptRunner(
        scripts or [],
        init_script=init_script if init_script is not None else manifest.get("init_script"),
        helpers=[*sequence_helpers(chapters), *scene_helpers(manifest)],
    )
