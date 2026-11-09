"""Admin table of per-provider voice ids for the voice list (``voice_provider_map``).

Rows are the voices of the voice list; admins fill in the Google TTS and OpenAI-compatible voice
for each. Import only fills the table (the admin then saves), export returns the file content.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_admin
from backend.core.database import get_db
from backend.core.global_settings import get_server_settings_for_update, read_server_settings
from backend.core.tts_voices import GOOGLE_TTS_VOICE_CATALOG
from backend.engine.audio.elevenlabs_voices import load_voice_catalog
from backend.engine.audio.voice_map_transfer import (
    export_csv,
    export_json,
    merge_import,
    parse_import,
)
from backend.engine.audio.voice_provider_map import (
    MAX_VOICE_ID_CHARS,
    VoiceMapError,
    build_voice_map,
    effective_voice_map,
    mapping_rows,
)
from backend.models.user import User

router = APIRouter(prefix="/settings/voice-map", tags=["Settings"])

FileFormat = Literal["csv", "json"]


class VoiceMapRowPayload(BaseModel):
    id: str = Field(max_length=64)
    name: Optional[str] = Field(default=None, max_length=200)
    google: Optional[str] = Field(default=None, max_length=MAX_VOICE_ID_CHARS)
    custom_openai: Optional[str] = Field(default=None, max_length=MAX_VOICE_ID_CHARS)


class VoiceMapPayload(BaseModel):
    items: list[VoiceMapRowPayload] = Field(max_length=2000)


class VoiceMapImportPayload(BaseModel):
    content: str
    format: FileFormat = "csv"
    # The table as currently edited in the dialog (else the saved one).
    items: Optional[list[VoiceMapRowPayload]] = Field(default=None, max_length=2000)


class VoiceMapExportPayload(BaseModel):
    format: FileFormat = "csv"
    items: Optional[list[VoiceMapRowPayload]] = Field(default=None, max_length=2000)


async def _saved_rows(db: AsyncSession) -> list[dict[str, Any]]:
    server = await read_server_settings(db)
    voices = load_voice_catalog()
    return mapping_rows(voices, effective_voice_map(server.voice_provider_map, voices))


def _rows_with_edits(
    saved: list[dict[str, Any]], items: list[VoiceMapRowPayload]
) -> list[dict[str, Any]]:
    """The saved table with the dialog's unsaved cells (unknown rows are ignored)."""
    edits = {item.id: item for item in items}
    return [_with_edit(row, edits.get(row["id"])) for row in saved]


def _with_edit(row: dict[str, Any], edit: Optional[VoiceMapRowPayload]) -> dict[str, Any]:
    if edit is None:
        return row
    return {**row, "google": edit.google or "", "custom_openai": edit.custom_openai or ""}


async def _current_rows(
    db: AsyncSession, items: Optional[list[VoiceMapRowPayload]]
) -> list[dict[str, Any]]:
    saved = await _saved_rows(db)
    return _rows_with_edits(saved, items) if items is not None else saved


@router.get("")
async def get_voice_map(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """The table rows plus the Google voices a cell may hold."""
    _ = current_admin
    return {"items": await _saved_rows(db), "google_voices": GOOGLE_TTS_VOICE_CATALOG}


@router.put("")
async def update_voice_map(
    payload: VoiceMapPayload,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Replaces the mapping; empty cells mean the narrator voice."""
    _ = current_admin
    voices = load_voice_catalog()
    try:
        voice_map, _unknown = build_voice_map(
            [item.model_dump() for item in payload.items], {v["id"] for v in voices}
        )
    except VoiceMapError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    server = await get_server_settings_for_update(db)
    server.voice_provider_map = voice_map
    await db.commit()
    return {"status": "success", "items": mapping_rows(voices, voice_map)}


@router.post("/import")
async def import_voice_map(
    payload: VoiceMapImportPayload,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Lays an import file over the table and returns it for review; nothing is saved."""
    _ = current_admin
    try:
        imported = parse_import(payload.content, payload.format)
    except VoiceMapError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    result = merge_import(await _current_rows(db, payload.items), imported)
    return {
        "items": result.rows,
        "matched": result.matched,
        "unknown": result.unknown,
        "errors": result.errors,
    }


@router.post("/export")
async def export_voice_map(
    payload: VoiceMapExportPayload,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict[str, str]:
    """The table as file content (the client saves it as ``filename``)."""
    _ = current_admin
    rows = await _current_rows(db, payload.items)
    if payload.format == "json":
        return {"filename": "taleweaver_voice_map.json", "content": export_json(rows)}
    return {"filename": "taleweaver_voice_map.csv", "content": export_csv(rows)}
