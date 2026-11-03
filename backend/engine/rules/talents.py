"""Protagonist talents: non-combat abilities such as Mind Reading or a Gossip Attack.

Stored in ``avatar.stats``:

* ``talents``: list of talent definitions (see ``TalentSchema``).
* ``unlocked_talents``: IDs the player may use (locked talents join via unlock rules).
* ``talent_uses``: ``{talent_id: times used}`` for the ``max_uses`` limit (per adventure).

The player triggers a talent by typing ``use <talent> [on <target>]`` / ``cast <talent> ...``
or with the ``/talent <id or name> [| <target>]`` command that the Talents menu sends.
Typed text only counts as a talent use when it names a known talent, so "use the key on the
door" stays a normal Game Master turn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

TALENT_COMMAND = "/talent"
TARGET_TYPES = ("NONE", "NPC", "ITEM", "ANY")
COST_TYPES = ("mana", "stamina")
MAX_TALENTS = 8
MAX_TALENT_COST = 999

_TYPED_VERBS = re.compile(
    r"^\s*(?:i\s+)?(?:use|cast|activate|invoke|perform)\s+(?:my\s+|the\s+)?(?P<rest>.+?)[\s.!]*$",
    re.I,
)
_TARGET_PREPOSITIONS = r"(?:on|at|against|upon|to|onto|toward|towards)"
_ARTICLE = re.compile(r"^(?:the|a|an|my|this|that)\s+", re.I)


@dataclass(frozen=True)
class TalentRequest:
    """A recognised talent use: the stored definition and the raw target text."""

    talent: Optional[dict[str, Any]]
    target_hint: str = ""
    query: str = ""  # what the player named, for "unknown talent" messages


def _int_or(value: Any, fallback: Optional[int]) -> Optional[int]:
    if isinstance(value, bool):
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def normalize_talent(raw: Any) -> Optional[dict[str, Any]]:
    """A talent definition with defaults filled in, or None when it is unusable."""
    if not isinstance(raw, dict):
        return None
    talent_id = str(raw.get("id") or "").strip().upper()
    if not talent_id:
        return None
    target_type = str(raw.get("target_type") or "").strip().upper()
    cost_type = str(raw.get("cost_type") or "").strip().lower()
    max_uses = _int_or(raw.get("max_uses"), None)
    return {
        **raw,
        "id": talent_id,
        "name": str(raw.get("name") or talent_id).strip(),
        "description": str(raw.get("description") or "").strip(),
        "target_type": target_type if target_type in TARGET_TYPES else "NONE",
        "cost_type": cost_type if cost_type in COST_TYPES else "mana",
        "cost": max(0, min(MAX_TALENT_COST, _int_or(raw.get("cost"), 0) or 0)),
        "max_uses": max_uses if max_uses and max_uses > 0 else None,
    }


def normalize_talents(raw: Any) -> list[dict[str, Any]]:
    talents = [normalize_talent(entry) for entry in (raw if isinstance(raw, list) else [])]
    return [talent for talent in talents if talent]


def _labels(talent: dict[str, Any]) -> list[str]:
    labels = {talent["name"], talent["id"], talent["id"].replace("_", " ")}
    return sorted((label for label in labels if label), key=len, reverse=True)


def _strip_article(text: str) -> str:
    return _ARTICLE.sub("", text.strip()).strip()


def _match_label(label: str, rest: str) -> Optional[str]:
    """Target text after ``label`` ("" when there is none), or None when ``rest`` is not it."""
    pattern = re.compile(
        rf"^{re.escape(label)}(?:\s+(?:{_TARGET_PREPOSITIONS}\s+)?(?P<target>.+))?$", re.I
    )
    match = pattern.match(rest.strip())
    if not match:
        return None
    return _strip_article(match.group("target") or "")


def match_talent(talents: list[dict[str, Any]], text: str) -> Optional[TalentRequest]:
    """The talent named at the start of ``text`` (longest name wins) plus the target text."""
    candidates = sorted(
        ((label, talent) for talent in talents for label in _labels(talent)),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    for label, talent in candidates:
        target = _match_label(label, text)
        if target is not None:
            return TalentRequest(talent, target, label)
    return None


def parse_talent_command(talents: list[dict[str, Any]], user_msg: str) -> Optional[TalentRequest]:
    """``/talent <id or name> [| <target>]`` -> request (talent None when unknown)."""
    text = (user_msg or "").strip()
    head, _, args = text.partition(" ")
    if head.lower() != TALENT_COMMAND:
        return None
    name_part, _, target_part = args.partition("|")
    query = name_part.strip()
    target = _strip_article(target_part)
    key = query.lower().replace("_", " ")
    talent = next(
        (t for t in talents if key in (t["name"].lower(), t["id"].lower().replace("_", " "))),
        None,
    )
    if talent is None and query and not target_part:
        found = match_talent(talents, query)
        if found:
            return found
    return TalentRequest(talent, target, query)


def parse_typed_talent(talents: list[dict[str, Any]], user_msg: str) -> Optional[TalentRequest]:
    """``use <talent> [on <target>]`` / ``cast ...`` naming a known talent, else None."""
    match = _TYPED_VERBS.match(user_msg or "")
    if not match or not talents:
        return None
    return match_talent(talents, match.group("rest"))


def uses_left(talent: dict[str, Any], uses: dict[str, Any]) -> Optional[int]:
    """Remaining uses per adventure, or None for unlimited."""
    if not talent.get("max_uses"):
        return None
    used = _int_or(uses.get(talent["id"]), 0) or 0
    return max(0, int(talent["max_uses"]) - used)


def availability_problem(talent: dict[str, Any], stats: dict[str, Any], pool: int) -> str | None:
    """Why the talent cannot be used right now, or None when it can."""
    name = talent["name"]
    if talent["id"] not in set(stats.get("unlocked_talents") or []):
        return f"You have not unlocked {name} yet."
    if uses_left(talent, stats.get("talent_uses") or {}) == 0:
        return f"You have used up {name} for this adventure."
    if pool < talent["cost"]:
        return (
            f"Not enough {talent['cost_type']} for {name} "
            f"(needs {talent['cost']}, you have {pool})."
        )
    return None
