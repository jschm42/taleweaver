"""Item integrity: the GM may not invent items, and key items must actually be referenced."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select

from backend.core.prompts import KEY_ITEM_REFERENCE_SYSTEM_PROMPT
from backend.engine.rules.rule_engine import GameEvent
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)


class ReferenceCheckResponse(BaseModel):
    referenced: bool


@dataclass
class KnownItems:
    """Every item the world defines or that someone already carries, by upper ID and lower name."""

    entities_by_id: dict[str, WorldEntity] = field(default_factory=dict)
    entities_by_name: dict[str, WorldEntity] = field(default_factory=dict)
    carried_by_id: dict[str, dict] = field(default_factory=dict)
    carried_by_name: dict[str, dict] = field(default_factory=dict)

    def add_carried(self, items: Any) -> None:
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            iid = str(item.get("id") or "").strip().upper()
            iname = str(item.get("name") or "").strip().lower()
            if iid:
                self.carried_by_id[iid] = item
            if iname:
                self.carried_by_name[iname] = item

    def match(self, item: Any) -> tuple[WorldEntity | None, dict | None]:
        iid = str(item.id or "").strip().upper()
        iname = str(item.name or "").strip().lower()
        entity = self.entities_by_id.get(iid) or self.entities_by_name.get(iname)
        carried = self.carried_by_id.get(iid) or self.carried_by_name.get(iname)
        return entity, carried


def _canonicalize(item: Any, entity: WorldEntity | None, carried: dict | None) -> None:
    """Rewrites a GM item to the canonical ID/name/image of the existing item."""
    if entity is not None:
        item.id = entity.id
        item.name = item.name or entity.name
        item.image_url = item.image_url or entity.image_url
        return
    if carried is None:
        return
    item.id = carried.get("id") or item.id
    item.name = carried.get("name") or item.name
    item.image_url = item.image_url or carried.get("image_url")


class ItemIntegrityMixin:
    """Blocks invented items and verifies key-item usage."""

    async def _known_items(self) -> KnownItems:
        known = KnownItems()
        entities = await self._session_entities()
        known.entities_by_id = {e.id.upper(): e for e in entities if e.id}
        known.entities_by_name = {(e.name or "").strip().lower(): e for e in entities if e.name}
        known.add_carried(self.avatar.inventory)
        for ent in entities:
            known.add_carried(ent.inventory)
            meta = ent.metadata_json if isinstance(ent.metadata_json, dict) else {}
            known.add_carried(meta.get("inventory"))
        return known

    def _filter_invented(
        self, items: list[Any], known: KnownItems, reasons: list[str], kind: str
    ) -> list[Any]:
        kept = []
        for item in items:
            entity, carried = known.match(item)
            if entity is None and carried is None:
                reasons.append(
                    f"Spontaneous item generation blocked: '{item.name}' does not exist in the world template."
                )
                logger.warning(
                    "[Turn %s] Blocked dynamic %s: ID=%s, Name=%s",
                    self.game_id,
                    kind,
                    item.id,
                    item.name,
                )
                continue
            _canonicalize(item, entity, carried)
            kept.append(item)
        return kept

    async def _enforce_no_dynamic_item_generation(self, event: GameEvent) -> list[str]:
        """Drops items the GM invented from new inventory items and scene spawns."""
        reasons: list[str] = []
        if not event.new_inventory_items and not event.spawned_items:
            return reasons
        known = await self._known_items()
        if event.new_inventory_items:
            event.new_inventory_items = self._filter_invented(
                event.new_inventory_items, known, reasons, "inventory item generation"
            )
        if event.spawned_items:
            event.spawned_items = self._filter_invented(
                event.spawned_items, known, reasons, "scene item spawn"
            )
        return reasons

    async def _item_name(self, item_id: str) -> str | None:
        carried = next(
            (
                i.get("name")
                for i in self.avatar.inventory or []
                if isinstance(i, dict) and str(i.get("id") or "").strip().upper() == item_id.upper()
            ),
            None,
        )
        if carried:
            return carried
        res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id, WorldEntity.id == item_id
            )
        )
        ent = res.scalars().first()
        return ent.name if ent else None

    async def _llm_says_referenced(self, item_id: str, item_name: str, lowered_msg: str) -> bool:
        """Asks the small model whether a synonym or translation of the item is used."""
        try:
            llm, model = self._small_llm()
            res = await llm.aexecute_complex_task(
                system_prompt=KEY_ITEM_REFERENCE_SYSTEM_PROMPT,
                user_prompt=(
                    f"Required Item ID: {item_id}\nRequired Item Name: {item_name}\n"
                    f'Player Message: "{lowered_msg}"'
                ),
                model=model,
                response_model=ReferenceCheckResponse,
            )
        except Exception as exc:
            logger.error("Error checking key item mention with LLM: %s", exc)
            return False
        if isinstance(res, ReferenceCheckResponse):
            return res.referenced
        return bool(res.get("referenced", False)) if isinstance(res, dict) else False

    async def _is_key_item_referenced(
        self, item_id: str, lowered_msg: str, target_name: str | None = None
    ) -> bool:
        """True when the message names the key item by ID, name, synonym or translation."""
        if not item_id:
            return False
        if item_id.lower() in lowered_msg:
            return True
        item_name = await self._item_name(item_id)
        if not item_name:
            return False
        if item_name.strip().lower() in lowered_msg:
            return True
        return await self._llm_says_referenced(item_id, item_name, lowered_msg)
