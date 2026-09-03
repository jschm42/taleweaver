from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core import prompts
from backend.core.config import settings
from backend.core.prompts import INSPECT_SEARCH_INTENT_GUARD_SYSTEM_PROMPT
import backend.api.routes.adventures.gameplay_logic as gl
from backend.engine.rule_engine import (
    EntityMovement,
    ExitUpdate,
    GameEvent,
    InventoryItem,
    WorldEntityUpdate,
)
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

logger = logging.getLogger(__name__)


class TurnGuardrailsManager:
    """Manages server-side visibility authority and Pass 1.5 rule validations & reversions."""

    def __init__(self, manager: GameTurnManager) -> None:
        self.manager = manager

    @property
    def db(self):
        return self.manager.db

    @property
    def game_id(self):
        return self.manager.game_id

    @property
    def user(self):
        return self.manager.user

    @property
    def state(self):
        return self.manager.state

    @property
    def avatar(self):
        return self.manager.avatar

    @property
    def adventure(self):
        return self.manager.adventure

    @property
    def turn_language(self):
        return self.manager.turn_language

    def _switch_story_flags(self, *args, **kwargs):
        return self.manager._switch_story_flags(*args, **kwargs)

    async def _save_chat_message(self, *args, **kwargs):
        return await self.manager._save_chat_message(*args, **kwargs)

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any] | None:
        raw = (text or "").strip()
        if not raw:
            return None
        try:
            val = json.loads(raw)
            return val if isinstance(val, dict) else None
        except Exception:
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                return None
            try:
                val = json.loads(match.group(0))
                return val if isinstance(val, dict) else None
            except Exception:
                return None

    @staticmethod
    def _normalize_target_token(value: str) -> str:
        """Normalize a target hint for resilient matching across spacing and punctuation variants."""
        return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())

    @staticmethod
    def _sanitize_inspect_or_search_target(raw_target: str) -> str | None:
        """Normalize extracted inspect/search target and drop generic area references."""
        target = (raw_target or "").strip().strip("\"'")
        target = target.lstrip(" \t\n\r\v\f:,-").rstrip(" \t\n\r\v\f.,!?:;")
        if not target:
            return None

        generic_targets = {
            "around",
            "area",
            "surroundings",
            "the surroundings",
            "the area",
            "room",
            "the room",
            "umgebung",
            "bereich",
            "raum",
        }
        if target.lower() in generic_targets:
            return None
        return target

    async def _extract_inspect_or_search_target(self, user_msg: str) -> str | None:
        """Extract inspect/search target via lightweight intent detection without language-specific keyword regex."""
        text = " ".join((user_msg or "").strip().split())
        if not text:
            return None

        lower_text = text.lower()
        if lower_text.startswith("/inspect") or lower_text.startswith("/search"):
            direct_target = text.split(" ", 1)[1].strip() if " " in text else ""
            return self._sanitize_inspect_or_search_target(direct_target)

        llm_settings = self.user.llm_settings or {}
        small_model_provider = (
            llm_settings.get("small_model_provider")
            or llm_settings.get("complex_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        small_model = llm_settings.get("small_model") or "gpt-4o-mini"

        intent_system_prompt = INSPECT_SEARCH_INTENT_GUARD_SYSTEM_PROMPT

        try:
            llm = gl.GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            raw_intent = await llm.aexecute_simple_task(
                intent_system_prompt,
                text,
                small_model,
                adventure_id=self.adventure.id,
                game_id=self.game_id,
                operation="chat_turn",
                phase="inspect_search_intent_guard",
            )
            parsed = self._parse_json_object(raw_intent)
            if not parsed:
                return None

            action = str(parsed.get("action") or "").strip().lower()
            if action not in {"inspect", "search"}:
                return None

            raw_target = parsed.get("target")
            if raw_target is None:
                return None
            return self._sanitize_inspect_or_search_target(str(raw_target))
        except Exception as exc:
            logger.debug("[Turn %s] Inspect/search intent guard skipped: %s", self.game_id, exc)
            return None

    async def _collect_inspect_search_visibility_tokens(self) -> tuple[set[str], set[str]]:
        """Collect allowed and disallowed normalized tokens for inspect/search target checks."""
        allowed_tokens: set[str] = set()
        disallowed_tokens: set[str] = set()

        def _add_token(bucket: set[str], raw: Any) -> None:
            token = self._normalize_target_token(str(raw or ""))
            if token:
                bucket.add(token)

        states = self.state.entity_states or {}
        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
            )
        )
        entities = list(ent_res.scalars().all())

        for ent in entities:
            ent_state = states.get(ent.id, {}) if isinstance(states, dict) else {}
            current_scene_id = ent_state.get("current_scene_id", ent.current_scene_id)
            is_hidden = bool(ent_state.get("is_hidden", ent.is_hidden))
            is_in_inventory = bool(ent_state.get("is_in_inventory", ent.is_in_inventory))

            is_allowed_entity = current_scene_id == self.state.current_scene_id and not is_hidden and not is_in_inventory
            _add_token(allowed_tokens if is_allowed_entity else disallowed_tokens, ent.id)
            _add_token(allowed_tokens if is_allowed_entity else disallowed_tokens, ent.name)

            if (ent.entity_type or "").upper() != "NPC":
                continue

            npc_inventory = ent_state.get("inventory", ent.inventory or [])
            if not isinstance(npc_inventory, list):
                npc_inventory = []

            inventory_bucket = allowed_tokens if (current_scene_id == self.state.current_scene_id and not is_hidden) else disallowed_tokens
            for item in npc_inventory:
                if not isinstance(item, dict):
                    continue
                _add_token(inventory_bucket, item.get("id"))
                _add_token(inventory_bucket, item.get("name"))

        for item in (self.avatar.inventory or []):
            if not isinstance(item, dict):
                continue
            _add_token(allowed_tokens, item.get("id"))
            _add_token(allowed_tokens, item.get("name"))

        disallowed_tokens.difference_update(allowed_tokens)
        return allowed_tokens, disallowed_tokens

    async def _is_inspect_or_search_target_visible(self, target_hint: str) -> bool:
        """Allow inspect/search targets only from current scene, local NPC inventory, or avatar inventory."""
        normalized_hint = self._normalize_target_token(target_hint)
        if not normalized_hint:
            return True

        allowed_tokens: set[str] = set()

        def _add_token(raw: Any) -> None:
            token = self._normalize_target_token(str(raw or ""))
            if token:
                allowed_tokens.add(token)

        states = self.state.entity_states or {}
        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
            )
        )
        entities = list(ent_res.scalars().all())

        for ent in entities:
            ent_state = states.get(ent.id, {}) if isinstance(states, dict) else {}
            current_scene_id = ent_state.get("current_scene_id", ent.current_scene_id)
            is_hidden = bool(ent_state.get("is_hidden", ent.is_hidden))
            is_in_inventory = bool(ent_state.get("is_in_inventory", ent.is_in_inventory))

            if current_scene_id != self.state.current_scene_id or is_hidden:
                continue

            if not is_in_inventory:
                _add_token(ent.id)
                _add_token(ent.name)

            if (ent.entity_type or "").upper() != "NPC":
                continue

            npc_inventory = ent_state.get("inventory", ent.inventory or [])
            if not isinstance(npc_inventory, list):
                npc_inventory = []

            for item in npc_inventory:
                if not isinstance(item, dict):
                    continue
                _add_token(item.get("id"))
                _add_token(item.get("name"))

        for item in (self.avatar.inventory or []):
            if not isinstance(item, dict):
                continue
            _add_token(item.get("id"))
            _add_token(item.get("name"))

        if normalized_hint in allowed_tokens:
            return True

        return any(tok and tok in normalized_hint for tok in allowed_tokens if len(tok) >= 3)

    async def _guard_non_visible_inspect_or_search(self, user_msg: str) -> str | None:
        """Return a blocking system message if the player targets an unseen object for inspect/search."""
        normalized_message = self._normalize_target_token(user_msg)
        if not normalized_message:
            return None

        _allowed_tokens, disallowed_tokens = await self._collect_inspect_search_visibility_tokens()
        if not any(tok in normalized_message for tok in disallowed_tokens if len(tok) >= 3):
            return None

        target_hint = await self._extract_inspect_or_search_target(user_msg)
        if not target_hint:
            return None

        is_visible = await self._is_inspect_or_search_target_visible(target_hint)
        if is_visible:
            return None

        return (
            f"You cannot inspect or search '{target_hint}' right now. "
            "Only objects in the current scene and items from your inventory or local NPC inventories are available."
        )


    @staticmethod
    def _is_container_item(item: Any) -> bool:
        return isinstance(item, dict) and str(item.get("item_type") or "").upper() == "CONTAINER"

    def _is_container_locked(self, scene_container: WorldEntity | None, inventory_container: dict[str, Any] | None) -> bool:
        states = self.state.entity_states or {}

        def _requirements_from_metadata(metadata: dict[str, Any]) -> tuple[str, str, str]:
            return (
                str(metadata.get("code_to_unlock") or "").strip(),
                str(metadata.get("item_to_unlock") or "").strip().upper(),
                str(metadata.get("rule_to_unlock") or "").strip(),
            )

        if scene_container:
            state_locked = (states.get(scene_container.id) or {}).get("locked")
            if isinstance(state_locked, bool):
                return state_locked
            metadata_json = dict(getattr(scene_container, "metadata_json", None) or {})
            code_to_unlock, item_to_unlock, rule_to_unlock = _requirements_from_metadata(metadata_json)
            return bool(code_to_unlock or item_to_unlock or rule_to_unlock)

        if inventory_container:
            inv_id = str(inventory_container.get("id") or "").strip()
            if inv_id:
                state_locked = (states.get(inv_id) or {}).get("locked")
                if isinstance(state_locked, bool):
                    return state_locked
            item_locked = inventory_container.get("locked")
            if isinstance(item_locked, bool):
                return item_locked
            metadata_json = inventory_container.get("metadata_json")
            if not isinstance(metadata_json, dict):
                metadata_json = {}
            code_to_unlock, item_to_unlock, rule_to_unlock = _requirements_from_metadata(metadata_json)
            return bool(code_to_unlock or item_to_unlock or rule_to_unlock)

        return False

    @staticmethod
    def _extract_access_code(text: str) -> str | None:
        if not text:
            return None
        quoted = re.search(r"[\"']([A-Za-z0-9]{1,32})[\"']", text)
        if quoted:
            return quoted.group(1)
        match = re.search(r"\b(\d{3,8})\b", text)
        return match.group(1) if match else None

    async def _resolve_container_from_free_text(self, text: str) -> tuple[str, str, str, str, str, bool] | None:
        lowered = (text or "").strip().lower()
        if not lowered:
            return None

        best_match: tuple[int, str, str, str, str, str, bool] | None = None

        scene_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type == "OBJECT",
                WorldEntity.item_type == "CONTAINER",
                WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(False),
            )
        )
        for ent in scene_res.scalars().all():
            cid = str(ent.id or "")
            cname = str(ent.name or "")
            tokens = [cid.lower(), cname.lower()]
            token = next((tok for tok in tokens if tok and tok in lowered), None)
            if not token:
                continue
            locked = self._is_container_locked(ent, None)
            metadata_json = dict(ent.metadata_json or {})
            code_to_unlock = str(metadata_json.get("code_to_unlock") or "").strip()
            item_to_unlock = str(metadata_json.get("item_to_unlock") or "").strip().upper()
            rule_to_unlock = str(metadata_json.get("rule_to_unlock") or "").strip()
            candidate = (len(token), cid, cname or cid, code_to_unlock, item_to_unlock, rule_to_unlock, locked)
            if best_match is None or candidate[0] > best_match[0]:
                best_match = candidate

        for inv_item in (self.avatar.inventory or []):
            if not self._is_container_item(inv_item):
                continue
            cid = str(inv_item.get("id") or "").strip()
            cname = str(inv_item.get("name") or "").strip()
            tokens = [cid.lower(), cname.lower()]
            token = next((tok for tok in tokens if tok and tok in lowered), None)
            if not token:
                continue
            locked = self._is_container_locked(None, inv_item)
            metadata_json = inv_item.get("metadata_json")
            if not isinstance(metadata_json, dict):
                metadata_json = {}
            code_to_unlock = str(metadata_json.get("code_to_unlock") or "").strip()
            item_to_unlock = str(metadata_json.get("item_to_unlock") or "").strip().upper()
            rule_to_unlock = str(metadata_json.get("rule_to_unlock") or "").strip()
            candidate = (len(token), cid or cname, cname or cid or "container", code_to_unlock, item_to_unlock, rule_to_unlock, locked)
            if best_match is None or candidate[0] > best_match[0]:
                best_match = candidate

        if not best_match:
            return None

        _, cid, cname, code_to_unlock, item_to_unlock, rule_to_unlock, locked = best_match
        return cid, cname, code_to_unlock, item_to_unlock, rule_to_unlock, locked

    async def _enforce_no_dynamic_item_generation(self, event: GameEvent) -> list[str]:
        """
        Enforces that the GM/LLM cannot dynamically generate new items on-the-fly.
        Filters out any newly invented items from new_inventory_items and spawned_items.
        """
        reasons = []

        has_new_inv = bool(event.new_inventory_items)
        has_spawned = bool(event.spawned_items)
        if not has_new_inv and not has_spawned:
            return reasons

        # 1. Fetch all pre-defined entity IDs and entities for this session
        res = await self.db.execute(
            select(WorldEntity).where(WorldEntity.session_id == self.game_id)
        )
        db_entities = res.scalars().all()
        entity_by_id: dict[str, WorldEntity] = {e.id.upper(): e for e in db_entities if e.id}
        entity_by_name: dict[str, WorldEntity] = {(e.name or "").strip().lower(): e for e in db_entities if e.name}

        # 2. Collect avatar inventory items
        avatar_inv_by_id: dict[str, dict] = {}
        avatar_inv_by_name: dict[str, dict] = {}
        for item in (self.avatar.inventory or []):
            if isinstance(item, dict):
                iid = str(item.get("id") or "").strip().upper()
                iname = str(item.get("name") or "").strip().lower()
                if iid:
                    avatar_inv_by_id[iid] = item
                if iname:
                    avatar_inv_by_name[iname] = item

        # 3. Collect NPC and container inventories
        npc_container_inv_by_id: dict[str, dict] = {}
        npc_container_inv_by_name: dict[str, dict] = {}
        for e in db_entities:
            if isinstance(e.inventory, list):
                for item in e.inventory:
                    if isinstance(item, dict):
                        iid = str(item.get("id") or "").strip().upper()
                        iname = str(item.get("name") or "").strip().lower()
                        if iid:
                            npc_container_inv_by_id[iid] = item
                        if iname:
                            npc_container_inv_by_name[iname] = item
            meta = e.metadata_json or {}
            if isinstance(meta, dict):
                container_inv = meta.get("inventory") or []
                if isinstance(container_inv, list):
                    for item in container_inv:
                        if isinstance(item, dict):
                            iid = str(item.get("id") or "").strip().upper()
                            iname = str(item.get("name") or "").strip().lower()
                            if iid:
                                npc_container_inv_by_id[iid] = item
                            if iname:
                                npc_container_inv_by_name[iname] = item

        # 4. Filter new_inventory_items
        if event.new_inventory_items:
            filtered_inv = []
            for item in event.new_inventory_items:
                iid = str(item.id or "").strip().upper()
                iname = str(item.name or "").strip().lower()

                matched_entity = entity_by_id.get(iid) or entity_by_name.get(iname)
                matched_inv = (
                    avatar_inv_by_id.get(iid)
                    or avatar_inv_by_name.get(iname)
                    or npc_container_inv_by_id.get(iid)
                    or npc_container_inv_by_name.get(iname)
                )

                if not matched_entity and not matched_inv:
                    reasons.append(f"Spontaneous item generation blocked: '{item.name}' does not exist in the world template.")
                    logger.warning(
                        f"[Turn {self.game_id}] Blocked dynamic inventory item generation: ID={item.id}, Name={item.name}"
                    )
                    continue

                if matched_entity:
                    if not item.id or item.id != matched_entity.id:
                        item.id = matched_entity.id
                    if not item.name:
                        item.name = matched_entity.name
                    if matched_entity.image_url and not item.image_url:
                        item.image_url = matched_entity.image_url
                elif matched_inv:
                    if matched_inv.get("id"):
                        item.id = matched_inv["id"]
                    if matched_inv.get("name"):
                        item.name = matched_inv["name"]
                    if matched_inv.get("image_url") and not item.image_url:
                        item.image_url = matched_inv["image_url"]

                filtered_inv.append(item)
            event.new_inventory_items = filtered_inv

        # 5. Filter spawned_items
        if event.spawned_items:
            filtered_spawned = []
            for item in event.spawned_items:
                iid = str(item.id or "").strip().upper()
                iname = str(item.name or "").strip().lower()

                matched_entity = entity_by_id.get(iid) or entity_by_name.get(iname)
                matched_inv = (
                    avatar_inv_by_id.get(iid)
                    or avatar_inv_by_name.get(iname)
                    or npc_container_inv_by_id.get(iid)
                    or npc_container_inv_by_name.get(iname)
                )

                if not matched_entity and not matched_inv:
                    reasons.append(f"Spontaneous item generation blocked: '{item.name}' does not exist in the world template.")
                    logger.warning(
                        f"[Turn {self.game_id}] Blocked dynamic scene item spawn: ID={item.id}, Name={item.name}"
                    )
                    continue

                if matched_entity:
                    if not item.id or item.id != matched_entity.id:
                        item.id = matched_entity.id
                    if not item.name:
                        item.name = matched_entity.name
                    if matched_entity.image_url and not item.image_url:
                        item.image_url = matched_entity.image_url
                elif matched_inv:
                    if matched_inv.get("id"):
                        item.id = matched_inv["id"]
                    if matched_inv.get("name"):
                        item.name = matched_inv["name"]
                    if matched_inv.get("image_url") and not item.image_url:
                        item.image_url = matched_inv["image_url"]

                filtered_spawned.append(item)
            event.spawned_items = filtered_spawned

        return reasons

    async def _enforce_constructable_combination(self, event: GameEvent, user_msg: str) -> list[str]:
        """Deterministically resolve CONSTRUCTABLE items and prevent illegal spawning/revealing of them.

        A CONSTRUCTABLE is a hidden object that materializes when the player
        combines ALL of its ``combination_ingredients`` (minimum 2). When the
        player issues a combine/use action and every ingredient is currently
        accessible (in the protagonist's inventory or visible in the current
        scene) and at least one ingredient is referenced in the message, the
        engine consumes the ingredients (they vanish) and auto-reveals the
        constructable in the player's current scene. ``reveals_item_id`` and
        ``reveal_rule`` are intentionally ignored for this type.
        """
        ent_res = await self.db.execute(
            select(WorldEntity).where(WorldEntity.session_id == self.game_id)
        )
        all_entities = list(ent_res.scalars().all())

        constructable_entities = [
            e for e in all_entities
            if e.id and str(e.item_type or "").upper() == "CONSTRUCTABLE"
        ]
        if not constructable_entities:
            return []

        constructable_ids = {e.id.upper() for e in constructable_entities}
        constructed_this_turn: set[str] = set()
        messages: list[str] = []

        lowered = (user_msg or "").strip().lower()
        combine_intent = False
        if lowered:
            combine_intent = (
                bool(event.combination_intent)
                or lowered.startswith("use ")
                or lowered.startswith("benutz")
                or any(
                    kw in lowered
                    for kw in (
                        "combine", "assembl", "craft", " mix ", "put together",
                        "kombi", "misch", "zusammen", "herstell", "erzeug", "bastel", "bau "
                    )
                )
            )

        if combine_intent:
            ent_by_id_upper: dict[str, WorldEntity] = {
                (e.id or "").upper(): e for e in all_entities if e.id
            }

            current_scene_id = self.state.current_scene_id
            states_snapshot = dict(self.state.entity_states or {})

            def _is_hidden_now(e: WorldEntity) -> bool:
                ov = states_snapshot.get(e.id, {})
                if "is_hidden" in ov and ov["is_hidden"] is not None:
                    return bool(ov["is_hidden"])
                return bool(e.is_hidden)

            # Inventory ingredient ids (preserve original case for removal matching).
            inventory_id_lookup: dict[str, str] = {}
            for item in (self.avatar.inventory or []):
                if isinstance(item, dict) and item.get("id"):
                    inventory_id_lookup[str(item["id"]).strip().upper()] = str(item["id"])

            # Visible entities in the current scene (inventory items are tracked separately).
            scene_entity_ids: set[str] = set()
            for e in all_entities:
                if e.current_scene_id != current_scene_id:
                    continue
                if e.is_in_inventory:
                    continue
                if _is_hidden_now(e):
                    continue
                if e.id:
                    scene_entity_ids.add(e.id.upper())

            accessible_ids: set[str] = set(inventory_id_lookup.keys()) | scene_entity_ids
            consumed: set[str] = set()

            for e in all_entities:
                if str(e.item_type or "").upper() != "CONSTRUCTABLE":
                    continue
                raw_ingredients = e.combination_ingredients or []
                needed = [str(i).strip() for i in raw_ingredients if i and str(i).strip()]
                needed_upper = {i.upper() for i in needed}
                if len(needed_upper) < 2:
                    continue
                if e.id and e.id.upper() in consumed:
                    continue
                # Skip already-revealed constructables.
                if not _is_hidden_now(e):
                    continue
                # An ingredient already consumed by a prior constructable this turn?
                if needed_upper & consumed:
                    continue
                # All ingredients must be accessible right now.
                if not needed_upper.issubset(accessible_ids):
                    continue

                # At least one ingredient must be referenced (by name or id) in the
                # player's message, to avoid accidental construction.
                referenced = False
                for ing_upper in needed_upper:
                    ing_ent = ent_by_id_upper.get(ing_upper)
                    tokens = [ing_upper]
                    if ing_ent and ing_ent.name:
                        tokens.append(ing_ent.name)
                    for tok in tokens:
                        tok_low = (tok or "").lower()
                        if len(tok_low) >= 3 and re.search(r"\b" + re.escape(tok_low) + r"\b", lowered):
                            referenced = True
                            break
                    if referenced:
                        break

                # If strict string matching fails (e.g. due to translations/synonyms),
                # but the Game Master LLM explicitly decided to grant the combined item
                # as a result of this action, we trust the LLM and consider it intended.
                if not referenced:
                    llm_granted = False
                    if event.new_inventory_items:
                        for item in event.new_inventory_items:
                            iid = getattr(item, "id", None) or getattr(item, "entity_id", None)
                            if iid and str(iid).strip().upper() == e.id.upper():
                                llm_granted = True
                                break
                    if not llm_granted and event.spawned_items:
                        for item in event.spawned_items:
                            iid = getattr(item, "id", None) or getattr(item, "entity_id", None)
                            if iid and str(iid).strip().upper() == e.id.upper():
                                llm_granted = True
                                break
                    if llm_granted:
                        referenced = True

                if not referenced:
                    continue

                # CONSTRUCT — consume ingredients, reveal result.
                all_in_inventory = True
                for ing_upper in needed_upper:
                    if ing_upper in inventory_id_lookup:
                        if event.removed_inventory_item_ids is None:
                            event.removed_inventory_item_ids = []
                        original = inventory_id_lookup[ing_upper]
                        if original not in event.removed_inventory_item_ids:
                            event.removed_inventory_item_ids.append(original)
                    else:
                        self._upsert_entity_update(event, ing_upper, is_hidden=True)
                        all_in_inventory = False
                    consumed.add(ing_upper)

                self._upsert_entity_update(event, e.id, is_hidden=False)
                self._upsert_entity_movement(event, e.id, current_scene_id)
                if all_in_inventory:
                    from backend.engine.rule_engine import InventoryItem
                    if event.new_inventory_items is None:
                        event.new_inventory_items = []
                    # Check if already added
                    if not any(i.id == e.id for i in event.new_inventory_items):
                        event.new_inventory_items.append(InventoryItem(
                            id=e.id, 
                            name=e.name or "Unknown Item",
                            description=e.description,
                            item_type=e.item_type
                        ))
                constructed_this_turn.add(e.id.upper())

                ing_names: list[str] = []
                for ing_upper in needed_upper:
                    ing_ent = ent_by_id_upper.get(ing_upper)
                    ing_names.append(ing_ent.name if ing_ent and ing_ent.name else ing_upper)
                msg = f"You combine {', '.join(ing_names)} to create {e.name}!"
                messages.append(msg)
                logger.info(
                    "[Turn %s] CONSTRUCTABLE '%s' materialized from ingredients %s",
                    self.game_id,
                    e.id,
                    sorted(needed_upper),
                )

        # Reconcile / Guardrail Step: Ensure no constructable item has been spawned/revealed illegally by the LLM
        for cid_upper in constructable_ids:
            if cid_upper in constructed_this_turn:
                continue

            # Remove from event.new_inventory_items
            if event.new_inventory_items:
                filtered_new_inv = []
                for item in event.new_inventory_items:
                    item_id = getattr(item, "id", None) or getattr(item, "entity_id", None)
                    if item_id and str(item_id).strip().upper() == cid_upper:
                        original_ent = next((x for x in constructable_entities if x.id.upper() == cid_upper), None)
                        name = original_ent.name if original_ent else item.name
                        ingredients = original_ent.combination_ingredients if original_ent else []
                        messages.append(
                            f"Rule Violation: Attempted to add constructable item '{name}' ({cid_upper}) to inventory without combining its ingredients: {', '.join(ingredients) if ingredients else 'unknown'}."
                        )
                        continue
                    filtered_new_inv.append(item)
                event.new_inventory_items = filtered_new_inv

            # Remove from event.updated_inventory_items
            if event.updated_inventory_items:
                filtered_updated_inv = []
                for item in event.updated_inventory_items:
                    item_id = getattr(item, "id", None) or getattr(item, "entity_id", None)
                    if item_id and str(item_id).strip().upper() == cid_upper:
                        continue
                    filtered_updated_inv.append(item)
                event.updated_inventory_items = filtered_updated_inv

            # Remove from event.spawned_items
            if event.spawned_items:
                filtered_spawned = []
                for item in event.spawned_items:
                    item_id = getattr(item, "id", None) or getattr(item, "entity_id", None)
                    if item_id and str(item_id).strip().upper() == cid_upper:
                        original_ent = next((x for x in constructable_entities if x.id.upper() == cid_upper), None)
                        name = original_ent.name if original_ent else item.name
                        ingredients = original_ent.combination_ingredients if original_ent else []
                        messages.append(
                            f"Rule Violation: Attempted to spawn constructable item '{name}' ({cid_upper}) in scene without combining its ingredients: {', '.join(ingredients) if ingredients else 'unknown'}."
                        )
                        continue
                    filtered_spawned.append(item)
                event.spawned_items = filtered_spawned

            # Remove from event.updated_entities
            if event.updated_entities:
                filtered_entities = []
                for up in event.updated_entities:
                    if up.entity_id and up.entity_id.upper() == cid_upper:
                        if up.is_hidden is False:
                            original_ent = next((x for x in constructable_entities if x.id.upper() == cid_upper), None)
                            name = original_ent.name if original_ent else up.entity_id
                            ingredients = original_ent.combination_ingredients if original_ent else []
                            messages.append(
                                f"Rule Violation: Attempted to reveal constructable entity '{name}' ({cid_upper}) without combining its ingredients: {', '.join(ingredients) if ingredients else 'unknown'}."
                            )
                        continue
                    filtered_entities.append(up)
                event.updated_entities = filtered_entities

            # Remove from event.moved_entities
            if event.moved_entities:
                filtered_moved = []
                for move in event.moved_entities:
                    if move.entity_id and move.entity_id.upper() == cid_upper:
                        continue
                    filtered_moved.append(move)
                event.moved_entities = filtered_moved

        return messages

    async def _enforce_hidden_entity_reveal(
        self, event: GameEvent, user_msg: str, draft_narration: str = ""
    ) -> list[str]:
        """Auto-reveals hidden entities in the current scene when reveal conditions or search actions match.

        A hidden entity (is_hidden=True) should be revealed when:
        1. The LLM explicitly flags it in `discovered_entity_ids`.
        2. The event spawns or adds the item to inventory without an explicit unhide flag.
        """
        ent_res = await self.db.execute(
            select(WorldEntity).where(WorldEntity.session_id == self.game_id)
        )
        all_entities = list(ent_res.scalars().all())
        current_scene_id = self.state.current_scene_id
        states_snapshot = dict(self.state.entity_states or {})

        def _is_hidden_now(e: WorldEntity) -> bool:
            ov = states_snapshot.get(e.id, {})
            if "is_hidden" in ov and ov["is_hidden"] is not None:
                return bool(ov["is_hidden"])
            return bool(e.is_hidden)

        container_payloads = [
            {"item_type": e.item_type, "inventory": e.inventory}
            for e in all_entities
        ]
        contained_item_ids = AdventureLogic.collect_container_item_ids(container_payloads)

        hidden_entities = [
            e
            for e in all_entities
            if e.current_scene_id == current_scene_id
            and not getattr(e, "is_in_inventory", False)
            and str(e.id or "") not in contained_item_ids
            and str(e.item_type or "").upper() != "CONSTRUCTABLE"
            and _is_hidden_now(e)
        ]

        if not hidden_entities:
            return []

        revealed_messages: list[str] = []

        # Prepare list of explicitly discovered IDs from the LLM
        discovered_ids = {str(eid).strip().upper() for eid in (getattr(event, "discovered_entity_ids", []) or [])}

        for e in hidden_entities:
            eid = e.id
            if not eid:
                continue

            # Check if already revealed in event.updated_entities
            already_revealed = False
            for up in (event.updated_entities or []):
                if (up.entity_id or "").upper() == eid.upper() and up.is_hidden is False:
                    already_revealed = True
                    break
            if already_revealed:
                continue

            should_reveal = False
            
            # Condition 1: Explicitly flagged by LLM as discovered
            if eid.upper() in discovered_ids:
                should_reveal = True

            # Condition 2: Spawned or added to inventory
            if not should_reveal and event.spawned_items:
                for s in event.spawned_items:
                    sid = str(getattr(s, "id", "") or getattr(s, "entity_id", "") or "").upper()
                    sname = str(getattr(s, "name", "") or "").strip().lower()
                    if sid == eid.upper() or (sname and sname == (e.name or "").strip().lower()):
                        should_reveal = True
                        break

            if not should_reveal and event.new_inventory_items:
                for inv in event.new_inventory_items:
                    iid = str(getattr(inv, "id", "") or getattr(inv, "entity_id", "") or "").upper()
                    iname = str(getattr(inv, "name", "") or "").strip().lower()
                    if iid == eid.upper() or (iname and iname == (e.name or "").strip().lower()):
                        should_reveal = True
                        break

            # Condition 3: Parent container/object was unlocked, opened, or updated in this event
            if not should_reveal and event.updated_entities:
                for up in event.updated_entities:
                    if not up.entity_id:
                        continue
                    parent_ent = next((pe for pe in all_entities if pe.id == up.entity_id), None)
                    if parent_ent and parent_ent.reveals_item_id and parent_ent.reveals_item_id.strip().upper() == eid.upper():
                        should_reveal = True
                        break
                    parent_tag = f"##{up.entity_id.upper()}"
                    if (
                        parent_tag in str(e.spatial_position or "").upper()
                        or parent_tag in str(e.reveal_rule or "").upper()
                        or up.entity_id.upper() in str(e.spatial_position or "").upper()
                    ):
                        should_reveal = True
                        break

            # Fallback to fast LLM semantic evaluation for language-agnostic discovery
            if not should_reveal and (user_msg or draft_narration):
                try:
                    from backend.core.llm_router import GameMasterLLM
                    from pydantic import BaseModel
                    llm_settings = self.user.llm_settings or {}
                    small_model_provider = (
                        llm_settings.get("small_model_provider")
                        or llm_settings.get("provider")
                        or "openai"
                    )
                    small_model = (
                        llm_settings.get("small_model_name")
                        or llm_settings.get("model")
                        or "gpt-4o-mini"
                    )
                    llm = gl.GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
                    
                    system_prompt = (
                        "You are a mechanics checker for an AI Text Adventure RPG.\n"
                        "Determine if the Game Master's narration or the player's message explicitly describes finding, discovering, or revealing a specific hidden entity.\n"
                        "You must respond with a JSON object containing a single boolean field: 'discovered'.\n"
                        "Guidelines:\n"
                        "1. If the narration describes the player finding the item, or the item being uncovered (even using synonyms or translated words), 'discovered' must be true.\n"
                        "2. If the player searches the exact hiding spot (e.g. they search the couch, and the entity is hidden in the couch cushions), 'discovered' must be true.\n"
                        "3. Otherwise, if the item remains hidden or unmentioned, 'discovered' must be false.\n"
                        "4. Respond with exactly the JSON structure: {\"discovered\": true} or {\"discovered\": false}."
                    )
                    
                    user_prompt = (
                        f"Hidden Entity ID: {eid}\n"
                        f"Hidden Entity Name: {e.name}\n"
                        f"Entity Hidden At/Reveal Rule: {e.spatial_position or ''} {e.reveal_rule or ''}\n"
                        f"Player Message: \"{user_msg}\"\n"
                        f"Game Master Narration: \"{draft_narration}\""
                    )
                    
                    class DiscoveryCheckResponse(BaseModel):
                        discovered: bool
                        
                    res = await llm.aexecute_complex_task(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model=small_model,
                        response_model=DiscoveryCheckResponse
                    )
                    if isinstance(res, DiscoveryCheckResponse):
                        should_reveal = res.discovered
                    elif isinstance(res, dict):
                        should_reveal = bool(res.get("discovered", False))
                except Exception as ex:
                    import logging
                    logging.getLogger("backend").error(f"Error checking hidden entity discovery with LLM: {ex}")

            if should_reveal:
                self._upsert_entity_update(event, eid, is_hidden=False)
                revealed_messages.append(f"Revealed {e.name}")
                logger.info(
                    "[Turn %s] Auto-revealed hidden entity '%s' (%s) in scene '%s'",
                    self.game_id,
                    eid,
                    e.name,
                    current_scene_id,
                )

        return revealed_messages

    def _upsert_entity_update(self, event: GameEvent, entity_id: str, **fields: object) -> None:
        """Insert or merge a WorldEntityUpdate for ``entity_id`` into the event."""
        if not entity_id:
            return
        if event.updated_entities is None:
            event.updated_entities = []
        for up in event.updated_entities:
            if up.entity_id == entity_id:
                for key, value in fields.items():
                    setattr(up, key, value)
                return
        event.updated_entities.append(WorldEntityUpdate(entity_id=entity_id, **fields))  # type: ignore[arg-type]

    def _upsert_entity_movement(self, event: GameEvent, entity_id: str, to_scene_id: str) -> None:
        """Insert or merge an EntityMovement for ``entity_id`` into the event."""
        if not entity_id or not to_scene_id:
            return
        if event.moved_entities is None:
            event.moved_entities = []
        for move in event.moved_entities:
            if move.entity_id == entity_id:
                move.to_scene_id = to_scene_id
                return
        event.moved_entities.append(EntityMovement(entity_id=entity_id, to_scene_id=to_scene_id))

    async def _is_key_item_referenced(self, item_id: str, lowered_msg: str, target_name: str | None = None) -> bool:
        """Checks if the key item ID or its name/significant name tokens are referenced in the message."""
        if not item_id:
            return False

        # 1. Direct ID match
        if item_id.lower() in lowered_msg:
            return True

        # 2. Find item name
        item_name = None
        # Look in avatar inventory first
        for item in (self.avatar.inventory or []):
            if isinstance(item, dict) and str(item.get("id") or "").strip().upper() == item_id.upper():
                item_name = item.get("name")
                break

        if not item_name:
            # Look in database WorldEntities
            res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
                    WorldEntity.id == item_id
                )
            )
            db_ent = res.scalars().first()
            if db_ent:
                item_name = db_ent.name

        if not item_name:
            return False

        # 3. Direct name match (case-insensitive substring)
        name_low = item_name.strip().lower()
        if name_low in lowered_msg:
            return True

        # 4. Fallback to LLM semantic evaluation for synonyms, translations, and descriptions
        try:
            from pydantic import BaseModel
            from backend.core.llm_router import GameMasterLLM
            
            llm_settings = self.user.llm_settings or {}
            small_model_provider = (
                llm_settings.get("small_model_provider")
                or llm_settings.get("provider")
                or "openai"
            )
            small_model = (
                llm_settings.get("small_model_name")
                or llm_settings.get("model")
                or "gpt-4o-mini"
            )
            
            llm = gl.GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            
            system_prompt = (
                "You are a mechanics checker for an AI Text Adventure RPG.\n"
                "Determine if the player's message explicitly references, mentions, or utilizes a specific required item in the current turn.\n"
                "You must respond with a JSON object containing a single boolean field: 'referenced'.\n"
                "Guidelines:\n"
                "1. If the player mentions the name of the item, the item's ID, or a direct synonym or translation (e.g. 'Schlüssel' for 'key', 'Schraubenzieher' or 'Schraubendreher' for 'screwdriver', 'Karte' for 'card'), 'referenced' must be true.\n"
                "2. If the player only says a generic action (like 'öffne die kiste' or 'turn the switch') without specifying the item or tool they are using, 'referenced' must be false (even if the item is in their inventory).\n"
                "3. Respond with exactly the JSON structure: {\"referenced\": true} or {\"referenced\": false}."
            )
            
            user_prompt = (
                f"Required Item ID: {item_id}\n"
                f"Required Item Name: {item_name}\n"
                f"Player Message: \"{lowered_msg}\""
            )
            
            class ReferenceCheckResponse(BaseModel):
                referenced: bool
                
            res = await llm.aexecute_complex_task(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=small_model,
                response_model=ReferenceCheckResponse
            )
            if isinstance(res, ReferenceCheckResponse):
                return res.referenced
            elif isinstance(res, dict):
                return bool(res.get("referenced", False))
        except Exception as e:
            logging.getLogger("backend").error(f"Error checking key item mention with LLM: {e}")

        return False

    async def _get_switch_story_flags(self) -> set[str]:
        """Returns the set of all story flag keys configured as switch outcomes in this adventure."""
        res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "OBJECT",
                WorldEntity.item_type == "SWITCH"
            )
        )
        switches = res.scalars().all()
        flags = set()
        for sw in switches:
            meta = sw.metadata_json or {}
            config = meta.get("switch") or {}
            outcomes = meta.get("switch_outcomes") or config.get("outcomes") or []
            for oc in outcomes:
                if not isinstance(oc, dict):
                    continue
                effects = oc.get("effects") or []
                for eff in effects:
                    if isinstance(eff, dict) and eff.get("type") == "story_flag" and eff.get("key"):
                        flags.add(str(eff.get("key")).strip())
        return flags

    async def _enforce_container_unlock_guardrails(self, event: GameEvent, user_msg: str) -> list[str]:
        container_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "OBJECT",
                WorldEntity.item_type == "CONTAINER",
            )
        )
        db_containers = list(container_res.scalars().all())

        inventory_containers = []
        for item in (self.avatar.inventory or []):
            if isinstance(item, dict) and str(item.get("item_type") or "").upper() == "CONTAINER":
                inventory_containers.append(item)

        reasons = []
        lowered = (user_msg or "").strip().lower()

        switch_outcome_flags = await self._get_switch_story_flags()

        for ent in db_containers:
            is_locked = self._is_container_locked(ent, None)
            if not is_locked:
                continue

            # Determine if player is trying to open/unlock this container in free text
            is_player_trying_to_open = False
            ent_id_low = str(ent.id or "").strip().lower()
            ent_name_low = str(ent.name or "").strip().lower()
            if ent_id_low and ent_id_low in lowered:
                is_player_trying_to_open = True
            elif ent_name_low and ent_name_low in lowered:
                is_player_trying_to_open = True

            is_being_unlocked = any(
                update.entity_id == ent.id and update.locked is False
                for update in (event.updated_entities or [])
            )

            if not is_being_unlocked and not is_player_trying_to_open:
                continue

            metadata_json = dict(ent.metadata_json or {})
            required_code = str(metadata_json.get("code_to_unlock") or "").strip()
            required_item_id = str(metadata_json.get("item_to_unlock") or "").strip().upper()
            required_rule = str(metadata_json.get("rule_to_unlock") or "").strip()

            unlock_allowed = True
            reason = ""

            # 1. Rule validation
            if required_rule:
                is_switch_flag = required_rule in switch_outcome_flags
                flag_active = self._switch_story_flags().get(required_rule, False)

                if is_switch_flag:
                    if not flag_active:
                        unlock_allowed = False
                        reason = f"{ent.name} stays shut. It seems to require some mechanism to trigger."
                else:
                    if not is_being_unlocked:
                        unlock_allowed = False
                        hinted_actor = ""
                        distract_match = re.search(r"\bdistract\w*\s+([A-Za-z0-9_\- ]{2,60})", required_rule, re.IGNORECASE)
                        if distract_match:
                            hinted_actor = distract_match.group(1).strip(" .,:;!?")

                        if hinted_actor:
                            reason = (
                                f"{ent.name} stays shut. {hinted_actor} seems to keep a close eye on it. "
                                "A clever distraction might create an opening."
                            )
                        else:
                            reason = (
                                f"{ent.name} stays shut. The moment does not feel right yet. "
                                "A different approach might open a window."
                            )

            # 2. Code validation
            if unlock_allowed and required_code:
                if not is_being_unlocked or required_code.lower() not in lowered:
                    unlock_allowed = False
                    reason = f"{ent.name} gives a mocking click. That code won't do the trick."

            # 3. Item validation
            if unlock_allowed and required_item_id:
                inventory_ids = {
                    str(item.get("id") or "").strip().upper()
                    for item in (self.avatar.inventory or [])
                    if isinstance(item, dict)
                }
                if required_item_id.upper() not in inventory_ids:
                    unlock_allowed = False
                    reason = f"You need {required_item_id} to unlock {ent.name}."
                elif not await self._is_key_item_referenced(required_item_id, lowered, ent.name):
                    unlock_allowed = False
                    reason = f"You must specify which item you are using to unlock {ent.name}."
                elif not is_being_unlocked:
                    unlock_allowed = False
                    reason = f"You try using the item to unlock {ent.name}."

            if not is_being_unlocked:
                unlock_allowed = False

            if not unlock_allowed:
                sanitized_updates: list[WorldEntityUpdate] = []
                for update in (event.updated_entities or []):
                    if update.entity_id == ent.id and update.locked is False:
                        continue
                    sanitized_updates.append(update)
                sanitized_updates.append(WorldEntityUpdate(entity_id=ent.id, locked=True))
                event.updated_entities = sanitized_updates

                event.completed_quest_ids = []
                event.earned_award_keys = []
                event.new_inventory_items = []
                event.updated_inventory_items = []
                event.removed_inventory_item_ids = []
                event.spawned_items = []

                reasons.append(reason or f"{ent.name} stays locked.")

        for item in inventory_containers:
            inv_id = str(item.get("id") or "").strip()
            if not inv_id:
                continue

            is_locked = self._is_container_locked(None, item)
            if not is_locked:
                continue

            # Determine if player is trying to open/unlock this container in free text
            is_player_trying_to_open = False
            item_name = str(item.get("name") or "").strip().lower()
            if inv_id.lower() in lowered:
                is_player_trying_to_open = True
            elif item_name and item_name in lowered:
                is_player_trying_to_open = True

            is_being_unlocked = any(
                update.entity_id == inv_id and update.locked is False
                for update in (event.updated_entities or [])
            )

            if not is_being_unlocked and not is_player_trying_to_open:
                continue

            metadata_json = item.get("metadata_json") or {}
            required_code = str(metadata_json.get("code_to_unlock") or "").strip()
            required_item_id = str(metadata_json.get("item_to_unlock") or "").strip().upper()
            required_rule = str(metadata_json.get("rule_to_unlock") or "").strip()

            unlock_allowed = True
            reason = ""

            # 1. Rule validation
            if required_rule:
                is_switch_flag = required_rule in switch_outcome_flags
                flag_active = self._switch_story_flags().get(required_rule, False)

                if is_switch_flag:
                    if not flag_active:
                        unlock_allowed = False
                        reason = f"{item.get('name', 'Container')} stays shut. It seems to require some mechanism to trigger."
                else:
                    if not is_being_unlocked:
                        unlock_allowed = False
                        hinted_actor = ""
                        distract_match = re.search(r"\bdistract\w*\s+([A-Za-z0-9_\- ]{2,60})", required_rule, re.IGNORECASE)
                        if distract_match:
                            hinted_actor = distract_match.group(1).strip(" .,:;!?")

                        if hinted_actor:
                            reason = (
                                f"{item.get('name', 'Container')} stays shut. {hinted_actor} seems to keep a close eye on it. "
                                "A clever distraction might create an opening."
                            )
                        else:
                            reason = (
                                f"{item.get('name', 'Container')} stays shut. The moment does not feel right yet. "
                                "A different approach might open a window."
                            )

            # 2. Code validation
            if unlock_allowed and required_code:
                if not is_being_unlocked or required_code.lower() not in lowered:
                    unlock_allowed = False
                    reason = f"{item.get('name', 'Container')} gives a mocking click. That code won't do the trick."

            # 3. Item validation
            if unlock_allowed and required_item_id:
                inventory_ids = {
                    str(entry.get("id") or "").strip().upper()
                    for entry in (self.avatar.inventory or [])
                    if isinstance(entry, dict)
                }
                if required_item_id.upper() not in inventory_ids:
                    unlock_allowed = False
                    reason = f"You need a specific item to unlock {item.get('name', 'Container')}."
                elif not await self._is_key_item_referenced(required_item_id, lowered, item.get("name")):
                    unlock_allowed = False
                    reason = f"You must specify which item you are using to unlock {item.get('name', 'Container')}."
                elif not is_being_unlocked:
                    unlock_allowed = False
                    reason = f"You try using the item to unlock {item.get('name', 'Container')}."

            if not is_being_unlocked:
                unlock_allowed = False

            if not unlock_allowed:
                sanitized_updates: list[WorldEntityUpdate] = []
                for update in (event.updated_entities or []):
                    if update.entity_id == inv_id and update.locked is False:
                        continue
                    sanitized_updates.append(update)
                sanitized_updates.append(WorldEntityUpdate(entity_id=inv_id, locked=True))
                event.updated_entities = sanitized_updates

                event.completed_quest_ids = []
                event.earned_award_keys = []
                event.new_inventory_items = []
                event.updated_inventory_items = []
                event.removed_inventory_item_ids = []
                event.spawned_items = []

                reasons.append(reason or f"{item.get('name', 'Container')} stays locked.")

        return reasons

    async def _enforce_exit_unlock_guardrails(self, event: GameEvent, user_msg: str) -> list[str]:
        lowered = (user_msg or "").strip().lower()
        if not lowered:
            return []

        exit_res = await self.db.execute(
            select(WorldExit).where(
                WorldExit.session_id == self.game_id,
                or_(
                    WorldExit.from_scene_id == self.state.current_scene_id,
                    and_(
                        WorldExit.to_scene_id == self.state.current_scene_id,
                        WorldExit.exit_type == "bidirectional"
                    )
                )
            )
        )
        db_scene_exits = list(exit_res.scalars().all())
        scene_exits = []
        for e in db_scene_exits:
            if e.from_scene_id == self.state.current_scene_id:
                scene_exits.append(e)
            else:
                scene_exits.append(WorldExit(
                    id=e.id,
                    template_id=e.template_id,
                    session_id=e.session_id,
                    from_scene_id=e.to_scene_id,
                    to_scene_id=e.from_scene_id,
                    label=e.label,
                    exit_type=e.exit_type,
                    is_locked=e.is_locked,
                    lock_description=e.lock_description,
                    code_to_unlock=e.code_to_unlock,
                    item_to_unlock=e.item_to_unlock,
                    rule_to_unlock=e.rule_to_unlock
                ))

        reasons = []
        for ex in scene_exits:
            if not ex.is_locked:
                continue

            # Is the GM trying to unlock it, or is the player trying to traverse it?
            is_being_unlocked = False
            for up in (event.updated_exits or []):
                if up.from_scene_id == ex.from_scene_id and up.to_scene_id == ex.to_scene_id and not up.is_locked:
                    is_being_unlocked = True
                    break

            is_being_traversed = event.new_scene_id == ex.to_scene_id

            if not (is_being_unlocked or is_being_traversed):
                continue

            required_code = str(ex.code_to_unlock or "").strip()
            required_item_id = str(ex.item_to_unlock or "").strip().upper()
            required_rule = str(ex.rule_to_unlock or "").strip()

            unlock_allowed = True
            reason = ""

            if required_rule:
                if not is_being_unlocked:
                    unlock_allowed = False
                    reason = f"{ex.label} is locked."

            # Code validation: language-agnostic substring check (see container guardrails).
            if unlock_allowed and required_code:
                if required_code.lower() not in lowered:
                    unlock_allowed = False
                    reason = f"{ex.label} answers with a cold red blink. That code won't open the way."

            if unlock_allowed and required_item_id:
                inventory_ids = {
                    str(item.get("id") or "").strip().upper()
                    for item in (self.avatar.inventory or [])
                    if isinstance(item, dict)
                }
                if required_item_id.upper() not in inventory_ids:
                    unlock_allowed = False
                    reason = f"You need a specific item to unlock {ex.label}."
                elif not await self._is_key_item_referenced(required_item_id, lowered, ex.label):
                    unlock_allowed = False
                    reason = f"You must specify which item you are using to unlock {ex.label}."

            if not unlock_allowed:
                # Force stays locked in event.updated_exits
                sanitized_updates: list[ExitUpdate] = []
                for up in (event.updated_exits or []):
                    if up.from_scene_id == ex.from_scene_id and up.to_scene_id == ex.to_scene_id:
                        continue
                    sanitized_updates.append(up)
                sanitized_updates.append(ExitUpdate(from_scene_id=ex.from_scene_id, to_scene_id=ex.to_scene_id, is_locked=True))
                event.updated_exits = sanitized_updates

                # Block movement
                if event.new_scene_id == ex.to_scene_id:
                    event.new_scene_id = None
                    event.exit_label = None
                    event.scene_label = None

                # Clear quest completions and awards since the movement/interaction failed
                event.completed_quest_ids = []
                event.earned_award_keys = []
                event.new_inventory_items = []
                event.updated_inventory_items = []
                event.removed_inventory_item_ids = []
                event.spawned_items = []

                reasons.append(reason or f"{ex.label} stays locked.")
            else:
                # Automatically add unlock status to event.updated_exits so the DB updates
                if not event.updated_exits:
                    event.updated_exits = []
                already_present = False
                for up in event.updated_exits:
                    if up.from_scene_id == ex.from_scene_id and up.to_scene_id == ex.to_scene_id:
                        up.is_locked = False
                        already_present = True
                        break
                if not already_present:
                    event.updated_exits.append(ExitUpdate(
                        from_scene_id=ex.from_scene_id,
                        to_scene_id=ex.to_scene_id,
                        is_locked=False
                    ))

        return reasons

    async def _enforce_switch_transition_guardrails(self, event: GameEvent, user_msg: str) -> list[str]:
        if not event.updated_entities:
            return []

        reasons = []
        lowered = (user_msg or "").strip().lower()
        session_states = self.state.entity_states or {}

        for update in list(event.updated_entities):
            if not update.switch_state:
                continue

            eid = update.entity_id
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.id == eid,
                    WorldEntity.session_id == self.game_id,
                )
            )
            switch_entity = ent_res.scalars().first()
            if not switch_entity or str(switch_entity.item_type or "").upper() != "SWITCH":
                continue

            entry = dict(session_states.get(switch_entity.id) or {})
            metadata_json = switch_entity.metadata_json or {}
            config = metadata_json.get("switch") or {}
            configured_current = config.get("initial_state") or metadata_json.get("switch_initial_state") or ""
            current_state = str(entry.get("switch_state") or configured_current).strip().upper()
            target_state = str(update.switch_state).strip().upper()

            if current_state == target_state:
                continue

            transitions = metadata_json.get("switch_transitions") or config.get("transitions") or []
            trans = None
            if isinstance(transitions, list):
                wildcard_trans = None
                for t in transitions:
                    if not isinstance(t, dict):
                        continue
                    from_s = str(t.get("from") or t.get("from_state") or "").strip().upper()
                    to_s = str(t.get("to") or t.get("to_state") or "").strip().upper()
                    if not to_s or to_s != target_state:
                        continue
                    if from_s and from_s == current_state:
                        trans = t
                        break
                    if not from_s and wildcard_trans is None:
                        wildcard_trans = t
                if trans is None:
                    trans = wildcard_trans

            transition_allowed = True
            reason = ""

            if trans is not None:
                gates = trans.get("gates") if isinstance(trans.get("gates"), dict) else {}
                required_item = str(gates.get("item") or trans.get("required_item") or "").strip().upper()
                required_code = str(gates.get("code") or trans.get("code") or "").strip()
                required_rule = str(gates.get("rule") or trans.get("required_rule") or "").strip()
                fail_message = str(trans.get("fail_message") or "").strip()

                # Code validation: language-agnostic substring check (see container guardrails).
                if required_code:
                    if required_code.lower() not in lowered:
                        transition_allowed = False
                        reason = fail_message or f"{switch_entity.name} does not move."

                if transition_allowed and required_item:
                    inventory_ids = {
                        str(item.get("id") or "").strip().upper()
                        for item in (self.avatar.inventory or [])
                        if isinstance(item, dict)
                    }
                    if required_item.upper() not in inventory_ids:
                        transition_allowed = False
                        reason = fail_message or f"{switch_entity.name} does not move."
                    elif not await self._is_key_item_referenced(required_item, lowered, switch_entity.name):
                        transition_allowed = False
                        reason = fail_message or f"You must specify which item you are using on {switch_entity.name}."

                if transition_allowed and required_rule:
                    if not self._switch_story_flags().get(required_rule, False):
                        transition_allowed = False
                        reason = fail_message or f"{switch_entity.name} does not move."

            if not transition_allowed:
                update.switch_state = current_state
                reasons.append(reason or f"{switch_entity.name} cannot be flipped.")
                event.completed_quest_ids = []
                event.earned_award_keys = []
                event.new_inventory_items = []
                event.updated_inventory_items = []
                event.removed_inventory_item_ids = []
                event.spawned_items = []

        return reasons

    async def _enforce_quest_and_award_guardrails(self, event: GameEvent) -> None:
        """
        Validates that any quest completed or award granted in this turn
        does not require interaction with an entity (NPC or Object) that is
        physically inaccessible to the player.
        """
        if not event.completed_quest_ids and not event.earned_award_keys:
            return

        # Fetch all session entities to know their location/state
        entity_res = await self.db.execute(
            select(WorldEntity).where(WorldEntity.session_id == self.game_id)
        )
        all_entities = list(entity_res.scalars().all())

        # Build a set of accessible entity IDs and names.
        # An entity is accessible if it is in the current scene, or in the player's inventory/equipment,
        # or if it is being spawned/added to inventory in this turn.
        accessible_entity_ids: set[str] = set()
        accessible_entity_names: set[str] = set()

        def mark_accessible(ent_id: str | None, ent_name: str | None) -> None:
            if ent_id:
                accessible_entity_ids.add(ent_id.lower().strip())
            if ent_name:
                accessible_entity_names.add(ent_name.lower().strip())

        current_scene_id = self.state.current_scene_id

        # 1. Database-backed check
        for entity in all_entities:
            # Check if present in the current scene
            if entity.current_scene_id == current_scene_id:
                mark_accessible(entity.id, entity.name)
            
            # Check if NPC in current scene has items in inventory
            if entity.entity_type == "NPC" and entity.current_scene_id == current_scene_id:
                npc_inv = entity.inventory or []
                for item in npc_inv:
                    if isinstance(item, dict):
                        mark_accessible(item.get("id"), item.get("name"))

            # Check if marked as in player's inventory in DB
            if entity.is_in_inventory:
                mark_accessible(entity.id, entity.name)

        # 2. Check avatar's active inventory & equipment list
        if self.avatar.inventory:
            for item in self.avatar.inventory:
                if isinstance(item, dict):
                    mark_accessible(item.get("id"), item.get("name"))
        
        if self.avatar.equipment:
            for slot, item in self.avatar.equipment.items():
                if isinstance(item, dict):
                    mark_accessible(item.get("id"), item.get("name"))

        # 3. Check event updates (newly added/spawned/moved)
        if event.new_inventory_items:
            for item in event.new_inventory_items:
                mark_accessible(item.id, item.name)

        if event.spawned_items:
            for item in event.spawned_items:
                mark_accessible(item.id, item.name)

        if event.moved_entities:
            for move in event.moved_entities:
                if move.to_scene_id == current_scene_id:
                    matching_ent = next((e for e in all_entities if e.id == move.entity_id), None)
                    ent_name = matching_ent.name if matching_ent else None
                    mark_accessible(move.entity_id, ent_name)

        # Helper to check if a text (e.g. goal, requirement, description) mentions
        # an inaccessible entity.
        def has_inaccessible_entity_dependency(text: str | None) -> bool:
            if not text:
                return False
            
            text_lower = text.lower()
            for entity in all_entities:
                ent_id = entity.id
                ent_name = entity.name
                if not ent_id and not ent_name:
                    continue
                
                # Check if this specific entity is mentioned in the requirement/goal text
                # We use word boundaries to prevent partial matches (e.g. "key" in "keyboard")
                mentioned = False
                if ent_id:
                    pattern_id = r'\b' + re.escape(ent_id.lower()) + r'\b'
                    if re.search(pattern_id, text_lower):
                        mentioned = True
                if not mentioned and ent_name:
                    pattern_name = r'\b' + re.escape(ent_name.lower()) + r'\b'
                    if re.search(pattern_name, text_lower):
                        mentioned = True
                
                if mentioned:
                    # Entity is mentioned. Is it accessible?
                    is_accessible = False
                    if ent_id and ent_id.lower().strip() in accessible_entity_ids:
                        is_accessible = True
                    elif ent_name and ent_name.lower().strip() in accessible_entity_names:
                        is_accessible = True
                    
                    if not is_accessible:
                        logger.info(
                            "[Quest/Award Guardrail] Blocked because text '%s' mentions inaccessible entity '%s' (%s)",
                            text, ent_name or "", ent_id or ""
                        )
                        return True
            return False

        # Validate completed quests
        if event.completed_quest_ids:
            validated_quest_ids = []
            for qid in event.completed_quest_ids:
                quest = next((q for q in (self.state.quests or []) if q.get("id") == qid), None)
                if not quest:
                    validated_quest_ids.append(qid)
                    continue
                
                goal = quest.get("goal")
                desc = quest.get("description")
                if has_inaccessible_entity_dependency(goal) or has_inaccessible_entity_dependency(desc):
                    logger.info("[Quest Guardrail] Blocked completion of quest '%s' due to inaccessible entity dependency.", qid)
                    continue
                validated_quest_ids.append(qid)
            event.completed_quest_ids = validated_quest_ids

        # Validate earned awards
        if event.earned_award_keys:
            validated_award_keys = []
            for key in event.earned_award_keys:
                award = next((aw for aw in (self.adventure.awards or []) if aw.get("key") == key), None)
                if not award:
                    validated_award_keys.append(key)
                    continue
                
                req = award.get("requirement")
                desc = award.get("description")
                if has_inaccessible_entity_dependency(req) or has_inaccessible_entity_dependency(desc):
                    logger.info("[Award Guardrail] Blocked award '%s' due to inaccessible entity dependency.", key)
                    continue
                validated_award_keys.append(key)
            event.earned_award_keys = validated_award_keys


    async def _handle_read_action_unlock(self, read_target: str) -> None:
        """Finds the read item and checks if it unlocks any special actions."""
        target_lower = read_target.strip().lower()
        
        # 1. Search player inventory
        for item in (self.avatar.inventory or []):
            if isinstance(item, dict):
                if item.get("name", "").lower() == target_lower or item.get("id", "").lower() == target_lower:
                    if str(item.get("item_type") or "").upper() == "READABLE":
                        await self._check_special_action_unlocks("READ_ITEM", item.get("id"))
                        return
                        
        # 2. Search scene objects
        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type == "OBJECT",
                WorldEntity.is_hidden.is_(False),
                WorldEntity.item_type == "READABLE"
            )
        )
        candidates = ent_res.scalars().all()
        for candidate in candidates:
            if candidate.id and candidate.id.lower() == target_lower:
                await self._check_special_action_unlocks("READ_ITEM", candidate.id)
                return
            if candidate.name and candidate.name.lower() == target_lower:
                await self._check_special_action_unlocks("READ_ITEM", candidate.id)
                return

    async def _check_special_action_unlocks(self, condition_type: str, target_id: str) -> None:
        """Checks if a readable item ID or found item ID unlocks any special actions for the protagonist."""
        if not target_id:
            return
            
        player_specials = self.avatar.stats.get("special_actions") or []
        unlocked_actions = list(self.avatar.stats.get("unlocked_actions") or [])
        
        updated_unlocked = False
        for action in player_specials:
            action_id = action.get("id")
            if action_id in unlocked_actions:
                continue
                
            is_locked = action.get("is_locked", False)
            cond_type = action.get("unlock_condition_type")
            cond_target = action.get("unlock_condition_target")
            
            if is_locked and cond_type == condition_type and cond_target == target_id:
                unlocked_actions.append(action_id)
                updated_unlocked = True
                msg = f"✨ Spezialaktion freigeschaltet: {action.get('name')}! ✨"
                await self._save_chat_message("system", msg)
                
        if updated_unlocked:
            stats = dict(self.avatar.stats or {})
            stats["unlocked_actions"] = unlocked_actions
            self.avatar.stats = stats
            flag_modified(self.avatar, "stats")
            await self.db.commit()

