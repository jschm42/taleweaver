"""Loot normalization and the post-combat loot phase."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)

LOOT_HELP = "Loot commands: /loot take <item>, /loot leave <item>, /loot done"


def _find_loot_index(loot_items: list[dict[str, Any]], ref: str) -> int:
    low = ref.lower()
    for idx, item in enumerate(loot_items):
        if str(item.get("id", "")).lower() == low or str(item.get("name", "")).lower() == low:
            return idx
    return -1


class CombatLootMixin:
    """Loot normalization, scene drops and /loot commands."""

    async def _spawn_scene_item(self, item: dict[str, Any]) -> None:
        name = str(item.get("name") or "").strip()
        raw_id = str(item.get("id") or item.get("entity_id") or "").strip()

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id, WorldEntity.entity_type == "OBJECT"
            )
        )
        all_objs = ent_res.scalars().all()

        existing_ent: Optional[WorldEntity] = None
        if raw_id:
            existing_ent = next(
                (o for o in all_objs if (o.id or "").strip().upper() == raw_id.upper()), None
            )
        if not existing_ent and name:
            existing_ent = next(
                (o for o in all_objs if (o.name or "").strip().lower() == name.lower()), None
            )

        if not existing_ent:
            logger.warning(
                "[Turn %s] Skipped spawning non-existent entity: ID=%s, Name=%s (dynamic item generation is disabled)",
                self.game_id,
                raw_id,
                name,
            )
            return

        existing_ent.current_scene_id = self.state.current_scene_id
        existing_ent.is_in_inventory = False
        existing_ent.is_hidden = False
        self._update_entity_state(
            existing_ent.id,
            is_in_inventory=False,
            current_scene_id=self.state.current_scene_id,
            is_hidden=False,
        )

    async def _session_entity_id_exists(self, entity_id: str) -> bool:
        res = await self.db.execute(
            select(WorldEntity.pk)
            .where(WorldEntity.session_id == self.game_id, WorldEntity.id == entity_id)
            .limit(1)
        )
        return res.first() is not None

    async def _collect_existing_item_ids(self) -> set[str]:
        existing_ids: set[str] = {
            str(item.get("id"))
            for item in (self.avatar.inventory or [])
            if isinstance(item, dict) and item.get("id")
        }
        res = await self.db.execute(
            select(WorldEntity.id).where(WorldEntity.session_id == self.game_id)
        )
        existing_ids.update({row.id for row in res.all() if row.id})
        return existing_ids

    async def _resolve_loot_reference(self, ent_id: str) -> dict[str, Any]:
        ent = await self._load_session_entity(ent_id)
        if not ent and self.state and self.state.template_id:
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    (WorldEntity.template_id == self.state.template_id) & (WorldEntity.id == ent_id)
                )
            )
            ent = ent_res.scalars().first()
        if not ent:
            return {"id": ent_id, "name": ent_id}
        return {
            "id": ent.id,
            "name": ent.name,
            "description": ent.description,
            "image_url": ent.image_url,
            "item_type": ent.item_type,
            "wearable_slots": ent.wearable_slots,
            **(ent.metadata_json or {}),
        }

    async def _normalize_loot_items(self, items: list[Any]) -> list[dict[str, Any]]:
        """Normalizes loot (dicts or entity id strings) into dicts with ``id`` and ``name``."""
        normalized: list[dict[str, Any]] = []
        for it in items or []:
            if isinstance(it, dict):
                entry = dict(it)
                if not entry.get("id") and entry.get("name"):
                    entry["id"] = f"LOOT_{uuid.uuid4().hex[:8]}"
                normalized.append(entry)
            elif isinstance(it, str) and it.strip():
                normalized.append(await self._resolve_loot_reference(it.strip()))
        return normalized

    def _loot_take(self, combat: dict[str, Any], arg: str) -> str:
        loot_items = list(combat.get("loot_items") or [])
        idx = _find_loot_index(loot_items, arg)
        if idx < 0:
            return "Item not found in loot."
        picked = loot_items.pop(idx)
        self.avatar.inventory = [*list(self.avatar.inventory or []), picked]
        combat["loot_items"] = loot_items
        self._append_combat_log(combat, f"Loot taken: {picked.get('name', 'Unknown Item')}", "loot")
        self._set_combat_state(combat)
        return f"Added {picked.get('name', 'item')} to your inventory."

    async def _loot_leave(self, combat: dict[str, Any], arg: str) -> str:
        loot_items = list(combat.get("loot_items") or [])
        idx = _find_loot_index(loot_items, arg)
        if idx < 0:
            return "Item not found in loot."
        dropped = loot_items.pop(idx)
        await self._spawn_scene_item(dropped)
        combat["loot_items"] = loot_items
        self._append_combat_log(
            combat, f"Loot dropped to scene: {dropped.get('name', 'Unknown Item')}", "loot"
        )
        self._set_combat_state(combat)
        return f"{dropped.get('name', 'Item')} dropped to the current scene."

    async def _clear_combat_state(self) -> None:
        self.state.combat_json = None
        self.state.entity_states = {
            k: v for k, v in (self.state.entity_states or {}).items() if k != "__combat__"
        }
        flag_modified(self.state, "entity_states")
        last_msg = await self._load_last_assistant_message()
        await self._generate_prompt_suggestions(last_msg)
        await self.db.commit()

    async def _loot_done(self, combat: dict[str, Any]) -> str:
        dropped_items = list(combat.get("loot_items") or [])
        for item in dropped_items:
            await self._spawn_scene_item(item)
        combat["loot_items"] = []
        combat["loot_pending"] = False
        combat.pop("outcome", None)
        combat["status_note"] = "Combat resolved."
        self._append_combat_log(combat, combat["status_note"], "loot")

        if combat.get("active"):
            self._set_combat_state(combat)
        else:
            await self._clear_combat_state()

        if not dropped_items:
            return "Combat finished. No loot remained to drop."
        names = [
            str(item.get("name") or item.get("id") or "Unknown Item") for item in dropped_items
        ]
        return "Loot dropped to the scene:\n" + "\n".join(f"- {name}" for name in names)

    async def _resolve_loot_command(self, user_msg: str, combat: dict[str, Any]) -> str | None:
        if not user_msg.lower().strip().startswith("/loot"):
            return None

        parts = user_msg.split(" ", 2)
        action = parts[1].lower() if len(parts) > 1 else ""
        arg = parts[2].strip() if len(parts) > 2 else ""

        if action == "done":
            return await self._loot_done(combat)
        if action not in {"take", "leave", "drop"}:
            return LOOT_HELP
        if not arg:
            verb = "take" if action == "take" else "leave"
            return f"Usage: /loot {verb} <item id or item name>"
        if action == "take":
            return self._loot_take(combat, arg)
        return await self._loot_leave(combat, arg)
