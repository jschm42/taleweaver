"""Shared, precomputed view of an editor payload for all validation checks.

The payload is normalized once (ID sets, lookups, mode) so individual checks stay
small and do not rebuild the same indexes over and over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.schemas.validation import ValidationFinding

INVENTORY_LOCATION = "INVENTORY"
RULE_MODE_RPG = "rpg"


def finding(
    severity: str,
    code: str,
    message: str,
    location: Optional[str] = None,
    **context: Any,
) -> ValidationFinding:
    return ValidationFinding(
        severity=severity,
        code=code,
        message=message,
        location=location,
        context=context or None,
    )


def ref_id(value: Any) -> Optional[str]:
    """Return the referenced ID of an inventory/equipment entry (plain ID or item dict)."""
    if isinstance(value, dict):
        value = value.get("id") or value.get("item_id")
    text = str(value or "").strip()
    return text or None


def ref_ids(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [rid for rid in (ref_id(v) for v in values) if rid]


def scene_id(scene: dict[str, Any]) -> Optional[str]:
    return scene.get("id") or scene.get("scene_id")


def entity_id(entity: dict[str, Any]) -> Optional[str]:
    return entity.get("id") or entity.get("entity_id")


def entity_kind(entity: dict[str, Any]) -> str:
    """Return 'NPC', 'OBJECT', or 'UNKNOWN' for an entity dict."""
    et = (entity.get("entity_type") or entity.get("type") or "").upper()
    if et in {"NPC", "OBJECT"}:
        return et
    if entity.get("npc_type"):
        return "NPC"
    if entity.get("item_type"):
        return "OBJECT"
    return "UNKNOWN"


def item_type(entity: dict[str, Any]) -> str:
    return str(entity.get("item_type") or "").upper()


def metadata(entity: dict[str, Any]) -> dict[str, Any]:
    md = entity.get("metadata_json")
    return md if isinstance(md, dict) else {}


def entity_field(entity: dict[str, Any], key: str) -> Any:
    """Read a field that may live on the row or inside ``metadata_json``."""
    return entity.get(key) or metadata(entity).get(key)


def exit_is_bidirectional(exit_: dict[str, Any]) -> bool:
    """Mirror the engine: only ``exit_type == 'bidirectional'`` can be walked backwards."""
    if exit_.get("is_bidirectional") is True:
        return True
    return str(exit_.get("exit_type") or "").strip().lower() == "bidirectional"


@dataclass(frozen=True)
class ValidationContext:
    raw: dict[str, Any]
    adventure: dict[str, Any]
    protagonist: dict[str, Any]
    scenes: list[dict[str, Any]]
    exits: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    entities_by_id: dict[str, dict[str, Any]]
    scene_ids: frozenset[str]
    npc_ids: frozenset[str]
    object_ids: frozenset[str]
    start_scene_id: Optional[str]
    mode: str

    @property
    def entity_ids(self) -> frozenset[str]:
        return frozenset(self.entities_by_id)

    @property
    def is_rpg(self) -> bool:
        return self.mode == RULE_MODE_RPG

    def entities_of(self, kind: str) -> list[dict[str, Any]]:
        return [e for e in self.entities if entity_kind(e) == kind]

    @classmethod
    def from_payload(cls, payload: Any) -> ValidationContext:
        # Pydantic v2 BaseModel supports .model_dump(); dicts pass through unchanged.
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()

        adventure = payload.get("adventure") or {}
        scenes = list(payload.get("scenes") or [])
        entities = list(payload.get("entities_all") or [])
        if not entities:
            entities = list(payload.get("npcs") or []) + list(payload.get("objects") or [])

        entities_by_id: dict[str, dict[str, Any]] = {}
        for entity in entities:
            eid = entity_id(entity)
            if eid and eid not in entities_by_id:
                entities_by_id[eid] = entity

        return cls(
            raw=payload,
            adventure=adventure,
            protagonist=payload.get("protagonist") or {},
            scenes=scenes,
            exits=list(payload.get("exits") or []),
            entities=entities,
            entities_by_id=entities_by_id,
            scene_ids=frozenset(sid for sid in (scene_id(s) for s in scenes) if sid),
            npc_ids=frozenset(eid for eid, e in entities_by_id.items() if entity_kind(e) == "NPC"),
            object_ids=frozenset(
                eid for eid, e in entities_by_id.items() if entity_kind(e) == "OBJECT"
            ),
            start_scene_id=adventure.get("start_scene_id"),
            mode=str(adventure.get("rule_enforcement_mode") or RULE_MODE_RPG).lower(),
        )
