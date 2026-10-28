"""Session-owned copy of the adventure a session was started from.

A running session never reads the live ``AdventureTemplate``: the template's columns and its
``original_manifest`` (scripts, init_script, sequences, ...) are copied into the session state at
session start (``SESSION_MANIFEST_SNAPSHOT_KEY``). Later template edits, re-imports or the
template's deletion therefore never change a session.

Sessions started before the snapshot held every column are completed once from the template
while it still exists; from then on they are frozen as well.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState

logger = logging.getLogger(__name__)

SESSION_MANIFEST_SNAPSHOT_KEY = "__manifest_snapshot__"

# Generation logs are large and never used at play time; the manifest is stored on its own.
_EXCLUDED_COLUMNS = frozenset({"generation_logs", "original_manifest"})


def _column_keys() -> list[str]:
    return [
        attr.key
        for attr in sa_inspect(AdventureTemplate).column_attrs
        if attr.key not in _EXCLUDED_COLUMNS
    ]


def _column_defaults() -> dict[str, Any]:
    """Scalar column defaults, used for snapshot keys a deleted template can no longer supply."""
    defaults: dict[str, Any] = {}
    for attr in sa_inspect(AdventureTemplate).column_attrs:
        default = attr.columns[0].default
        if default is not None and default.is_scalar:
            defaults[attr.key] = default.arg
    return defaults


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return deepcopy(value)


def template_columns(adventure: AdventureTemplate) -> dict[str, Any]:
    """Every play-relevant template column as JSON-safe data."""
    return {key: _json_safe(getattr(adventure, key, None)) for key in _column_keys()}


def build_session_snapshot(adventure: Optional[AdventureTemplate]) -> dict[str, Any]:
    """The full adventure copy stored in a new session's state."""
    if not adventure:
        return {}
    return {
        "adventure": {**template_columns(adventure), "is_ready": True, "creation_status": "Ready"},
        "original_manifest": deepcopy(adventure.original_manifest or {}),
    }


def extract_snapshot(state: Optional[SessionState]) -> dict[str, Any]:
    raw = getattr(state, "entity_states", None)
    if not isinstance(raw, dict):
        return {}
    snapshot = raw.get(SESSION_MANIFEST_SNAPSHOT_KEY)
    return snapshot if isinstance(snapshot, dict) else {}


def _needs_backfill(snapshot: dict[str, Any]) -> bool:
    adventure = snapshot.get("adventure")
    if not isinstance(adventure, dict) or "original_manifest" not in snapshot:
        return True
    return any(key not in adventure for key in _column_keys())


def _store_snapshot(state: SessionState, snapshot: dict[str, Any]) -> None:
    entity_states = dict(state.entity_states or {})
    entity_states[SESSION_MANIFEST_SNAPSHOT_KEY] = snapshot
    state.entity_states = entity_states
    flag_modified(state, "entity_states")


def _backfill(state: SessionState, snapshot: dict[str, Any], template: AdventureTemplate) -> dict:
    """Completes an older snapshot from the template; values the session already has win."""
    existing = snapshot.get("adventure") if isinstance(snapshot.get("adventure"), dict) else {}
    manifest = snapshot.get("original_manifest")
    completed = {
        "adventure": {**template_columns(template), **existing},
        "original_manifest": manifest
        if isinstance(manifest, dict)
        else deepcopy(template.original_manifest or {}),
    }
    _store_snapshot(state, completed)
    logger.info("[SessionAdventure] Completed adventure snapshot for session %s", state.session_id)
    return completed


def _state_fallbacks(state: SessionState) -> dict[str, Any]:
    """Session values for keys an old snapshot of a deleted template does not have."""
    session = getattr(state, "session", None)
    return {
        "id": state.template_id or "deleted-template",
        "title": getattr(session, "adventure_title", None) or "Deleted Adventure",
        "image_url": getattr(session, "adventure_image_url", None),
        "quests": state.quests or [],
        "plot": state.plot,
        "rules": state.rules,
        "completed_condition": state.completed_condition,
        "gameover_condition": state.gameover_condition,
        "tts_director_notes": state.tts_director_notes,
        "allow_dynamic_items": False,
    }


class SessionAdventure:
    """Read-only, attribute-style view of a session's adventure snapshot.

    Mirrors the ``AdventureTemplate`` attributes the game loop uses, including the manifest-backed
    ``scripts`` and ``init_script`` properties.
    """

    def __init__(self, adventure: dict[str, Any], manifest: dict[str, Any]):
        self._data = adventure
        self.original_manifest = manifest

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        data = self.__dict__.get("_data") or {}
        if name in data:
            return data[name]
        # A template column the snapshot lacks (old session of a deleted template): unset.
        if name in _column_keys():
            return None
        raise AttributeError(name)

    @property
    def scripts(self) -> list[dict[str, Any]]:
        scripts = self.original_manifest.get("scripts")
        return scripts if isinstance(scripts, list) else []

    @property
    def init_script(self) -> Optional[str]:
        return self.original_manifest.get("init_script")


def session_adventure_from_snapshot(
    state: SessionState, snapshot: dict[str, Any]
) -> Optional[SessionAdventure]:
    adventure = snapshot.get("adventure") if isinstance(snapshot.get("adventure"), dict) else {}
    manifest = snapshot.get("original_manifest")
    manifest = manifest if isinstance(manifest, dict) else {}
    if not adventure and not manifest:
        return None
    data = {**_column_defaults(), **_state_fallbacks(state)}
    data.update({key: value for key, value in adventure.items() if value is not None})
    return SessionAdventure(data, manifest)


async def load_session_adventure(
    db: AsyncSession, state: Optional[SessionState]
) -> Optional[SessionAdventure]:
    """The session's own adventure copy; never the live template once the snapshot is complete."""
    if state is None:
        return None
    snapshot = extract_snapshot(state)
    if _needs_backfill(snapshot) and state.template_id:
        template = await db.get(AdventureTemplate, state.template_id)
        if template is not None:
            snapshot = _backfill(state, snapshot, template)
    return session_adventure_from_snapshot(state, snapshot)
