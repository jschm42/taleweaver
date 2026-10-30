"""Scene helper blocks: per-scene functions and constants, available to every script run.

A scene's ``helpers_script`` works like the global ``init_script`` definitions: only ``def``
statements and constant assignments are loaded, freshly on every script run, so nothing is
stored in the game state. All scenes' helpers are always available, in manifest order after
``init_script``, regardless of where the player is. Scoping them to the current scene would
make a function's existence depend on the player's route.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.scripting.runner import ScriptRunner


def helper_source_id(scene_id: str) -> str:
    """Name used in script error messages for a scene's helper block."""
    return f"helpers_{scene_id}"


def scene_helpers(manifest: Optional[dict[str, Any]]) -> list[tuple[str, str]]:
    """``(source_id, code)`` of every scene with a helper block, in manifest order."""
    scenes = (manifest or {}).get("scenes")
    if not isinstance(scenes, list):
        return []
    helpers: list[tuple[str, str]] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        code = str(scene.get("helpers_script") or "").strip()
        if code:
            helpers.append((helper_source_id(str(scene.get("id") or "?")), code))
    return helpers


def runner_for_manifest(
    manifest: Optional[dict[str, Any]],
    scripts: Optional[list[dict[str, Any]]] = None,
    init_script: Optional[str] = None,
) -> ScriptRunner:
    """A runner that loads ``init_script`` and all scene helpers before every script run."""
    manifest = manifest or {}
    return ScriptRunner(
        scripts or [],
        init_script=init_script if init_script is not None else manifest.get("init_script"),
        helpers=scene_helpers(manifest),
    )
