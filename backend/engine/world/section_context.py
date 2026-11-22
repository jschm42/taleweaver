"""World context of the region prompt: one block per context option the author can switch.

The Region Builder lets the author choose which parts of the existing world go into the
prompt of a new region (``off`` / ``compact`` / ``full``). Each option is one block built from
the database; ``section_context_world`` builds the scene, character and item blocks. Turning
an option off only shortens the prompt: validation always checks against the full ledger.
Spec: docs/specs/region_builder.md (section 5).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from backend.engine.world.section_ledger import WorldRows
from backend.engine.world.section_outline import normalize_outline, outline_prompt_block
from backend.engine.world.sections import is_stub

# Prompt order of the switchable blocks (docs/specs/region_builder.md, 7.2).
CONTEXT_OPTIONS = (
    "outline",
    "regions",
    "plot",
    "rules",
    "sequences",
    "quests",
    "scenes",
    "npcs",
    "items",
)
DETAIL_LEVELS = ("off", "compact", "full")
DEFAULT_CONTEXT: dict[str, str] = {
    "outline": "full",
    "regions": "full",
    "plot": "full",
    "rules": "full",
    "sequences": "full",
    "quests": "full",
    "scenes": "compact",
    "npcs": "compact",
    "items": "compact",
}
# A block longer than this is cut with a note.
MAX_BLOCK_CHARS = 24000
_WALKTHROUGH_CHARS = 600


@dataclass
class ContextSource:
    """Everything the blocks are built from."""

    adventure: Any
    section: dict[str, Any]
    sections: list[dict[str, Any]]
    rows: WorldRows
    walkthroughs: bool = True
    start_scene_id: Optional[str] = None


@dataclass
class ContextBlock:
    id: str
    text: str
    count: int = 0
    always: bool = False
    included: bool = True
    detail: str = "full"

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)


def estimate_tokens(text: str) -> int:
    """A rough token count (characters / 4); shown to the author as an estimate."""
    return math.ceil(len(text or "") / 4)


def normalize_context(raw: Any) -> dict[str, Any]:
    """Detail level per option plus ``walkthroughs``; unknown or missing values take the default."""
    data = raw if isinstance(raw, dict) else {}
    context: dict[str, Any] = {
        key: data.get(key) if data.get(key) in DETAIL_LEVELS else default
        for key, default in DEFAULT_CONTEXT.items()
    }
    context["walkthroughs"] = data.get("walkthroughs") is not False
    return context


def clip(text: Any, limit: int) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 3] + "..."


def render(heading: str, entries: list[str]) -> str:
    """The block text: heading plus entries, cut at ``MAX_BLOCK_CHARS``."""
    if not entries:
        return ""
    text = "\n".join([heading, *entries])
    if len(text) <= MAX_BLOCK_CHARS:
        return text
    return text[:MAX_BLOCK_CHARS] + "\n[cut: the list is longer]"


# --- story blocks ----------------------------------------------------------------------------


def _region_line(section: dict[str, Any], detail: str) -> str:
    state = "planned" if is_stub(section) else "built"
    line = f"- {section['id']} {section['label']} [{state}]"
    if detail != "full":
        return line
    text = section["description"] if is_stub(section) else section["summary"]
    brief = (
        f" Brief: {clip(section['brief'], 300)}" if is_stub(section) and section["brief"] else ""
    )
    links = ", ".join(
        link["to_section_id"]
        + (f" ({link['travel_minutes']} min)" if link.get("travel_minutes") else "")
        for link in section["planned_links"]
    )
    tail = f" Links: {links}" if links else ""
    return f"{line}: {clip(text or section['description'], 400)}{brief}{tail}"


def _regions(src: ContextSource, detail: str) -> tuple[str, int]:
    entries = [_region_line(s, detail) for s in src.sections if s["id"] != src.section["id"]]
    return render("OTHER REGIONS:", entries), len(entries)


def _outline(src: ContextSource, _detail: str) -> tuple[str, int]:
    outline = getattr(src.adventure, "world_outline", None)
    if normalize_outline(outline) is None:
        return "", 0
    return outline_prompt_block(outline, src.section["id"]), 1


def _plot(src: ContextSource, _detail: str) -> tuple[str, int]:
    adv = src.adventure
    entries = [
        f"{label}: {value}"
        for label, value in (("Teaser", adv.teaser), ("Plot", adv.plot))
        if (value or "").strip()
    ]
    return render("ADVENTURE PLOT:", entries), len(entries)


def _yes(value: Any) -> str:
    return "yes" if value else "no"


def _rules(src: ContextSource, _detail: str) -> tuple[str, int]:
    adv = src.adventure
    entries = [adv.rules.strip()] if (adv.rules or "").strip() else []
    if (adv.rule_enforcement_mode or "") == "rpg":
        entries.append(
            f"Combat: the player may hurt characters: {_yes(adv.can_damage_npcs)}; "
            f"characters may hurt the player: {_yes(adv.npcs_can_damage_protagonist)}."
        )
    on_zero = (getattr(adv, "game_over_rules", None) or {}).get("on_zero_hp")
    if on_zero:
        entries.append(f"At 0 HP: {on_zero}.")
    return render("WORLD RULES:", entries), len(entries)


def _sequence_line(seq: dict[str, Any], detail: str, walkthroughs: bool) -> str:
    line = f"{seq.get('order')}. {seq.get('title', '')}"
    if detail != "full":
        return line
    line += f": {clip(seq.get('description'), 300)}"
    if seq.get("end_condition"):
        line += f" Ends when: {clip(seq['end_condition'], 200)}"
    if walkthroughs and seq.get("walkthrough"):
        line += f"\n   Walkthrough: {clip(seq['walkthrough'], _WALKTHROUGH_CHARS)}"
    return line


def _order(seq: dict[str, Any]) -> int:
    try:
        return int(seq.get("order") or 0)
    except (TypeError, ValueError):
        return 0


def _sequences(src: ContextSource, detail: str) -> tuple[str, int]:
    chapters = sorted((s for s in src.adventure.sequences or [] if isinstance(s, dict)), key=_order)
    entries = [_sequence_line(s, detail, src.walkthroughs) for s in chapters]
    return render("EXISTING CHAPTERS (new chapters come after them):", entries), len(entries)


_QUEST_REFS = (
    ("required_item_id", "needs item"),
    ("required_scene_id", "at scene"),
    ("required_defeated_npc_id", "defeat"),
    ("section_id", "region"),
)


def _quest_line(quest: dict[str, Any], detail: str) -> str:
    line = f"- {quest.get('id')} {quest.get('title', '')}"
    if detail != "full":
        return line
    refs = "; ".join(f"{label} {quest[key]}" for key, label in _QUEST_REFS if quest.get(key))
    goal = f" Goal: {clip(quest.get('goal'), 160)}" if quest.get("goal") else ""
    return f"{line}: {clip(quest.get('description'), 200)}{goal}" + (f" ({refs})" if refs else "")


def _quests(src: ContextSource, detail: str) -> tuple[str, int]:
    quests = [q for q in src.adventure.quests or [] if isinstance(q, dict)]
    entries = [_quest_line(q, detail) for q in quests]
    return render("EXISTING QUESTS (ids are taken):", entries), len(entries)


def _builders() -> dict[str, Callable[[ContextSource, str], tuple[str, int]]]:
    # Lazy import: the world module imports helpers of this one.
    from backend.engine.world.section_context_world import items_block, npcs_block, scenes_block

    return {
        "outline": _outline,
        "regions": _regions,
        "plot": _plot,
        "rules": _rules,
        "sequences": _sequences,
        "quests": _quests,
        "scenes": scenes_block,
        "npcs": npcs_block,
        "items": items_block,
    }


def option_blocks(src: ContextSource, context: dict[str, Any]) -> list[ContextBlock]:
    """Every option's block in prompt order. An option that is off is built at its default
    detail (so the author sees what it would cost) and marked ``included=False``."""
    builders = _builders()
    blocks = []
    for key in CONTEXT_OPTIONS:
        chosen = context.get(key, DEFAULT_CONTEXT[key])
        detail = DEFAULT_CONTEXT[key] if chosen == "off" else chosen
        text, count = builders[key](src, detail)
        blocks.append(ContextBlock(key, text, count, included=chosen != "off", detail=chosen))
    return blocks
