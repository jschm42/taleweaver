"""Session audio state (``entity_states["__audio__"]``) and the replay of ``tw.audio`` ops.

Scripts never generate audio themselves. ``tw.audio`` records ordered operations in
``ScriptChangeset.audio_ops``; every changeset applier replays them with ``apply_audio_ops``.
Without a script track (``now`` is None) the track the current scene selected from the audio
library plays, unless a script silenced the audio (``tw.audio.stop()``; ``tw.audio.release()`` hands
control back to scene audio). The state only says *what* should play; the generation service
(``backend.engine.audio.audio_generation``) renders missing tracks in the background and the
client plays them once their file exists. Because the state lives in ``entity_states`` it is part
of every checkpoint.

Shape::

    {
        "rev": 3,                      # bumped by every op, so clients notice replays
        "volume": 1.0,                 # script volume 0..1 (multiplied with the player's volume)
        "now": {"id": "...", "loop": True, "fade": 2.0} | None,   # script track to play
        "silenced": False,             # tw.audio.stop(): no scene audio either
        "tracks": {"<id>": {"name", "prompt", "negative_prompt", "duration", "seed"}},
        "library": {"<name>": "<id>"},
    }
"""

from __future__ import annotations

import copy
import re
from typing import Any, Optional

AUDIO_STATE_KEY = "__audio__"
# Sessions saved before the rename to "audio" keep their state under this key.
LEGACY_STATE_KEY = "__music__"
TRACK_ID_RE = re.compile(r"^[a-f0-9]{32}$")
MAX_TRACKS = 100
MAX_PROMPT_CHARS = 1000
MAX_NAME_CHARS = 64
MAX_FADE_SECONDS = 30.0


def empty_audio_state() -> dict[str, Any]:
    return {"rev": 0, "volume": 1.0, "now": None, "silenced": False, "tracks": {}, "library": {}}


def read_audio_state(entity_states: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return a normalized copy of the session's audio state."""
    states = entity_states or {}
    raw = states.get(AUDIO_STATE_KEY, states.get(LEGACY_STATE_KEY))
    state = empty_audio_state()
    if not isinstance(raw, dict):
        return state
    state["rev"] = int(raw.get("rev") or 0)
    state["volume"] = clamp_volume(raw.get("volume", 1.0))
    state["silenced"] = bool(raw.get("silenced", False))
    state["tracks"] = {
        str(k): dict(v)
        for k, v in (raw.get("tracks") or {}).items()
        if TRACK_ID_RE.fullmatch(str(k)) and isinstance(v, dict)
    }
    state["library"] = {
        str(k): str(v) for k, v in (raw.get("library") or {}).items() if v in state["tracks"]
    }
    now = raw.get("now")
    if isinstance(now, dict) and now.get("id") in state["tracks"]:
        state["now"] = dict(now)
    return state


def clamp_volume(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 1.0


def clamp_fade(value: Any) -> float:
    try:
        return min(MAX_FADE_SECONDS, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 2.0


def _now_entry(op: dict[str, Any]) -> dict[str, Any]:
    return {"id": op["id"], "loop": bool(op.get("loop", True)), "fade": clamp_fade(op.get("fade"))}


def _op_generate(state: dict[str, Any], op: dict[str, Any]) -> None:
    track_id = str(op.get("id") or "")
    if not TRACK_ID_RE.fullmatch(track_id) or len(state["tracks"]) >= MAX_TRACKS:
        return
    state["tracks"][track_id] = {
        "name": op.get("name"),
        "prompt": str(op.get("prompt") or "")[:MAX_PROMPT_CHARS],
        "negative_prompt": str(op.get("negative_prompt") or "")[:MAX_PROMPT_CHARS],
        "duration": op.get("duration"),
        "seed": int(op.get("seed") or 0),
    }
    if op.get("name"):
        state["library"][str(op["name"])] = track_id
    if op.get("play", True):
        state["now"] = _now_entry(op)
        state["silenced"] = False


def _op_play(state: dict[str, Any], op: dict[str, Any]) -> None:
    if op.get("id") in state["tracks"]:
        state["now"] = _now_entry(op)
        state["silenced"] = False


def _op_stop(state: dict[str, Any], op: dict[str, Any]) -> None:
    del op
    state["now"] = None
    state["silenced"] = True


def _op_release(state: dict[str, Any], op: dict[str, Any]) -> None:
    del op
    state["now"] = None
    state["silenced"] = False


def _op_volume(state: dict[str, Any], op: dict[str, Any]) -> None:
    state["volume"] = clamp_volume(op.get("value"))


def _op_forget(state: dict[str, Any], op: dict[str, Any]) -> None:
    state["library"].pop(str(op.get("name") or ""), None)


_OPS = {
    "generate": _op_generate,
    "play": _op_play,
    "stop": _op_stop,
    "release": _op_release,
    "volume": _op_volume,
    "forget": _op_forget,
}


def apply_audio_op_list(state: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a new audio state with ``ops`` applied in order (unknown ops are skipped)."""
    result = copy.deepcopy(state)
    for op in ops:
        handler = _OPS.get(str(op.get("op") or ""))
        if handler is None:
            continue
        handler(result, op)
        result["rev"] = int(result.get("rev") or 0) + 1
    return result


def apply_audio_ops(entity_states: dict[str, Any], ops: list[dict[str, Any]]) -> bool:
    """Replay ``tw.audio`` ops into ``entity_states`` in place; True when anything changed."""
    if not ops:
        return False
    entity_states[AUDIO_STATE_KEY] = apply_audio_op_list(read_audio_state(entity_states), ops)
    entity_states.pop(LEGACY_STATE_KEY, None)
    return True
