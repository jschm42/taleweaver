"""``[Cutscene: ID] Title`` blocks of a blueprint.

Every prose line of the block is one slide (what the narrator says); a line starting with ``+``
adds a further passage to the slide above it (shown after it over the same picture).
``image N:`` sets the image prompt of slide N, ``style:`` the cut-scene's own image style and
``audio:`` a track of the audio library. A chapter shows it with ``cutscene: ID``. Example::

    [Cutscene: INTRO] The Crimson Debt
    style: comic book
    The village burns inside a ring of black fire.
    + Nobody remembers who lit it.
    A shadow wolf watches from the hill.
    image 1: a medieval village ringed by black fire at night

The author's slides are final: after generation they replace the slides the LLM wrote for that
id (``apply_cutscene_blocks``); an LLM image prompt is kept where the author gave none.
"""

from __future__ import annotations

import re
from typing import Any

from backend.engine.blueprint.models import Blueprint, BlueprintBlock

_IMAGE_KEY = re.compile(r"^image_(\d{1,2})$")
MAX_SLIDES = 12


def _image_prompts(block: BlueprintBlock) -> dict[int, str]:
    prompts: dict[int, str] = {}
    for key, value in block.fields.items():
        match = _IMAGE_KEY.match(key)
        if match:
            prompts[int(match.group(1)) - 1] = str(value.value or "").strip()
    return prompts


def _slide_passages(block: BlueprintBlock) -> list[list[str]]:
    """The passages of each slide: a ``+`` line continues the slide above it."""
    slides: list[list[str]] = []
    for raw in block.prose:
        line = raw.strip()
        if line.startswith("+") and slides:
            passage = line[1:].strip()
            if passage:
                slides[-1].append(passage)
        elif line:
            slides.append([line.lstrip("+").strip()])
    return slides[:MAX_SLIDES]


def cutscene_from_block(block: BlueprintBlock) -> dict[str, Any]:
    """The manifest entry the block describes."""
    prompts = _image_prompts(block)
    slides = _slide_passages(block)
    fields = block.fixed() | block.hints()
    return {
        "id": block.ref,
        "title": block.name or "",
        "image_style": str(fields.get("image_style") or ""),
        "audio_track_id": fields.get("audio_track_id") or None,
        "slides": [
            {"passages": passages, "image_prompt": prompts.get(index, "")}
            for index, passages in enumerate(slides)
        ],
    }


def _merge_into(entry: dict[str, Any], own: dict[str, Any]) -> None:
    llm_slides = [s for s in entry.get("slides") or [] if isinstance(s, dict)]
    if own["slides"]:
        for index, slide in enumerate(own["slides"]):
            if not slide["image_prompt"] and index < len(llm_slides):
                slide["image_prompt"] = str(llm_slides[index].get("image_prompt") or "")
        entry["slides"] = own["slides"]
    for key in ("title", "image_style", "audio_track_id"):
        if own.get(key):
            entry[key] = own[key]
    for key in [k for k in entry if _IMAGE_KEY.match(k)]:
        entry.pop(key)


def apply_cutscene_blocks(manifest: dict[str, Any], blueprint: Blueprint) -> None:
    """Writes the blueprint's cut-scenes over the generated ones (by id)."""
    entries = manifest.setdefault("cutscenes", [])
    if not isinstance(entries, list):
        entries = manifest["cutscenes"] = []
    for block in blueprint.of_kind("cutscene"):
        own = cutscene_from_block(block)
        wanted = block.ref.upper()
        entry = next(
            (
                e
                for e in entries
                if isinstance(e, dict) and str(e.get("id") or "").upper() == wanted
            ),
            None,
        )
        if entry is None:
            entries.append(own)
            continue
        _merge_into(entry, own)


def check_cutscene_blocks(blueprint: Blueprint) -> None:
    """Warns about cut-scenes without slides and image prompts for missing slides."""
    for block in blueprint.of_kind("cutscene"):
        slides = len(_slide_passages(block))
        if slides == 0:
            blueprint.add_issue(
                block.line,
                f"Cut-scene {block.ref} has no slide: write one line of narration per slide.",
                "warning",
            )
        for index in _image_prompts(block):
            if index >= slides:
                blueprint.add_issue(
                    block.line, f"Cut-scene {block.ref}: image {index + 1} has no slide.", "warning"
                )
