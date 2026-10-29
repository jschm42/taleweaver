"""Resolves where (initial scene) and when (in-game start datetime) a new session begins."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from backend.engine.sessions.start_scene import resolve_initial_scene_id
from backend.models.session_state import SessionState

__all__ = ["resolve_initial_scene_id", "resolve_start_datetime"]

logger = logging.getLogger(__name__)

_RELATIVE_TIME_SYSTEMS = ("relative", "units")
_DEFAULT_START_TIME = "08:00"
_DEFAULT_START_HOUR_MINUTE = (8, 0)
_DEFAULT_START_YEAR = 2026


def _parse_iso(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _merged_time_config(manifest: dict[str, Any], time_config: Optional[dict]) -> dict[str, Any]:
    """Editor time_config wins over manifest defaults so the world editor can set the start."""
    merged = dict(time_config or {})
    manifest_time_config = manifest.get("time_config")
    if isinstance(manifest_time_config, dict):
        for key, value in manifest_time_config.items():
            merged.setdefault(key, value)
    return merged


def _from_date_and_time(config: dict[str, Any], manifest: dict[str, Any]) -> Optional[str]:
    start_date = config.get("start_date") or manifest.get("start_date")
    if not isinstance(start_date, str) or not start_date.strip():
        return None
    start_time = config.get("start_time") or manifest.get("start_time")
    has_time = isinstance(start_time, str) and start_time.strip()
    time_part = start_time.strip() if has_time else _DEFAULT_START_TIME
    return _parse_iso(f"{start_date.strip()}T{time_part}")


def _hour_minute(configured_start: Any) -> tuple[int, int]:
    if not isinstance(configured_start, str) or not configured_start.strip():
        return _DEFAULT_START_HOUR_MINUTE
    try:
        hour, minute = map(int, configured_start.strip().split(":"))
    except ValueError:
        logger.debug("Ignoring malformed start_time %r", configured_start)
        return _DEFAULT_START_HOUR_MINUTE
    return hour, minute


def _from_time_and_year(config: dict[str, Any]) -> Optional[str]:
    """Builds Jan 1st of the (overridden) year at ``start_time`` (e.g. "14:30")."""
    configured_start = config.get("start_time")
    year_override = config.get("start_year_override")
    if not configured_start and not year_override:
        return None
    hour, minute = _hour_minute(configured_start)
    try:
        year = int(year_override) if year_override else _DEFAULT_START_YEAR
        return datetime(year=year, month=1, day=1, hour=hour, minute=minute).isoformat()
    except (TypeError, ValueError):
        return None


def resolve_start_datetime(
    manifest: Optional[dict[str, Any]],
    state: Optional[SessionState] = None,
    time_config: Optional[dict] = None,
) -> Optional[str]:
    """Returns a usable ISO datetime string. Prioritizes session-specific state over manifest."""
    if state and state.start_datetime:
        return state.start_datetime

    target_manifest = manifest or {}
    config = _merged_time_config(target_manifest, time_config)
    time_system = config.get("time_system") or target_manifest.get("time_system")
    if time_system in _RELATIVE_TIME_SYSTEMS:
        return None
    return (
        _parse_iso(config.get("start_datetime"))
        or _parse_iso(target_manifest.get("start_datetime"))
        or _from_date_and_time(config, target_manifest)
        or _from_time_and_year(config)
    )
