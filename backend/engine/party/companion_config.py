"""The authored ``companion`` block of an NPC (``metadata_json["companion"]``).

An NPC with this block can join the protagonist's party. Example::

    "companion": {
        "recruitable": true,
        "starts_in_party": false,
        "tactics": "SUPPORT",
        "banter": "NORMAL",
        "downed_recovery": 0.25,
        "recruit_mode": "ITEM",
        "recruit_item_id": "BOTTLE_OF_RUM",
        "recruit_hint": "Bring me something to drink and I'm yours."
    }

``recruit_mode`` says how the player recruits the NPC: ``SCRIPT`` (default) only through a
script (``tw.party.recruit``), ``INSTANT`` with the NPC's *Recruit* action, ``ITEM`` with the
*Recruit* dialog in which the player offers ``recruit_item_id`` (the NPC keeps it; see
``api/routes/adventures/companion_recruit.py``). ``recruit_hint`` is the dialog's text.
``starts_in_party`` puts it into the party when a session starts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

COMPANION_KEY = "companion"
TACTICS = ("BALANCED", "OFFENSIVE", "DEFENSIVE", "SUPPORT")
BANTER_LEVELS = ("NORMAL", "QUIET", "CHATTY")
DEFAULT_DOWNED_RECOVERY = 0.25
RECRUIT_SCRIPT = "SCRIPT"
RECRUIT_INSTANT = "INSTANT"
RECRUIT_ITEM = "ITEM"
RECRUIT_MODES = (RECRUIT_SCRIPT, RECRUIT_INSTANT, RECRUIT_ITEM)
RECRUIT_HINT_MAX = 300


@dataclass(frozen=True)
class CompanionConfig:
    """Normalized companion settings of one NPC."""

    recruitable: bool = True
    starts_in_party: bool = False
    tactics: str = TACTICS[0]
    banter: str = BANTER_LEVELS[0]
    downed_recovery: float = DEFAULT_DOWNED_RECOVERY
    recruit_mode: str = RECRUIT_SCRIPT
    recruit_item_id: str = ""
    recruit_hint: str = ""

    @property
    def player_recruitable(self) -> bool:
        """The player can recruit it with the Recruit action (not only a script)."""
        return self.recruitable and self.recruit_mode != RECRUIT_SCRIPT

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
        **_recruit_fields(raw),
    )
    return config.to_dict()


def _recruit_fields(raw: dict[str, Any]) -> dict[str, str]:
    """Recruit mode, item and hint; ITEM without an item falls back to INSTANT."""
    item_id = str(raw.get("recruit_item_id") or "").strip().upper()
    mode = _choice(raw.get("recruit_mode"), RECRUIT_MODES)
    if mode == RECRUIT_ITEM and not item_id:
        mode = RECRUIT_INSTANT
    hint = str(raw.get("recruit_hint") or "").strip()[:RECRUIT_HINT_MAX]
    return {
        "recruit_mode": mode,
        "recruit_item_id": item_id if mode == RECRUIT_ITEM else "",
        "recruit_hint": hint,
    }


def companion_config(metadata: Any) -> Optional[CompanionConfig]:
    """The companion settings stored in an NPC's metadata, or ``None`` for ordinary NPCs."""
    if not isinstance(metadata, dict):
        return None
    normalized = normalize_companion(metadata.get(COMPANION_KEY))
    if normalized is None:
        return None
    return CompanionConfig(**normalized)
