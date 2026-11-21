"""The campaign outline: the plan that keeps generated regions consistent with each other.

Stored in ``AdventureTemplate.world_outline``. Text only and cheap to write, it is what lets
the first region plant what a later region needs::

    {
      "premise": "...",
      "arc": ["act 1 ...", "act 2 ..."],
      "sections": [{"id", "purpose", "gating", "plants": [...], "resolves": [...]}],
      "threads": [{"id", "opened_in", "resolved_in", "status": "open|resolved", "note"}]
    }

Region generation reads it (``section_prompt.py``) and updates thread status afterwards.
Spec: docs/specs/world_sections.md (9.1).
"""

from __future__ import annotations

from typing import Any

from backend.engine.world.sections import section_id_or_none

THREAD_STATUSES = ("open", "resolved")
MAX_TEXT = 2000
MAX_ITEMS = 24
MAX_ITEM_TEXT = 300


def _text(raw: Any, limit: int = MAX_TEXT) -> str:
    return str(raw or "").strip()[:limit]


def _texts(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [t for t in (_text(v, MAX_ITEM_TEXT) for v in raw) if t][:MAX_ITEMS]


def _section_plan(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not section_id_or_none(raw.get("id")):
        return None
    return {
        "id": section_id_or_none(raw.get("id")),
        "purpose": _text(raw.get("purpose"), MAX_ITEM_TEXT),
        "gating": _text(raw.get("gating"), MAX_ITEM_TEXT),
        "plants": _texts(raw.get("plants")),
        "resolves": _texts(raw.get("resolves")),
    }


def _thread(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not section_id_or_none(raw.get("id")):
        return None
    status = str(raw.get("status") or "open").strip().lower()
    return {
        "id": section_id_or_none(raw.get("id")),
        "opened_in": section_id_or_none(raw.get("opened_in")),
        "resolved_in": section_id_or_none(raw.get("resolved_in")),
        "status": status if status in THREAD_STATUSES else "open",
        "note": _text(raw.get("note"), MAX_ITEM_TEXT),
    }


def _unique(entries: list[Any]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry and entry["id"] not in seen:
            seen[entry["id"]] = entry
    return list(seen.values())[:MAX_ITEMS]


def normalize_outline(raw: Any) -> dict[str, Any] | None:
    """The canonical outline, or None when it holds nothing."""
    if not isinstance(raw, dict):
        return None
    outline = {
        "premise": _text(raw.get("premise")),
        "arc": _texts(raw.get("arc")),
        "sections": _unique([_section_plan(s) for s in raw.get("sections") or []]),
        "threads": _unique([_thread(t) for t in raw.get("threads") or []]),
    }
    return outline if any(outline.values()) else None


def apply_thread_updates(outline: Any, updates: Any) -> dict[str, Any] | None:
    """Merges thread updates (new threads, status changes) reported by a region generation."""
    current = normalize_outline(outline) or {
        "premise": "",
        "arc": [],
        "sections": [],
        "threads": [],
    }
    threads = {t["id"]: t for t in current["threads"]}
    for raw in updates if isinstance(updates, list) else []:
        update = _thread(raw)
        if update is None:
            continue
        known = threads.get(update["id"])
        threads[update["id"]] = (
            {**known, **{k: v for k, v in update.items() if v}} if known else update
        )
    current["threads"] = list(threads.values())[:MAX_ITEMS]
    return normalize_outline(current)


def outline_prompt_block(outline: Any, section_id: str | None = None) -> str:
    """The CAMPAIGN OUTLINE block of the region generation prompt."""
    plan = normalize_outline(outline)
    if plan is None:
        return "CAMPAIGN OUTLINE: none yet. Keep the region consistent with the adventure's plot."
    lines = ["CAMPAIGN OUTLINE:"]
    if plan["premise"]:
        lines.append(f"Premise: {plan['premise']}")
    lines.extend(f"Arc {i}: {step}" for i, step in enumerate(plan["arc"], start=1))
    for entry in plan["sections"]:
        marker = " (THIS REGION)" if entry["id"] == section_id else ""
        plants = f"; plants: {', '.join(entry['plants'])}" if entry["plants"] else ""
        resolves = f"; resolves: {', '.join(entry['resolves'])}" if entry["resolves"] else ""
        gating = f"; gating: {entry['gating']}" if entry["gating"] else ""
        lines.append(f"- {entry['id']}{marker}: {entry['purpose']}{gating}{plants}{resolves}")
    for thread in plan["threads"]:
        lines.append(
            f"Thread {thread['id']} [{thread['status']}]: opened in {thread['opened_in'] or '?'}, "
            f"resolved in {thread['resolved_in'] or '?'}. {thread['note']}".strip()
        )
    return "\n".join(lines)
