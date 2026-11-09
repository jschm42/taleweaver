"""CSV / JSON import and export of the voice mapping table (see ``voice_provider_map``).

A file has one row per list voice: ``name``, ``description`` (informational), ``elevenlabs_id``,
``google_voice`` and ``openai_compatible_voice``. Import matches rows by ElevenLabs id, else by
name; an empty cell means the narrator voice. CSV files may use ``,``, ``;`` or tabs (spreadsheet
exports), JSON files hold ``{"voices": [...]}`` or a plain list of rows.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from backend.engine.audio.voice_provider_map import (
    COMPATIBLE_PROVIDER,
    GOOGLE_PROVIDER,
    VoiceMapError,
    clean_provider_voice,
)

JSON_FORMAT_ID: Final = "taleweaver-voice-map"
MAX_IMPORT_CHARS: Final = 1_000_000
# File column -> provider key of the mapping table.
PROVIDER_COLUMNS: Final = {
    "google_voice": GOOGLE_PROVIDER,
    "openai_compatible_voice": COMPATIBLE_PROVIDER,
}
CSV_COLUMNS: Final = ("name", "description", "elevenlabs_id", *PROVIDER_COLUMNS)


@dataclass
class ImportResult:
    rows: list[dict[str, Any]]
    matched: int = 0
    unknown: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _file_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "name": str(row.get("name") or ""),
        "description": str(row.get("description") or ""),
        "elevenlabs_id": str(row.get("elevenlabs") or row.get("id") or ""),
        **{column: str(row.get(provider) or "") for column, provider in PROVIDER_COLUMNS.items()},
    }


def export_csv(rows: list[Mapping[str, Any]]) -> str:
    """The table as CSV with a BOM, so spreadsheet apps read the names as UTF-8."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(_file_row(row) for row in rows)
    return "﻿" + buffer.getvalue()


def export_json(rows: list[Mapping[str, Any]]) -> str:
    payload = {"format": JSON_FORMAT_ID, "version": 1, "voices": [_file_row(r) for r in rows]}
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _key(value: object) -> str:
    return str(value or "").strip().lower()


def _header_key(value: object) -> str:
    return _key(value).replace(" ", "_").replace("-", "_")


def _parse_csv(content: str) -> list[dict[str, Any]]:
    sample = content[:4096]
    try:
        dialect: Any = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    return [{_header_key(k): v for k, v in row.items() if k} for row in reader]


def _parse_json(content: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(content)
    except ValueError as exc:
        raise VoiceMapError(f"The file is not valid JSON ({exc.msg}).") from None
    rows = data.get("voices") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise VoiceMapError("The JSON file needs a 'voices' list.")
    return [{_header_key(k): v for k, v in row.items()} for row in rows if isinstance(row, dict)]


def parse_import(content: str, file_format: str) -> list[dict[str, Any]]:
    """Rows of an import file; raises ``VoiceMapError`` for unreadable files."""
    text = content.lstrip("﻿")
    if len(text) > MAX_IMPORT_CHARS:
        raise VoiceMapError("The file is too large.")
    if not text.strip():
        raise VoiceMapError("The file is empty.")
    return _parse_json(text) if file_format == "json" else _parse_csv(text)


def _find_row(
    imported: Mapping[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    list_id = str(imported.get("elevenlabs_id") or imported.get("id") or "").strip()
    return by_id.get(list_id) or by_name.get(_key(imported.get("name")))


def _apply_cells(target: dict[str, Any], imported: Mapping[str, Any], errors: list[str]) -> None:
    for column, provider in PROVIDER_COLUMNS.items():
        if column not in imported:
            continue
        try:
            target[provider] = clean_provider_voice(provider, imported.get(column))
        except VoiceMapError as exc:
            errors.append(f"{target['name']}: {exc}")


def merge_import(
    table: list[dict[str, Any]], imported_rows: list[Mapping[str, Any]]
) -> ImportResult:
    """The current table with the imported cells laid over it (nothing is saved here).

    Columns missing from the file keep their current values; invalid cells are skipped and listed.
    """
    rows = [dict(row) for row in table]
    by_id = {row["id"]: row for row in rows}
    by_name = {_key(row["name"]): row for row in rows}
    result = ImportResult(rows=rows)
    for imported in imported_rows:
        target = _find_row(imported, by_id, by_name)
        if target is None:
            label = imported.get("name") or imported.get("elevenlabs_id") or "?"
            result.unknown.append(str(label))
            continue
        result.matched += 1
        _apply_cells(target, imported, result.errors)
    return result


__all__ = [
    "CSV_COLUMNS",
    "ImportResult",
    "export_csv",
    "export_json",
    "merge_import",
    "parse_import",
]
