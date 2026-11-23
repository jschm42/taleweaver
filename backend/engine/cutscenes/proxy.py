"""``tw.cutscene``: scripts show a cut-scene of the adventure's library.

``tw.cutscene.play("INTRO")`` records the id in ``ScriptChangeset.cutscene_ops``; every changeset
applier queues it (``queue.apply_cutscene_ops``) and the client shows it over the play view.
Scripts run to completion, so the call does not wait for the cut-scene to end. Combine it with
``tw.story.skip_narration()`` when the cut-scene should replace the turn's narration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.engine.cutscenes.library import cutscene_id_or_none

if TYPE_CHECKING:
    from backend.engine.scripting.context import ScriptChangeset


class CutsceneProxy:
    """Safe proxy exposed to scripts as ``tw.cutscene`` (alias ``tw.cutscenes``)."""

    def __init__(self, changeset: ScriptChangeset, debug: Any = None):
        self._changeset = changeset
        self._debug = debug

    def play(self, cutscene_id: str) -> bool:
        """Queues the cut-scene ``cutscene_id``; False when the id is not valid."""
        wanted = cutscene_id_or_none(cutscene_id)
        if wanted is None:
            if self._debug:
                self._debug(f"tw.cutscene.play ignored: invalid id {cutscene_id!r}.")
            return False
        self._changeset.cutscene_ops.append(wanted)
        return True

    def show(self, cutscene_id: str) -> bool:
        """Alias for play()."""
        return self.play(cutscene_id)
