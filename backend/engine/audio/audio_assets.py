"""Audio asset URLs of adventures: library storage, validation and ADZ import mapping.

The tracks of an adventure's audio library are files in ``adventures/library/<template>/audio/``
(imported ones in the library root); the library stores their ``/data/...`` URL like images. Manifests from outside (``.adv`` uploads,
World-Builder output) may only point at the adventure's own library files; anything else is
dropped. Deletion is likewise limited to the owning adventure's ``audio/`` folder, so a crafted
manifest can never make the editor delete another adventure's files.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from backend.utils.path_security import (
    assert_within_data_dir,
    data_url_to_local_path,
    local_path_to_data_url,
    safe_data_path,
    sanitize_path_component,
)

_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _within(path: str, folder: str) -> bool:
    root = os.path.realpath(folder)
    resolved = os.path.realpath(path)
    try:
        return os.path.commonpath([resolved, root]) == root and resolved != root
    except ValueError:
        return False


def _url_in(url: Any, folder_of: Any, template_id: Optional[str]) -> Optional[str]:
    text = str(url or "").strip()
    path = data_url_to_local_path(text) if text else None
    if not path or not template_id or len(text) > 255:
        return None
    try:
        folder = folder_of(template_id)
    except ValueError:
        return None
    return text if _within(path, folder) else None


def library_dir(template_id: str) -> str:
    safe_template = sanitize_path_component(template_id)
    if not safe_template:
        raise ValueError("Invalid adventure id for audio storage.")
    return safe_data_path("adventures", "library", safe_template)


def local_audio_url(url: Any, template_id: Optional[str]) -> Optional[str]:
    """``url`` when it points into ``template_id``'s own library folder, else None.

    Imported ``.adz`` assets land in the library root, rendered tracks in ``audio/``.
    """
    return _url_in(url, library_dir, template_id)


def library_audio_dir(template_id: str) -> str:
    safe_template = sanitize_path_component(template_id)
    if not safe_template:
        raise ValueError("Invalid adventure id for audio storage.")
    return safe_data_path("adventures", "library", safe_template, "audio")


def legacy_library_audio_dir(template_id: str) -> str:
    """Folder of tracks stored before the rename to audio (still played and deletable)."""
    safe_template = sanitize_path_component(template_id)
    if not safe_template:
        raise ValueError("Invalid adventure id for audio storage.")
    return safe_data_path("adventures", "library", safe_template, "music")


def save_library_audio(template_id: str, stem: str, token: str, data: bytes, ext: str) -> str:
    """Write a rendered track into the adventure library; returns its ``/data`` URL.

    The random ``token`` in the file name keeps browsers and exports from reusing an old file
    after the track was rendered again.
    """
    folder = library_audio_dir(template_id)
    os.makedirs(folder, exist_ok=True)
    safe_stem = _SAFE_STEM_RE.sub("_", stem)[:60].strip("_") or "audio"
    target = assert_within_data_dir(os.path.join(folder, f"{safe_stem}_{token}.{ext}"))
    with open(target, "wb") as handle:
        handle.write(data)
    return local_path_to_data_url(target)


def delete_library_audio(url: Optional[str], template_id: str) -> None:
    """Remove a replaced track; only files in ``template_id``'s own audio folder are touched."""
    own = _url_in(url, library_audio_dir, template_id)
    if not (own or _url_in(url, legacy_library_audio_dir, template_id)):
        return
    path = data_url_to_local_path(url)
    if path and os.path.isfile(path):
        os.remove(assert_within_data_dir(path))


def map_imported_audio(manifest: dict[str, Any], extracted: dict[str, str]) -> None:
    """Point the audio library's track URLs at the extracted ADZ files.

    Only files shipped inside the bundle are accepted; any other URL is dropped.
    """
    adventure = manifest.get("adventure") if isinstance(manifest.get("adventure"), dict) else {}
    for track in adventure.get("audio_tracks") or adventure.get("music_tracks") or []:
        if isinstance(track, dict) and track.get("url"):
            track["url"] = extracted.get(track["url"])
