"""The protagonist's talents and companion as the play-agent sees them.

A human player uses talents from the Talents menu and steers the companion from the hero
dialog. The play-agent only types, so this block lists what it can use and the exact
commands those widgets send (``/talent``, ``/companion ...``). It shows the same data as the
player's UI: unlocked talents only, and the active companion's sheet.
"""

from __future__ import annotations

from typing import Any

from backend.engine.rules.talents import availability_problem, normalize_talents, uses_left

TALENT_USAGE = "Use a talent with `/talent <name>` or `/talent <name> | <target>`."
COMPANION_USAGE = (
    "Companion commands: `/companion wait` (stay here), `/companion follow` (come along), "
    "`/companion_give <item>[, <item>]`, `/companion_take <item>[, <item>]`, "
    "`/companion_equip <item>`, `/companion_unequip <slot>`, "
    "`/companion_ability <ability> on|off`."
)


def _talent_line(talent: dict[str, Any], stats: dict[str, Any], avatar: Any) -> str:
    pool = int(getattr(avatar, talent["cost_type"], 0) or 0)
    parts = [f"costs {talent['cost']} {talent['cost_type']}"]
    if talent.get("target_type") and talent["target_type"] != "NONE":
        parts.append(f"target: {talent['target_type'].lower()}")
    left = uses_left(talent, stats.get("talent_uses") or {})
    if left is not None:
        parts.append(f"{left} uses left")
    problem = availability_problem(talent, stats, pool)
    if problem:
        parts.append(f"NOT USABLE NOW: {problem}")
    description = " ".join(str(talent.get("description") or "").split())
    suffix = f" - {description}" if description else ""
    return f"- {talent['name']} ({', '.join(parts)}){suffix}"


def format_talents(avatar: Any) -> str:
    """Unlocked talents with cost, target and remaining uses; empty without talents."""
    stats = getattr(avatar, "stats", None) or {}
    unlocked = set(stats.get("unlocked_talents") or [])
    talents = [t for t in normalize_talents(stats.get("talents")) if t["id"] in unlocked]
    if not talents:
        return ""
    lines = [_talent_line(talent, stats, avatar) for talent in talents]
    return "YOUR TALENTS:\n" + "\n".join(lines) + "\n" + TALENT_USAGE


def _item_names(items: list[dict[str, Any]] | None) -> str:
    names = [str(i.get("name")) for i in items or [] if isinstance(i, dict) and i.get("name")]
    return ", ".join(names) or "nothing"


def _whereabouts(sheet: dict[str, Any]) -> str:
    if sheet.get("is_defeated"):
        return "is defeated and cannot act"
    if not sheet.get("present"):
        return "is NOT here (it waits elsewhere; go back to fetch it)"
    return "is here and follows you" if sheet.get("following") else "is here but waits"


def format_companion(sheet: dict[str, Any] | None) -> str:
    """The active companion: where it is, what it carries and its combat abilities."""
    if not sheet:
        return ""
    equipped = {slot: item for slot, item in (sheet.get("equipment") or {}).items() if item}
    gear = ", ".join(f"{slot}: {item.get('name')}" for slot, item in equipped.items()) or "none"
    abilities = ", ".join(
        f"{a['name']} ({'on' if a.get('enabled') else 'off'})" for a in sheet.get("abilities") or []
    )
    lines = [
        f"YOUR COMPANION: {sheet.get('name')} {_whereabouts(sheet)}.",
        f"HP: {sheet.get('hp')}/{sheet.get('max_hp')} | Carries: {_item_names(sheet.get('inventory'))}"
        f" | Equipped: {gear}",
    ]
    if abilities:
        lines.append(f"Combat abilities: {abilities}")
    lines.append(COMPANION_USAGE)
    return "\n".join(lines)


async def format_abilities_and_party(db: Any, state: Any, avatar: Any) -> str:
    """The talents and companion blocks for the agent prompt."""
    # companion_sheet imports the sheet snapshot, which imports the agent modules.
    from backend.api.routes.adventures.companion_sheet import build_companion_sheet

    companion = await build_companion_sheet(db, state, {})
    blocks = [format_talents(avatar), format_companion(companion)]
    return "\n\n".join(b for b in blocks if b) or "No talents and no companion."
