"""`tw.audio` (alias `tw.sound`): background music and sound effects requested by scripts.

The proxy only records commands in ``changeset.audio_commands``; the turn manager forwards them
to the client in the final turn event (``audio_events``), which plays them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.engine.scripting.context import ScriptChangeset


def _clamp_volume(volume: float) -> float:
    return max(0.0, min(1.0, float(volume)))


class AudioProxy:
    """Controls background music and audio playback via scripts."""

    def __init__(self, changeset: ScriptChangeset):
        self._changeset = changeset

    def play_music(self, url: str, loop: bool = True, volume: float = 1.0) -> None:
        """Plays background music track. Loop defaults to True."""
        if not url:
            return
        self._changeset.audio_commands.append(
            {
                "action": "play_music",
                "url": str(url).strip(),
                "loop": bool(loop),
                "volume": _clamp_volume(volume),
            }
        )

    def stop_music(self) -> None:
        """Stops current background music."""
        self._changeset.audio_commands.append({"action": "stop_music"})

    def play_sound(self, url: str, volume: float = 1.0) -> None:
        """Plays a one-shot sound effect."""
        if not url:
            return
        self._changeset.audio_commands.append(
            {"action": "play_sound", "url": str(url).strip(), "volume": _clamp_volume(volume)}
        )

    def play(self, url: str, loop: bool = False, volume: float = 1.0) -> None:
        """Plays an audio file. If loop is True, acts as play_music; otherwise play_sound."""
        if loop:
            self.play_music(url, loop=True, volume=volume)
        else:
            self.play_sound(url, volume=volume)
