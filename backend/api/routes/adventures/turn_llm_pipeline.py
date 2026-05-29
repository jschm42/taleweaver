from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core import prompts
from backend.core.llm_logger import log_structured_event
from backend.engine.memory_manager import MemoryManager
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)


@dataclass
class TurnLlmContext:
    history: list[dict[str, str]]
    entities: list[WorldEntity]
    all_entities: list[WorldEntity]
    exits: list[WorldExit]
    all_scenes: list[WorldScene]
    mechanics_system_prompt: str
    narration_system_prompt: str
    mechanics_awards: list[dict]
    small_model_provider: str
    complex_model_provider: str
    small_model: str
    complex_model: str


class TurnLlmContextBuilder:
    """Builds the heavy LLM context and prompt prelude for one turn cycle."""

    def __init__(self, manager: Any):
        self.manager = manager

    async def build_context(self, user_msg: str, language: str | None) -> TurnLlmContext:
        db_start = time.perf_counter()
        hist_res = await self.manager.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == self.manager.state.session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        history = [{"role": m.role, "content": m.content} for m in hist_res.scalars().all()]

        scene_res = await self.manager.db.execute(
            select(WorldScene).where(
                WorldScene.id == self.manager.state.current_scene_id,
                WorldScene.session_id == self.manager.game_id,
            )
        )
        current_scene = scene_res.scalars().first()

        all_ent_res = await self.manager.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.manager.game_id,
                WorldEntity.is_in_inventory.is_(False),
            )
        )
        all_entities = list(all_ent_res.scalars().all())

        exit_res = await self.manager.db.execute(
            select(WorldExit).where(
                WorldExit.from_scene_id == self.manager.state.current_scene_id,
                WorldExit.session_id == self.manager.game_id,
            )
        )
        exits = list(exit_res.scalars().all())

        overrides = self.manager.state.entity_states or {}
        for ent in all_entities:
            if ent.id not in overrides:
                continue
            ov = overrides[ent.id]
            if "hp" in ov:
                ent.hp = ov["hp"]
            if "mana" in ov:
                ent.mana = ov["mana"]
            if "stamina" in ov:
                ent.stamina = ov["stamina"]
            if "spatial_position" in ov:
                ent.spatial_position = ov["spatial_position"]
            if "name" in ov:
                ent.name = ov["name"]
            if "description" in ov:
                ent.description = ov["description"]
            if "current_scene_id" in ov:
                ent.current_scene_id = ov["current_scene_id"]
            if "is_hidden" in ov:
                ent.is_hidden = ov["is_hidden"]
            if "is_in_inventory" in ov:
                ent.is_in_inventory = ov["is_in_inventory"]
            if "inventory" in ov:
                ent.inventory = ov["inventory"]
            ent.is_defeated = bool(ov.get("is_defeated", False))

        container_payloads = [
            {"item_type": e.item_type, "inventory": e.inventory}
            for e in all_entities
        ]
        contained_item_ids = AdventureLogic.collect_container_item_ids(container_payloads)

        scene_entities_all = [
            e
            for e in all_entities
            if e.current_scene_id == self.manager.state.current_scene_id
            and not getattr(e, "is_in_inventory", False)
            and str(e.id or "") not in contained_item_ids
        ]
        entities = [e for e in scene_entities_all if not getattr(e, "is_hidden", False)]
        hidden_entities = [e for e in scene_entities_all if getattr(e, "is_hidden", False)]

        other_npcs = [
            e
            for e in all_entities
            if e.current_scene_id != self.manager.state.current_scene_id
            and e.entity_type == "NPC"
            and not getattr(e, "is_hidden", False)
        ]

        all_scenes_res = await self.manager.db.execute(
            select(WorldScene).where(WorldScene.session_id == self.manager.game_id)
        )
        all_scenes = list(all_scenes_res.scalars().all())
        scene_map = {s.id: s.label for s in all_scenes}

        db_duration = time.perf_counter() - db_start
        logger.debug("[Turn %s] LLM Context DB prep took %.4fs", self.manager.game_id, db_duration)

        mechanics_system_prompt = MemoryManager.build_context(
            self.manager.avatar,
            self.manager.adventure.original_prompt or "",
            history,
            current_scene=current_scene,
            entities=entities,
            exits=exits,
            in_game_time=self.manager.state.in_game_time,
            awards=self.manager.adventure.awards,
            plot=self.manager.state.plot or self.manager.adventure.plot,
            rules=self.manager.state.rules or self.manager.adventure.rules,
            walkthrough=self.manager.state.walkthrough or self.manager.adventure.walkthrough,
            completed_condition=self.manager.state.completed_condition or self.manager.adventure.completed_condition,
            gameover_condition=self.manager.state.gameover_condition or self.manager.adventure.gameover_condition,
            time_system=self.manager.state.time_system or self.manager.adventure.time_system or "calendar",
            time_config=self.manager.state.time_config or self.manager.adventure.time_config,
            is_adventure_generator=self.manager.adventure.is_adventure_generator,
            location_detail_level="concise",
            other_npcs=other_npcs,
            scene_map=scene_map,
            hidden_entities=hidden_entities,
        )[0]["content"]

        narration_system_prompt = MemoryManager.build_context(
            self.manager.avatar,
            self.manager.adventure.original_prompt or "",
            history,
            current_scene=current_scene,
            entities=entities,
            exits=exits,
            in_game_time=self.manager.state.in_game_time,
            awards=self.manager.adventure.awards,
            plot=self.manager.state.plot or self.manager.adventure.plot,
            rules=self.manager.state.rules or self.manager.adventure.rules,
            walkthrough=self.manager.state.walkthrough or self.manager.adventure.walkthrough,
            completed_condition=self.manager.state.completed_condition or self.manager.adventure.completed_condition,
            gameover_condition=self.manager.state.gameover_condition or self.manager.adventure.gameover_condition,
            time_system=self.manager.state.time_system or self.manager.adventure.time_system or "calendar",
            time_config=self.manager.state.time_config or self.manager.adventure.time_config,
            is_adventure_generator=self.manager.adventure.is_adventure_generator,
            location_detail_level="full",
            # Keep off-scene NPC metadata out of narration context to avoid
            # unintended dialogue from NPCs that are not physically present.
            other_npcs=None,
            scene_map=scene_map,
            hidden_entities=hidden_entities,
        )[0]["content"]

        notes_prompt_block = self.manager._build_gm_notes_prompt_block()
        mechanics_system_prompt += notes_prompt_block
        narration_system_prompt += notes_prompt_block
        mechanics_awards = self.manager._build_mechanics_awards()

        mechanics_prompt_chars = len(mechanics_system_prompt or "")
        narration_prompt_chars = len(narration_system_prompt or "")
        prompt_delta_chars = narration_prompt_chars - mechanics_prompt_chars
        prompt_reduction_pct = (
            round((prompt_delta_chars / narration_prompt_chars) * 100, 2)
            if narration_prompt_chars
            else 0.0
        )

        log_structured_event(
            "gm.turn.pipeline.context",
            adventure_id=self.manager.adventure.id,
            game_id=self.manager.game_id,
            operation="chat_turn",
            phase="context",
            db_prep_ms=round(db_duration * 1000, 2),
            history_count=len(history),
            history_chars=sum(len(m.get("content") or "") for m in history),
            mechanics_system_prompt_chars=mechanics_prompt_chars,
            narration_system_prompt_chars=narration_prompt_chars,
            prompt_delta_chars=prompt_delta_chars,
            prompt_reduction_pct=prompt_reduction_pct,
            entities_count=len(entities),
            exits_count=len(exits),
            mechanics_awards_count=len(mechanics_awards),
            strict_rules=bool(self.manager.adventure.strict_rules),
            is_adventure_generator=bool(self.manager.adventure.is_adventure_generator),
        )

        if language:
            logger.info(
                "[Turn %s] Bable Fish Active: Target Language = %s",
                self.manager.game_id,
                language,
            )
            translation_instruction = (
                "\n\n--- BABLE FISH TRANSLATION PROTOCOL ---\n"
                f"TARGET LANGUAGE: {language.upper()}\n"
                f"INSTRUCTION: You MUST translate ALL your output (narration, dialogue, descriptions) into {language}. "
                "Do NOT respond in English or the original world language if it differs. "
                "Note: The chat history may contain messages in various languages due to previous Bable Fish settings. "
                f"IGNORE those languages and strictly use {language} for the current turn. "
                f"The player has activated their Bable Fish, so everything they hear/see must be in {language}."
                "\n----------------------------------------\n"
            )
            mechanics_system_prompt += translation_instruction
            narration_system_prompt += translation_instruction

        if user_msg == "[EVALUATE STATE]":
            technical_instruction = (
                "\n\nIMPORTANT: The player just synchronized their character sheet or world state (e.g., closing a menu). "
                "This is a TECHNICAL turn. Respond only if something meaningful changed (e.g., equipment effects). "
                "Do NOT list available actions, do NOT provide suggestions, and do NOT use meta-formatting like '---' or 'You can:'. "
                "Keep the narrative flow natural if you speak at all."
            )
            mechanics_system_prompt += technical_instruction
            narration_system_prompt += technical_instruction

        llm_settings = self.manager.user.llm_settings or {}
        small_model_provider = (
            llm_settings.get("small_model_provider")
            or llm_settings.get("complex_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        complex_model_provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        small_model = llm_settings.get("small_model") or "gpt-4o-mini"
        complex_model = llm_settings.get("complex_model") or "gpt-4o"

        return TurnLlmContext(
            history=history,
            entities=entities,
            all_entities=all_entities,
            exits=exits,
            all_scenes=all_scenes,
            mechanics_system_prompt=mechanics_system_prompt,
            narration_system_prompt=narration_system_prompt,
            mechanics_awards=mechanics_awards,
            small_model_provider=small_model_provider,
            complex_model_provider=complex_model_provider,
            small_model=small_model,
            complex_model=complex_model,
        )
