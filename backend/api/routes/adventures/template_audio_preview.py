"""Hover preview audio of library tiles: each adventure's optional title track."""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Optional

from backend.engine.audio.audio_library import find_track, normalize_tracks
from backend.models.adventure_template import AdventureTemplate
from backend.utils.path_security import data_url_to_local_path


def _playable(url: Optional[str]) -> Optional[str]:
    path = data_url_to_local_path(url)
    return url if path and os.path.isfile(path) else None


def title_track_urls(templates: Iterable[AdventureTemplate]) -> dict[str, str]:
    """template id -> playable URL of its title track (adventures without one are left out)."""
    previews: dict[str, str] = {}
    for template in templates:
        if not template.title_track_id:
            continue
        tracks = normalize_tracks(template.audio_tracks, template.id)
        track = find_track(tracks, template.title_track_id)
        url = _playable(track.get("url")) if track else None
        if url:
            previews[template.id] = url
    return previews
