"""``tw.music``: background music generated on the fly by scripts.

Calls only record ordered ops in ``changeset.music_ops`` (see ``engine/audio/music_state.py``)
and mirror them on a local copy, so a script reads its own changes back
(``tw.music.generate("...", name="storm"); tw.music.has("storm")`` is True). Rendering happens
later in the background; until the track is ready, the previous music keeps playing.
"""

from __future__ import annotations

import secrets
from typing import Any, Optional
from uuid import uuid4

from backend.engine.audio.music_state import (
    MAX_NAME_CHARS,
    MAX_PROMPT_CHARS,
    MAX_TRACKS,
    apply_music_op_list,
    clamp_fade,
    clamp_volume,
    empty_music_state,
)


class MusicProxy:
    """Safe proxy exposed to scripts as ``tw.music``."""

    def __init__(self, changeset: Any, state: Optional[dict[str, Any]], context: Any = None):
        self._changeset = changeset
        self._state = state or empty_music_state()
        self._context = context

    def _record(self, op: dict[str, Any]) -> None:
        self._changeset.music_ops.append(op)
        self._state = apply_music_op_list(self._state, [op])

    def _debug(self, message: str) -> None:
        if self._context is not None:
            self._context.debug(message)

    def _name(self, name: Any) -> Optional[str]:
        text = str(name or "").strip()
        return text[:MAX_NAME_CHARS] if text else None

    # --- reading -------------------------------------------------------------------------

    @property
    def current(self) -> Optional[str]:
        """Name of the track that should play now (its id for unnamed tracks), else None."""
        now = self._state.get("now")
        if not now:
            return None
        track = self._state["tracks"].get(now["id"]) or {}
        return track.get("name") or now["id"]

    @property
    def is_playing(self) -> bool:
        """True while a track is set to play (it may still be generating)."""
        return self._state.get("now") is not None

    @property
    def volume(self) -> float:
        return float(self._state.get("volume", 1.0))

    @property
    def tracks(self) -> list[str]:
        """Names of all named tracks of this session."""
        return list(self._state["library"])

    def has(self, name: str) -> bool:
        """True when a track with this name was generated (or requested) before."""
        return str(name or "").strip() in self._state["library"]

    # --- changing ------------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        name: Optional[str] = None,
        duration: Optional[int] = None,
        play: bool = True,
        loop: bool = True,
        negative_prompt: str = "",
        seed: Optional[int] = None,
        regenerate: bool = False,
        fade: float = 2.0,
    ) -> Optional[str]:
        """Requests a new track from ``prompt``; returns its id (None when rejected).

        A ``name`` makes the track reusable: calling ``generate`` again with the same name
        plays the existing track instead of rendering a new one, unless ``regenerate=True``.
        """
        text = str(prompt or "").strip()[:MAX_PROMPT_CHARS]
        if not text:
            self._debug("tw.music.generate ignored: the prompt is empty.")
            return None
        track_name = self._name(name)
        if track_name and self.has(track_name) and not regenerate:
            if play:
                self.play(track_name, loop=loop, fade=fade)
            return self._state["library"][track_name]
        if len(self._state["tracks"]) >= MAX_TRACKS:
            self._debug(f"tw.music.generate ignored: a session holds at most {MAX_TRACKS} tracks.")
            return None
        track_id = uuid4().hex
        self._record(
            {
                "op": "generate",
                "id": track_id,
                "name": track_name,
                "prompt": text,
                "negative_prompt": str(negative_prompt or "")[:MAX_PROMPT_CHARS],
                "duration": int(duration) if duration else None,
                "seed": int(seed) if seed is not None else secrets.randbelow(2**31),
                "play": bool(play),
                "loop": bool(loop),
                "fade": clamp_fade(fade),
            }
        )
        return track_id

    def play(self, name: str, loop: bool = True, fade: float = 2.0) -> bool:
        """Plays a track generated before (by name or id); False if it is unknown."""
        key = str(name or "").strip()
        track_id = self._state["library"].get(key) or (key if key in self._state["tracks"] else "")
        if not track_id:
            self._debug(f"tw.music.play ignored: no track named '{key}'.")
            return False
        self._record({"op": "play", "id": track_id, "loop": bool(loop), "fade": clamp_fade(fade)})
        return True

    def stop(self, fade: float = 2.0) -> None:
        """Fades the music out (silence until the next play/generate)."""
        self._record({"op": "stop", "fade": clamp_fade(fade)})

    def set_volume(self, value: float) -> None:
        """Sets the script music volume 0..1 (multiplied with the player's own volume)."""
        self._record({"op": "volume", "value": clamp_volume(value)})

    def forget(self, name: str) -> None:
        """Removes a name, so the next ``generate`` with it renders a new track."""
        self._record({"op": "forget", "name": str(name or "").strip()})
