from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.turn_context_helpers import (
    TECHNICAL_TURN_INSTRUCTION,
    apply_entity_overrides,
    bable_fish_instruction,
    orient_exits,
    resolve_model_settings,
    resolve_sequence_guidance,
)
from backend.core.llm_logger import log_structured_event
from backend.engine.rules.crafting_recipes import is_recipe
from backend.engine.rules.soft_rules import (
    build_soft_rules_prompt_block,
    fired_counts,
    sequence_soft_rules,
)
from backend.engine.sessions.memory_manager import MemoryManager
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)


# Only the tail of the chat log is needed for Pass 1 context and generator tool intents;
# Pass 2 loads its own memory window.
RECENT_HISTORY_LIMIT = 12


@dataclass
class TurnLlmContext:
    history: list[dict[str, str]]
    entities: list[WorldEntity]
    all_entities: list[WorldEntity]
    exits: list[WorldExit]
    all_scenes: list[WorldScene]
    global_unlock_rules_prompt_block: str
    # Static prompt prefixes (stable between scene/sequence changes -> prompt-cache friendly)
    mechanics_static_prompt: str
    narration_static_prompt: str
    # Volatile CURRENT STATE blocks (sent in the latest user message)
    mechanics_state_block: str
    narration_state_block: str
    mechanics_awards: list[dict]
    small_model_provider: str
    complex_model_provider: str
    small_model: str
    complex_model: str
    compression_model_provider: str = "openai"
    compression_model: str = ""
    compression_max_tokens: int = 4096

    @property
    def mechanics_system_prompt(self) -> str:
        """Self-contained mechanics prompt (static + state) for single-shot callers."""
        return f"{self.mechanics_static_prompt}\n\n{self.mechanics_state_block}"


@dataclass
class _WorldSnapshot:
    current_scene: WorldScene | None
    all_entities: list[WorldEntity]
    exits: list[WorldExit]
    all_scenes: list[WorldScene]
    all_exits: list[WorldExit]


class TurnLlmContextBuilder:
    """Builds the heavy LLM context and prompt prelude for one turn cycle."""

    def __init__(self, manager: Any):
        self.manager = manager

    @staticmethod
    def _is_entity_locked_by_requirements(entity: WorldEntity, overrides: dict[str, Any]) -> bool:
        state_locked = (
            (overrides.get(entity.id) or {}).get("locked") if isinstance(overrides, dict) else None
        )
        if isinstance(state_locked, bool):
            return state_locked

        metadata = dict(getattr(entity, "metadata_json", None) or {})
        return bool(
            str(metadata.get("code_to_unlock") or "").strip()
            or str(metadata.get("item_to_unlock") or "").strip()
            or str(metadata.get("rule_to_unlock") or "").strip()
        )

    def _build_global_unlock_rules_prompt_block(
        self,
        all_entities: list[WorldEntity],
        all_exits: list[WorldExit],
        all_scenes: list[WorldScene],
        overrides: dict[str, Any],
    ) -> str:
        scene_label_map = {str(scene.id): str(scene.label or scene.id) for scene in all_scenes}

        container_rules: list[dict[str, str]] = []
        for ent in all_entities:
            if str(getattr(ent, "entity_type", "") or "").upper() != "OBJECT":
                continue
            if str(getattr(ent, "item_type", "") or "").upper() != "CONTAINER":
                continue
            if not self._is_entity_locked_by_requirements(ent, overrides):
                continue

            metadata = dict(getattr(ent, "metadata_json", None) or {})
            rule_to_unlock = str(metadata.get("rule_to_unlock") or "").strip()
            if not rule_to_unlock:
                continue

            scene_id = str(getattr(ent, "current_scene_id", "") or "")
            container_rules.append(
                {
                    "entity_id": str(ent.id or "").strip(),
                    "name": str(ent.name or ent.id or "container").strip(),
                    "scene_id": scene_id,
                    "scene_label": scene_label_map.get(scene_id, scene_id),
                    "rule_to_unlock": rule_to_unlock,
                }
            )

        exit_rules: list[dict[str, str]] = []
        for ex in all_exits:
            if not bool(getattr(ex, "is_locked", False)):
                continue
            rule_to_unlock = str(getattr(ex, "rule_to_unlock", "") or "").strip()
            if not rule_to_unlock:
                continue

            from_scene_id = str(getattr(ex, "from_scene_id", "") or "")
            to_scene_id = str(getattr(ex, "to_scene_id", "") or "")
            exit_rules.append(
                {
                    "from_scene_id": from_scene_id,
                    "from_scene_label": scene_label_map.get(from_scene_id, from_scene_id),
                    "to_scene_id": to_scene_id,
                    "to_scene_label": scene_label_map.get(to_scene_id, to_scene_id),
                    "label": str(getattr(ex, "label", "") or "").strip(),
                    "rule_to_unlock": rule_to_unlock,
                }
            )

        if not container_rules and not exit_rules:
            return ""

        payload = {
            "containers": container_rules,
            "exits": exit_rules,
        }

        return (
            "\n\nGLOBAL SOFT UNLOCK RULES (ADVENTURE-WIDE):\n"
            "- These locks may be unlocked from ANY scene when the player's action clearly fulfills the rule this turn.\n"
            "- For container unlocks, emit `updated_entities` with the exact `entity_id` and `locked=false`.\n"
            "- For exit unlocks, emit `updated_exits` with exact `from_scene_id`, `to_scene_id`, and `is_locked=false`.\n"
            "- Do not unlock speculatively; only unlock when the action actually satisfies the rule.\n"
            f"RULE_LOCKS_JSON: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
        )

    async def _load_recent_history(self) -> list[dict[str, str]]:
        hist_res = await self.manager.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == self.manager.state.session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(RECENT_HISTORY_LIMIT)
        )
        return [
            {"role": m.role, "content": m.content} for m in reversed(list(hist_res.scalars().all()))
        ]

    async def _load_world(self) -> _WorldSnapshot:
        db = self.manager.db
        game_id = self.manager.game_id
        current_scene_id = self.manager.state.current_scene_id

        scene_res = await db.execute(
            select(WorldScene).where(
                WorldScene.id == current_scene_id, WorldScene.session_id == game_id
            )
        )
        ent_res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == game_id, WorldEntity.is_in_inventory.is_(False)
            )
        )
        exit_res = await db.execute(
            select(WorldExit).where(
                WorldExit.session_id == game_id,
                or_(
                    WorldExit.from_scene_id == current_scene_id,
                    and_(
                        WorldExit.to_scene_id == current_scene_id,
                        WorldExit.exit_type == "bidirectional",
                    ),
                ),
            )
        )
        scenes_res = await db.execute(select(WorldScene).where(WorldScene.session_id == game_id))
        all_exits_res = await db.execute(select(WorldExit).where(WorldExit.session_id == game_id))

        all_entities = list(ent_res.scalars().all())
        apply_entity_overrides(all_entities, self.manager.state.entity_states or {})
        return _WorldSnapshot(
            current_scene=scene_res.scalars().first(),
            all_entities=all_entities,
            exits=orient_exits(list(exit_res.scalars().all()), current_scene_id),
            all_scenes=list(scenes_res.scalars().all()),
            all_exits=list(all_exits_res.scalars().all()),
        )

    def _partition_scene_entities(
        self, all_entities: list[WorldEntity]
    ) -> tuple[list[WorldEntity], list[WorldEntity]]:
        """Returns (visible, hidden) entities lying openly in the current scene.

        CONSTRUCTABLE recipes are meta items; the GM only sees their (hidden) results.
        """
        contained_item_ids = AdventureLogic.collect_container_item_ids(
            [{"item_type": e.item_type, "inventory": e.inventory} for e in all_entities]
        )
        scene_entities = [
            e
            for e in all_entities
            if e.current_scene_id == self.manager.state.current_scene_id
            and not getattr(e, "is_in_inventory", False)
            and str(e.id or "") not in contained_item_ids
            and not is_recipe(e)
        ]
        visible = [e for e in scene_entities if not getattr(e, "is_hidden", False)]
        hidden = [e for e in scene_entities if getattr(e, "is_hidden", False)]
        return visible, hidden

    async def _remember_scene_npcs(self, visible_entities: list[WorldEntity]) -> None:
        """Marks visible NPCs in the current scene as remembered in session state."""
        overrides = dict(self.manager.state.entity_states or {})
        state_modified = False
        for npc in (e for e in visible_entities if e.entity_type == "NPC"):
            if not isinstance(overrides.get(npc.id), dict):
                overrides[npc.id] = {}
            if overrides[npc.id].get("remembered"):
                continue
            overrides[npc.id]["remembered"] = True
            state_modified = True
        if state_modified:
            self.manager.state.entity_states = overrides
            flag_modified(self.manager.state, "entity_states")
            await self.manager.db.flush()

    def _remembered_off_scene_npcs(self, all_entities: list[WorldEntity]) -> list[WorldEntity]:
        entity_states = self.manager.state.entity_states or {}
        return [
            e
            for e in all_entities
            if e.current_scene_id != self.manager.state.current_scene_id
            and e.entity_type == "NPC"
            and not getattr(e, "is_hidden", False)
            and entity_states.get(e.id, {}).get("remembered")
        ]

    def _build_static_prompt(self) -> str:
        state = self.manager.state
        adventure = self.manager.adventure
        walkthrough, end_condition = resolve_sequence_guidance(adventure, state)
        return MemoryManager.build_static_prompt(
            adventure.original_prompt or "",
            plot=state.plot or adventure.plot,
            rules=state.rules or adventure.rules,
            walkthrough=walkthrough,
            completed_condition=end_condition,
            gameover_condition=state.gameover_condition or adventure.gameover_condition,
            is_adventure_generator=adventure.is_adventure_generator,
        )

    def _build_state_blocks(
        self,
        world: _WorldSnapshot,
        visible: list[WorldEntity],
        hidden: list[WorldEntity],
        global_unlock_rules_prompt_block: str,
    ) -> tuple[str, str]:
        """Returns the (mechanics, narration) CURRENT STATE blocks."""
        state = self.manager.state
        adventure = self.manager.adventure
        state_kwargs: dict[str, Any] = {
            "current_scene": world.current_scene,
            "entities": visible,
            "exits": world.exits,
            "in_game_time": state.in_game_time,
            "time_system": state.time_system or adventure.time_system or "calendar",
            "time_config": state.time_config or adventure.time_config,
            "scene_map": {s.id: s.label for s in world.all_scenes},
            "hidden_entities": hidden,
        }
        mechanics_state_block = MemoryManager.build_state_block(
            self.manager.avatar,
            location_detail_level="concise",
            other_npcs=self._remembered_off_scene_npcs(world.all_entities),
            **state_kwargs,
        )
        # Keep off-scene NPC metadata out of narration context to avoid
        # unintended dialogue from NPCs that are not physically present.
        narration_state_block = MemoryManager.build_state_block(
            self.manager.avatar,
            location_detail_level="full",
            other_npcs=None,
            **state_kwargs,
        )
        session_memory_block = (
            self.manager._build_gm_notes_prompt_block()
            + self.manager._build_compressed_history_prompt_block()
            + self.manager._build_world_memories_prompt_block()
        )
        soft_rules_block = build_soft_rules_prompt_block(
            sequence_soft_rules(AdventureLogic.resolve_active_sequence(adventure, state)),
            fired_counts(state.entity_states),
        )
        return (
            mechanics_state_block
            + session_memory_block
            + global_unlock_rules_prompt_block
            + soft_rules_block,
            narration_state_block + session_memory_block,
        )

    async def build_context(self, user_msg: str, language: str | None) -> TurnLlmContext:
        db_start = time.perf_counter()
        history = await self._load_recent_history()
        world = await self._load_world()
        visible, hidden = self._partition_scene_entities(world.all_entities)
        await self._remember_scene_npcs(visible)
        global_unlock_rules_prompt_block = self._build_global_unlock_rules_prompt_block(
            all_entities=world.all_entities,
            all_exits=world.all_exits,
            all_scenes=world.all_scenes,
            overrides=self.manager.state.entity_states or {},
        )
        db_duration = time.perf_counter() - db_start
        logger.debug("[Turn %s] LLM Context DB prep took %.4fs", self.manager.game_id, db_duration)

        static_prompt = self._build_static_prompt()
        mechanics_state_block, narration_state_block = self._build_state_blocks(
            world, visible, hidden, global_unlock_rules_prompt_block
        )
        narration_static_prompt = static_prompt
        if language:
            logger.info(
                "[Turn %s] Bable Fish Active: Target Language = %s", self.manager.game_id, language
            )
            # Only the narration is player-facing; Pass 1 drafts stay in English.
            narration_static_prompt += bable_fish_instruction(language)
        if user_msg == "[EVALUATE STATE]":
            mechanics_state_block += TECHNICAL_TURN_INSTRUCTION
            narration_state_block += TECHNICAL_TURN_INSTRUCTION
        mechanics_awards = self.manager._build_mechanics_awards()

        log_structured_event(
            "gm.turn.pipeline.context",
            adventure_id=self.manager.adventure.id,
            game_id=self.manager.game_id,
            operation="chat_turn",
            phase="context",
            db_prep_ms=round(db_duration * 1000, 2),
            history_count=len(history),
            history_chars=sum(len(m.get("content") or "") for m in history),
            static_prompt_chars=len(static_prompt),
            mechanics_state_chars=len(mechanics_state_block),
            narration_state_chars=len(narration_state_block),
            entities_count=len(visible),
            exits_count=len(world.exits),
            mechanics_awards_count=len(mechanics_awards),
            strict_rules=bool(self.manager.adventure.strict_rules),
            is_adventure_generator=bool(self.manager.adventure.is_adventure_generator),
        )

        return TurnLlmContext(
            history=history,
            entities=visible,
            all_entities=world.all_entities,
            exits=world.exits,
            all_scenes=world.all_scenes,
            global_unlock_rules_prompt_block=global_unlock_rules_prompt_block,
            mechanics_static_prompt=static_prompt,
            narration_static_prompt=narration_static_prompt,
            mechanics_state_block=mechanics_state_block,
            narration_state_block=narration_state_block,
            mechanics_awards=mechanics_awards,
            **resolve_model_settings(self.manager.user.llm_settings or {}),
        )
