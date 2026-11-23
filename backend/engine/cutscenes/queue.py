"""Cut-scenes waiting to be shown in a session (``entity_states["__cutscene__"]``).

State::

    {"queue": [{"token": "9f2c...", "id": "INTRO"}]}

Entries are added when a chapter with ``start_cutscene_id`` starts and by ``tw.cutscene.play``
(``ScriptChangeset.cutscene_ops``, replayed by every changeset applier with
``apply_cutscene_ops``). The client shows the first entry (``client_cutscene``) and confirms it
with ``POST /{game_id}/cutscene/seen``, which removes it (``mark_seen``). The queue is part of
``entity_states`` and therefore of every checkpoint.
"""

from __future__ import annotations

import secrets
from typing import Any, Optional

from backend.engine.audio.audio_library import find_track, normalize_tracks
from backend.engine.cutscenes.library import cutscene_id_or_none, find_cutscene, normalize_cutscene

CUTSCENE_STATE_KEY = "__cutscene__"
MAX_QUEUE = 5


def _queue(entity_states: Any) -> list[dict[str, Any]]:
    state = (entity_states or {}).get(CUTSCENE_STATE_KEY)
    raw = state.get("queue") if isinstance(state, dict) else None
    return [e for e in raw or [] if isinstance(e, dict) and e.get("token") and e.get("id")]


def queue_cutscene(entity_states: dict[str, Any], cutscene_id: Any, front: bool = False) -> bool:
    """Adds a cut-scene to the session's queue; False for an invalid or already waiting id.

    ``front`` puts it first (a chapter intro plays before cut-scenes its scripts queued). A
    full queue drops its oldest entry, so ids the library does not know (a typo in a script;
    they are skipped, never shown) cannot block new cut-scenes.
    """
    wanted = cutscene_id_or_none(cutscene_id)
    queue = _queue(entity_states)
    if wanted is None or any(e["id"] == wanted for e in queue):
        return False
    queue = queue[-(MAX_QUEUE - 1) :]
    entry = {"token": secrets.token_hex(8), "id": wanted}
    queue = [entry, *queue] if front else [*queue, entry]
    entity_states[CUTSCENE_STATE_KEY] = {"queue": queue}
    return True


def queue_chapter_cutscene(
    entity_states: dict[str, Any], sequence: Any, front: bool = False
) -> bool:
    """Queues the ``start_cutscene_id`` of a chapter (sequence) that just started."""
    cutscene_id = sequence.get("start_cutscene_id") if isinstance(sequence, dict) else None
    return bool(cutscene_id) and queue_cutscene(entity_states, cutscene_id, front=front)


def apply_cutscene_ops(entity_states: dict[str, Any], ops: Optional[list[Any]]) -> None:
    """Replays the ``tw.cutscene.play`` calls of a script changeset, in order."""
    for cutscene_id in ops or []:
        queue_cutscene(entity_states, cutscene_id)


def mark_seen(entity_states: dict[str, Any], token: str) -> bool:
    """Removes the entry with ``token``; False when there is none."""
    queue = _queue(entity_states)
    remaining = [e for e in queue if e["token"] != token]
    if len(remaining) == len(queue):
        return False
    entity_states[CUTSCENE_STATE_KEY] = {"queue": remaining}
    return True


def pending_entry(entity_states: Any) -> Optional[dict[str, Any]]:
    queue = _queue(entity_states)
    return queue[0] if queue else None


def client_cutscene(
    entity_states: Any, cutscenes: Any, audio_tracks: Any, template_id: Optional[str]
) -> Optional[dict[str, Any]]:
    """The cut-scene the client shows next, resolved for playback, or None.

    Entries whose cut-scene no longer exists (deleted in the editor) are skipped; they leave
    the queue when the client confirms the next one or when ``drop_unknown`` runs.
    """
    for entry in _queue(entity_states):
        cutscene = normalize_cutscene(find_cutscene(cutscenes, entry["id"]))
        if cutscene is None or not cutscene["slides"]:
            continue
        track = find_track(normalize_tracks(audio_tracks, template_id), cutscene["audio_track_id"])
        return {
            "token": entry["token"],
            "id": cutscene["id"],
            "title": cutscene["title"],
            "slides": [
                {"id": s["id"], "text": s["text"], "image_url": s["image_url"]}
                for s in cutscene["slides"]
            ],
            "audio": {"id": track["id"], "url": track["url"]}
            if track and track.get("url")
            else None,
        }
    return None


def drop_unknown(entity_states: dict[str, Any], cutscenes: Any) -> bool:
    """Removes queued entries whose cut-scene is missing or empty; True when any was removed."""
    queue = _queue(entity_states)
    known = [
        e
        for e in queue
        if (normalize_cutscene(find_cutscene(cutscenes, e["id"])) or {}).get("slides")
    ]
    if len(known) == len(queue):
        return False
    entity_states[CUTSCENE_STATE_KEY] = {"queue": known}
    return True
