"""An adventure's cut-scenes (``AdventureTemplate.cutscenes``).

A cut-scene is a slide show shown over the play view: at the start of a chapter
(``sequence.start_cutscene_id``) or when a script calls ``tw.cutscene.play(id)``.

Entry::

    {"id": "INTRO", "title": "The Debt", "audio_track_id": "CRYPT_THEME" | None,
     "image_style": "" | "comic" | "loose watercolor, soft edges",
     "slides": [{"id": "a1b2c3", "text": "...", "image_url": "/data/..." | None,
                 "image_prompt": "..."}]}

A slide without ``image_url`` is shown on the theme's veil (the World-Builder writes slides with
a prompt; images are drawn during the manifest apply or in the editor). ``image_style`` overrides
the adventure's image style for the slide images: a style catalog id or name, or a free
description; empty = the adventure's style.
"""

from __future__ import annotations

import re
import secrets
from typing import Any, Optional

from backend.engine.audio.audio_library import track_id_or_none

CUTSCENE_ID_RE = re.compile(r"^[A-Z0-9_]{1,40}$")
SLIDE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
MAX_CUTSCENES = 100
MAX_SLIDES = 12
MAX_TITLE_CHARS = 100
MAX_TEXT_CHARS = 800
MAX_PROMPT_CHARS = 1000
MAX_URL_CHARS = 500
MAX_STYLE_CHARS = 300


def new_slide_id() -> str:
    return secrets.token_hex(4)


def cutscene_id_or_none(value: Any) -> Optional[str]:
    """An upper-case cut-scene id, or None when ``value`` is no valid id."""
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "").strip()).strip("_").upper()
    return text if CUTSCENE_ID_RE.fullmatch(text) else None


def _line(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _text(value: Any, limit: int) -> str:
    """Keeps paragraph breaks, trims each line."""
    lines = [re.sub(r"[ \t]+", " ", part).strip() for part in str(value or "").splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()[:limit]


def _image_url(value: Any) -> Optional[str]:
    """Local media URLs (``/data/...``) or bundle paths (``assets/...``); nothing else."""
    url = str(value or "").strip()[:MAX_URL_CHARS]
    if ".." in url:
        return None
    return url if url.startswith(("/data/", "assets/")) else None


def normalize_slide(raw: Any) -> Optional[dict[str, Any]]:
    """A clean slide, or None when it has neither text nor image nor prompt."""
    if isinstance(raw, str):
        raw = {"text": raw}
    if not isinstance(raw, dict):
        return None
    slide_id = str(raw.get("id") or "").strip()
    slide = {
        "id": slide_id if SLIDE_ID_RE.fullmatch(slide_id) else new_slide_id(),
        "text": _text(raw.get("text"), MAX_TEXT_CHARS),
        "image_url": _image_url(raw.get("image_url")),
        "image_prompt": _line(raw.get("image_prompt"), MAX_PROMPT_CHARS),
    }
    if not (slide["text"] or slide["image_url"] or slide["image_prompt"]):
        return None
    return slide


def normalize_cutscene(raw: Any) -> Optional[dict[str, Any]]:
    """A clean cut-scene, or None without a valid id."""
    if not isinstance(raw, dict):
        return None
    cutscene_id = cutscene_id_or_none(raw.get("id"))
    if cutscene_id is None:
        return None
    raw_slides = raw.get("slides") if isinstance(raw.get("slides"), list) else []
    slides = [s for s in (normalize_slide(entry) for entry in raw_slides) if s]
    return {
        "id": cutscene_id,
        "title": _line(raw.get("title"), MAX_TITLE_CHARS),
        "audio_track_id": track_id_or_none(raw.get("audio_track_id")),
        "image_style": _line(raw.get("image_style"), MAX_STYLE_CHARS),
        "slides": _unique_slide_ids(slides[:MAX_SLIDES]),
    }


def _unique_slide_ids(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    for slide in slides:
        while slide["id"] in seen:
            slide["id"] = new_slide_id()
        seen.add(slide["id"])
    return slides


def normalize_cutscenes(raw: Any) -> list[dict[str, Any]]:
    """Valid, unique cut-scenes (first entry per id wins), at most ``MAX_CUTSCENES``."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw if isinstance(raw, list) else []:
        cutscene = normalize_cutscene(entry)
        if cutscene is None or cutscene["id"] in seen:
            continue
        seen.add(cutscene["id"])
        result.append(cutscene)
    return result[:MAX_CUTSCENES]


def find_cutscene(cutscenes: Any, cutscene_id: Any) -> Optional[dict[str, Any]]:
    wanted = cutscene_id_or_none(cutscene_id)
    if wanted is None or not isinstance(cutscenes, list):
        return None
    return next(
        (
            c
            for c in cutscenes
            if isinstance(c, dict) and cutscene_id_or_none(c.get("id")) == wanted
        ),
        None,
    )


def cutscene_ids(cutscenes: Any) -> set[str]:
    return {c["id"] for c in normalize_cutscenes(cutscenes)}


def image_urls(cutscenes: Any) -> list[str]:
    """Every slide image URL (for export, clone and asset checks)."""
    return [
        slide["image_url"]
        for cutscene in normalize_cutscenes(cutscenes)
        for slide in cutscene["slides"]
        if slide["image_url"]
    ]


def map_image_urls(cutscenes: Any, mapper: Any) -> list[dict[str, Any]]:
    """The cut-scenes with every slide image URL replaced by ``mapper(url)`` (None drops it)."""
    result = normalize_cutscenes(cutscenes)
    for cutscene in result:
        for slide in cutscene["slides"]:
            if slide["image_url"]:
                slide["image_url"] = mapper(slide["image_url"])
    return result
