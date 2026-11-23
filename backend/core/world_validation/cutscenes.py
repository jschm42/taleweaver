"""Cut-scene checks (see backend/engine/cutscenes/library.py).

A chapter's ``start_cutscene_id`` and every literal ``tw.cutscene.play("ID")`` in a script must
name a cut-scene of the library; a cut-scene needs slides and its audio track must exist.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from backend.core.world_validation.context import ValidationContext, finding
from backend.engine.cutscenes.library import cutscene_id_or_none, normalize_cutscenes
from backend.schemas.validation import ValidationFinding

_PLAY_RE = re.compile(r"tw\.cutscenes?\.(?:play|show)\(\s*[\"']([A-Za-z0-9_]+)[\"']")


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _chapter_findings(ctx: ValidationContext, known: set[str]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for seq in ctx.adventure.get("sequences") or []:
        if not isinstance(seq, dict) or not seq.get("start_cutscene_id"):
            continue
        wanted = cutscene_id_or_none(seq["start_cutscene_id"])
        if wanted in known:
            continue
        title = seq.get("title") or seq.get("id")
        findings.append(
            finding(
                "warn",
                "chapter_cutscene_missing",
                f"Chapter '{title}' starts with cut-scene '{seq['start_cutscene_id']}', "
                "which does not exist.",
                location=f"sequence:{seq.get('id')}",
                cutscene_id=seq["start_cutscene_id"],
            )
        )
    return findings


def _library_findings(
    ctx: ValidationContext, cutscenes: list[dict[str, Any]]
) -> list[ValidationFinding]:
    tracks = {
        str(t.get("id")) for t in ctx.adventure.get("audio_tracks") or [] if isinstance(t, dict)
    }
    findings: list[ValidationFinding] = []
    for cutscene in cutscenes:
        location = f"cutscene:{cutscene['id']}"
        if not cutscene["slides"]:
            findings.append(
                finding(
                    "warn",
                    "cutscene_without_slides",
                    f"Cut-scene '{cutscene['id']}' has no slides and is never shown.",
                    location=location,
                )
            )
        track = cutscene["audio_track_id"]
        if track and track not in tracks:
            findings.append(
                finding(
                    "warn",
                    "cutscene_audio_missing",
                    f"Cut-scene '{cutscene['id']}' plays audio track '{track}', which does not exist.",
                    location=location,
                )
            )
    return findings


def _script_findings(ctx: ValidationContext, known: set[str]) -> list[ValidationFinding]:
    unknown = sorted(
        {
            cid
            for text in _strings(ctx.raw)
            if "tw.cutscene" in text
            for cid in _PLAY_RE.findall(text)
            if cutscene_id_or_none(cid) not in known
        }
    )
    return [
        finding(
            "warn",
            "script_cutscene_missing",
            f"A script plays cut-scene '{cid}', which does not exist.",
            cutscene_id=cid,
        )
        for cid in unknown
    ]


def check_cutscene_refs(ctx: ValidationContext) -> list[ValidationFinding]:
    cutscenes = normalize_cutscenes(ctx.adventure.get("cutscenes"))
    known = {c["id"] for c in cutscenes}
    return [
        *_chapter_findings(ctx, known),
        *_library_findings(ctx, cutscenes),
        *_script_findings(ctx, known),
    ]
