"""Inspect/search visibility guard: players can only examine what is actually reachable.

The guard is language-independent: a target is only blocked when it names an entity of
this adventure that is not reachable right now. Anything else (e.g. "the room" in any
language) passes, so no word lists are needed.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.api.routes.adventures.guardrails.base import entity_view
from backend.core.prompts import INSPECT_SEARCH_INTENT_GUARD_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MIN_TOKEN_LENGTH = 3
_STRIP_LEADING = " \t\n\r\v\f:,-"
_STRIP_TRAILING = " \t\n\r\v\f.,!?:;"


class InspectGuardMixin:
    """Blocks inspect/search on entities that exist but are out of reach."""

    @staticmethod
    def _sanitize_inspect_or_search_target(raw_target: str) -> str | None:
        """Strips quotes and punctuation from an extracted target; None when nothing remains."""
        target = (raw_target or "").strip().strip("\"'")
        target = target.lstrip(_STRIP_LEADING).rstrip(_STRIP_TRAILING)
        return target or None

    async def _extract_inspect_or_search_target(self, user_msg: str) -> str | None:
        """Extracts the inspect/search target from a slash command or via a small LLM call."""
        text = " ".join((user_msg or "").strip().split())
        if not text:
            return None
        if text.lower().startswith(("/inspect", "/search")):
            return self._sanitize_inspect_or_search_target(
                text.split(" ", 1)[1] if " " in text else ""
            )

        try:
            llm, model = self._small_llm()
            raw_intent = await llm.aexecute_simple_task(
                INSPECT_SEARCH_INTENT_GUARD_SYSTEM_PROMPT,
                text,
                model,
                adventure_id=self.adventure.id,
                game_id=self.game_id,
                operation="chat_turn",
                phase="inspect_search_intent_guard",
            )
        except Exception as exc:
            logger.debug("[Turn %s] Inspect/search intent guard skipped: %s", self.game_id, exc)
            return None

        parsed = self._parse_json_object(raw_intent) or {}
        action = str(parsed.get("action") or "").strip().lower()
        if action not in {"inspect", "search"} or parsed.get("target") is None:
            return None
        return self._sanitize_inspect_or_search_target(str(parsed["target"]))

    def _add_token(self, bucket: set[str], raw: Any) -> None:
        token = self._normalize_target_token(str(raw or ""))
        if token:
            bucket.add(token)

    async def _collect_inspect_search_visibility_tokens(self) -> tuple[set[str], set[str]]:
        """Returns (reachable, unreachable) normalized names/IDs of every entity and carried item."""
        allowed: set[str] = set()
        disallowed: set[str] = set()
        states = self.state.entity_states or {}
        current_scene = self.state.current_scene_id

        for ent in await self._session_entities():
            view = entity_view(ent, states)
            present = view.scene_id == current_scene and not view.hidden
            bucket = allowed if present and not view.in_inventory else disallowed
            self._add_token(bucket, ent.id)
            self._add_token(bucket, ent.name)
            if (ent.entity_type or "").upper() != "NPC":
                continue
            npc_inventory = (states.get(ent.id, {}) or {}).get("inventory", ent.inventory or [])
            inventory_bucket = allowed if present else disallowed
            for item in npc_inventory if isinstance(npc_inventory, list) else []:
                if isinstance(item, dict):
                    self._add_token(inventory_bucket, item.get("id"))
                    self._add_token(inventory_bucket, item.get("name"))

        for item in self.avatar.inventory or []:
            if isinstance(item, dict):
                self._add_token(allowed, item.get("id"))
                self._add_token(allowed, item.get("name"))

        disallowed.difference_update(allowed)
        return allowed, disallowed

    @staticmethod
    def _target_matches(normalized_target: str, tokens: set[str]) -> bool:
        if normalized_target in tokens:
            return True
        return any(tok in normalized_target for tok in tokens if len(tok) >= MIN_TOKEN_LENGTH)

    async def _is_inspect_or_search_target_visible(self, target_hint: str) -> bool:
        """True when the target names something in the scene, a local NPC inventory or the player's inventory."""
        normalized = self._normalize_target_token(target_hint)
        if not normalized:
            return True
        allowed, _disallowed = await self._collect_inspect_search_visibility_tokens()
        return self._target_matches(normalized, allowed)

    async def _guard_non_visible_inspect_or_search(self, user_msg: str) -> str | None:
        """Returns a blocking system message if the player targets a known but unreachable entity."""
        normalized_message = self._normalize_target_token(user_msg)
        if not normalized_message:
            return None
        allowed, disallowed = await self._collect_inspect_search_visibility_tokens()
        if not any(tok in normalized_message for tok in disallowed if len(tok) >= MIN_TOKEN_LENGTH):
            return None

        target_hint = await self._extract_inspect_or_search_target(user_msg)
        normalized_target = self._normalize_target_token(target_hint or "")
        if not normalized_target:
            return None
        # Only block known entities that are out of reach; generic words ("room", "Zimmer",
        # "la pièce", ...) never match an entity and therefore pass in every language.
        if not self._target_matches(normalized_target, disallowed):
            return None
        if self._target_matches(normalized_target, allowed):
            return None
        return (
            f"You cannot inspect or search '{target_hint}' right now. "
            "Only objects in the current scene and items from your inventory or local NPC inventories are available."
        )
