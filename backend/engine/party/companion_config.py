"""The authored ``companion`` block of an NPC (``metadata_json["companion"]``).

An NPC with this block can join the protagonist's party. Example::

    "companion": {
        "recruitable": true,
        "starts_in_party": false,
        "tactics": "SUPPORT",
        "banter": "NORMAL",
        "downed_recovery": 0.25
    }

Recruiting is always done by a script (``tw.party.recruit``); ``recruitable`` only marks
the NPC as a companion. ``starts_in_party`` puts it into the party when a session starts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

COMPANION_KEY = "companion"
TACTICS = ("BALANCED", "OFFENSIVE", "DEFENSIVE", "SUPPORT")
BANTER_LEVELS = ("NORMAL", "QUIET", "CHATTY")
DEFAULT_DOWNED_RECOVERY = 0.25


@dataclass(frozen=True)
class CompanionConfig:
    """Normalized companion settings of one NPC."""

    recruitable: bool = True
    starts_in_party: bool = False
    tactics: str = TACTICS[0]
    banter: str = BANTER_LEVELS[0]
    downed_recovery: float = DEFAULT_DOWNED_RECOVERY

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _choice(raw: Any, allowed: tuple[str, ...]) -> str:
    value = str(raw or "").strip().upper()
    return value if value in allowed else allowed[0]


def _ratio(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_DOWNED_RECOVERY
    if value > 1:
        # Authors may write percent values ("25").
        value /= 100
    return min(1.0, max(0.01, value))


def normalize_companion(raw: Any) -> Optional[dict[str, Any]]:
    """Normalizes a ``companion`` block; ``None``/``False``/empty means "not a companion".

    ``True`` is accepted as shorthand for a recruitable companion with default settings.
    """
    if raw is True:
        return CompanionConfig().to_dict()
    if not isinstance(raw, dict) or not raw:
        return None
    config = CompanionConfig(
        recruitable=bool(raw.get("recruitable", True)),
        starts_in_party=bool(raw.get("starts_in_party", False)),
        tactics=_choice(raw.get("tactics"), TACTICS),
        banter=_choice(raw.get("banter"), BANTER_LEVELS),
        downed_recovery=_ratio(raw.get("downed_recovery", DEFAULT_DOWNED_RECOVERY)),
    )
    return config.to_dict()


def companion_config(metadata: Any) -> Optional[CompanionConfig]:
    """The companion settings stored in an NPC's metadata, or ``None`` for ordinary NPCs."""
    if not isinstance(metadata, dict):
        return None
    normalized = normalize_companion(metadata.get(COMPANION_KEY))
    if normalized is None:
        return None
    return CompanionConfig(**normalized)
