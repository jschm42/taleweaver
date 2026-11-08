"""``tw.audio``: background audio generated on the fly by scripts.

Calls only record ordered ops in ``changeset.audio_ops`` (see ``engine/audio/audio_state.py``)
and mirror them on a local copy, so a script reads its own changes back
(``tw.audio.generate("...", name="storm"); tw.audio.has("storm")`` is True). Rendering happens
later in the background; until the track is ready, the previous audio keeps playing.
"""

from __future__ import annotations

import secrets
from typing import Any, Optional
from uuid import uuid4

from backend.engine.audio.audio_state import (
    MAX_NAME_CHARS,
    MAX_PROMPT_CHARS,
    MAX_TRACKS,
    apply_audio_op_list,
    clamp_fade,
    clamp_volume,
    empty_audio_state,
)


class AudioProxy:
    """Safe proxy exposed to scripts as ``tw.audio``."""

    def __init__(
        self,
        changeset: Any,
        state: Optional[dict[str, Any]],
        context: Any = None,
        library: Optional[list[dict[str, Any]]] = None,
    ):
        self._changeset = changeset
        self._state = state or empty_audio_state()
        self._context = context
        # The adventure's audio library (editor Audio tab): {track id: name}.
        self._library = {
            str(t.get("id")): str(t.get("name") or t.get("id"))
            for t in library or []
            if isinstance(t, dict) and t.get("id")
        }

    def _record(self, op: dict[str, Any]) -> None:
        self._changeset.audio_ops.append(op)
        self._state = apply_audio_op_list(self._state, [op])

    def _debug(self, message: str) -> None:
        if self._context is not None:
            self._context.debug(message)

    def _error(self, api: str, message: str) -> None:
        """A script error the player sees in the chat (like an unknown award key)."""
        from backend.engine.scripting.runner import SCRIPT_ERROR_PREFIX

        self._changeset.system_messages.append(f"{SCRIPT_ERROR_PREFIX} in '{api}': {message}")

    def _library_id(self, key: str) -> Optional[str]:
        """Library track by id, else by its exact name."""
        if key in self._library:
            return key
        return next((tid for tid, name in self._library.items() if name == key), None)

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
        if now.get("library_id"):
            return now["library_id"]
        track = self._state["tracks"].get(now["id"]) or {}
        return track.get("name") or now["id"]

    @property
    def is_playing(self) -> bool:
        """True while a script track is set to play (it may still be generating)."""
        return self._state.get("now") is not None

    @property
    def is_silenced(self) -> bool:
        """True after ``stop()``: no scene audio until ``play``/``release``."""
        return bool(self._state.get("silenced"))

    @property
    def volume(self) -> float:
        return float(self._state.get("volume", 1.0))

    @property
    def tracks(self) -> list[str]:
        """Names of all named tracks of this session."""
        return list(self._state["library"])

    @property
    def library(self) -> list[str]:
        """Ids of the adventure's audio library tracks (editor Audio tab)."""
        return list(self._library)

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
        volume: float = 1.0,
    ) -> Optional[str]:
        """Requests a new track from ``prompt``; returns its id (None when rejected).

        ``volume`` (0..1) applies to this playback only. A ``name`` makes the track reusable: calling ``generate`` again with the same name
        plays the existing track instead of rendering a new one, unless ``regenerate=True``.
        """
        text = str(prompt or "").strip()[:MAX_PROMPT_CHARS]
        if not text:
            self._debug("tw.audio.generate ignored: the prompt is empty.")
            return None
        track_name = self._name(name)
        if track_name and self.has(track_name) and not regenerate:
            if play:
                self.play(track_name, loop=loop, fade=fade, volume=volume)
            return self._state["library"][track_name]
        if len(self._state["tracks"]) >= MAX_TRACKS:
            self._debug(f"tw.audio.generate ignored: a session holds at most {MAX_TRACKS} tracks.")
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
                "volume": clamp_volume(volume),
            }
        )
        return track_id

    def play(self, name: str, loop: bool = True, fade: float = 2.0, volume: float = 1.0) -> bool:
        """Plays a track; False (and a script error in the chat) if there is none.

        Looks for, in this order: a track this session generated (by name or id), then a track
        of the adventure's audio library (by its id from the Audio tab, or its exact name).
        """
        key = str(name or "").strip()
        track_id = self._state["library"].get(key) or (key if key in self._state["tracks"] else "")
        if track_id:
            self._record(
                {
                    "op": "play",
                    "id": track_id,
                    "loop": bool(loop),
                    "fade": clamp_fade(fade),
                    "volume": clamp_volume(volume),
                }
            )
            return True
        library_id = self._library_id(key)
        if library_id:
            self._record(
                {
                    "op": "play_library",
                    "library_id": library_id,
                    "loop": bool(loop),
                    "fade": clamp_fade(fade),
                    "volume": clamp_volume(volume),
                }
            )
            return True
        self._error(
            "tw.audio.play",
            f"no audio track '{key}'. Use the id or name of a track from the editor's Audio tab, "
            "or the name of a track this session generated with tw.audio.generate(name=...).",
        )
        return False

    def stop(self, fade: float = 2.0) -> None:
        """Fades all audio out, scene audio too (silence until play/generate/release)."""
        self._record({"op": "stop", "fade": clamp_fade(fade)})

    def release(self) -> None:
        """Ends script audio; the current scene's library track plays again."""
        self._record({"op": "release"})

    def stop_speech(self, fade: float = 0.5) -> None:
        """Fades out the text-to-speech that plays now (and drops its queued lines).

        E.g. before a track starts that must not be talked over; combine with
        ``tw.story.skip_narration()`` so the turn's narration does not start new speech.
        ``fade`` is in seconds (0..5).
        """
        self._record({"op": "stop_speech", "fade": fade})

    def set_volume(self, value: float) -> None:
        """Sets the script audio volume 0..1 (multiplied with the player's own volume)."""
        self._record({"op": "volume", "value": clamp_volume(value)})

    def forget(self, name: str) -> None:
        """Removes a name, so the next ``generate`` with it renders a new track."""
        self._record({"op": "forget", "name": str(name or "").strip()})
