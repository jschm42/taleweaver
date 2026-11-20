"""``tw.game`` fast travel calls (mixed into ``GameProxy``).

The calls only record ordered ``ScriptChangeset.travel_ops``; every changeset applier replays
them with ``engine/rules/fast_travel.apply_travel_ops``. Reads include this script's own
changes.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.rules.fast_travel import TRAVEL_KEY, apply_travel_ops, read_travel


class FastTravelMixin:
    """Fast travel points and the fast travel switch of ``tw.game``."""

    _changeset: Any
    _travel_record: Optional[dict[str, Any]] = None

    def _init_travel(self, record: Optional[dict[str, Any]]) -> None:
        self._travel_record = record if isinstance(record, dict) else None

    def _current_travel(self) -> dict[str, Any]:
        states: dict[str, Any] = {}
        if self._travel_record is not None:
            states[TRAVEL_KEY] = self._travel_record
        apply_travel_ops(states, self._changeset.travel_ops)
        return read_travel(states)

    @property
    def fast_travel_points(self) -> list[str]:
        """Scene ids of the unlocked fast travel points."""
        return list(self._current_travel()["unlocked"])

    @property
    def fast_travel_enabled(self) -> bool:
        """False while a script switched fast travel off (the adventure setting is separate)."""
        return not self._current_travel()["disabled"]

    def unlock_fast_travel(self, scene_id: str) -> None:
        """Makes a fast travel point a destination (the scene must be marked as one)."""
        self._changeset.travel_ops.append({"op": "unlock", "scene_id": str(scene_id or "")})

    def lock_fast_travel(self, scene_id: str) -> None:
        """Removes a fast travel point from the destinations again."""
        self._changeset.travel_ops.append({"op": "lock", "scene_id": str(scene_id or "")})

    def set_fast_travel(self, enabled: bool, reason: Optional[str] = None) -> None:
        """Switches fast travel off (with the reason players see) or on again."""
        self._changeset.travel_ops.append(
            {"op": "enable", "enabled": bool(enabled), "reason": str(reason or "")}
        )
