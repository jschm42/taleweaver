from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.core.config import settings
from backend.engine.interaction.script_item_apply import (
    apply_player_inventory,
    insert_cloned_entities,
    sync_entity_rows,
)
from backend.engine.interaction.switch_service import SwitchService
from backend.engine.scripting.context import GameContext, ScriptChangeset
from backend.engine.scripting.dialog import store_pending_dialog
from backend.engine.scripting.gm_directions import store_gm_directions
from backend.engine.scripting.llm_proxy import LlmAsker
from backend.engine.scripting.npc_persona import PERSONA_FIELDS, apply_persona
from backend.engine.scripting.runner import ScriptRunner
from backend.engine.scripting.scene_helpers import runner_for_manifest
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)


class TriggerService:
    """Service for resolving deterministic guards and executing transition triggers."""

    @staticmethod
    def is_debug_mode(state: Optional[SessionState] = None) -> bool:
        """Determines if debug mode is active globally or for the session."""
        return bool(
            settings.TALEWEAVER_DEBUG_ENABLED
            or (state is not None and getattr(state, "is_debug_enabled", False))
        )

    @classmethod
    async def build_context(
        cls, db: AsyncSession, state: SessionState, llm_asker: Optional[LlmAsker] = None
    ) -> GameContext:
        """Builds a GameContext instance from session database state."""
        avatar = await cls._load_avatar(db, state)
        avatar_dict = {
            "name": avatar.name if avatar else "Protagonist",
            "hp": avatar.hp if avatar else 100,
            "mana": avatar.mana if avatar else 100,
            "stamina": avatar.stamina if avatar else 100,
            "inventory": list(avatar.inventory or []) if avatar else [],
            "status_effects": list(avatar.status_effects or []) if avatar else [],
        }

        ents_res = await db.execute(
            select(WorldEntity).where(WorldEntity.session_id == state.session_id)
        )
        entities_list = ents_res.scalars().all()
        session_overrides = dict(state.entity_states or {})

        entities_map: dict[str, dict[str, Any]] = {}
        for ent in entities_list:
            if not ent.id:
                continue
            # All columns, like a turn's context: item transfers need inventories and item data.
            ent_dict: dict[str, Any] = {c.name: getattr(ent, c.name) for c in ent.__table__.columns}
            ent_dict.update(
                hp=getattr(ent, "hp", 0) or 0,
                is_defeated=bool(session_overrides.get(ent.id, {}).get("is_defeated", False)),
                metadata_json=dict(ent.metadata_json or {}),
                inventory=list(ent.inventory or []),
            )
            if ent.id in session_overrides:
                ent_dict.update(session_overrides[ent.id])
            entities_map[ent.id] = ent_dict

        script_vars = dict(session_overrides.get("__script_vars__", {}))
        story_flags = dict(session_overrides.get("__switch_story_flags__", {}))

        return GameContext(
            avatar_data=avatar_dict,
            current_scene_id=state.current_scene_id,
            entities=entities_map,
            exit_states=state.exit_states or {},
            quests=state.quests or [],
            script_vars=script_vars,
            in_game_time=state.in_game_time,
            story_flags=story_flags,
            is_debug_enabled=cls.is_debug_mode(state),
            llm_asker=llm_asker,
        )

    @classmethod
    async def evaluate_guard(
        cls, db: AsyncSession, state: SessionState, guard_expression: Optional[str]
    ) -> tuple[bool, Optional[str]]:
        """Evaluates a scripted guard condition against current context."""
        expr = str(guard_expression or "").strip()
        if not expr:
            return True, None
        context = await cls.build_context(db, state)
        return SwitchService.evaluate_gate_expression(expr, context)

    @classmethod
    async def execute_trigger(
        cls,
        db: AsyncSession,
        state: SessionState,
        trigger_name: str,
        target_id: str,
        script_code: Optional[str] = None,
        narrative_text: Optional[str] = None,
        llm_asker: Optional[LlmAsker] = None,
    ) -> list[str]:
        """
        Executes a transition trigger (script + narrative text).
        Persists in-game chat messages and debug notifications when active.
        """
        messages: list[str] = []
        is_debug = cls.is_debug_mode(state)

        if is_debug:
            debug_msg = f"[DEBUG: Trigger fired] {trigger_name} on {target_id}"
            db.add(
                ChatMessage(
                    session_id=state.session_id,
                    role="system",
                    content=debug_msg,
                )
            )
            messages.append(debug_msg)

        if narrative_text and narrative_text.strip():
            txt = narrative_text.strip()
            db.add(
                ChatMessage(
                    session_id=state.session_id,
                    role="system",
                    content=txt,
                )
            )
            messages.append(txt)

        code = str(script_code or "").strip()
        if code:
            context = await cls.build_context(db, state, llm_asker)
            runner = await cls._session_runner(db, state)
            scope = {"tw": context, "game": context}
            runner.execute_code(code, scope, script_id=f"trigger_{trigger_name}_{target_id}")

            for narr_msg in context.changeset.narrative_messages:
                db.add(
                    ChatMessage(
                        session_id=state.session_id,
                        role="assistant",
                        content=narr_msg,
                        is_raw=bool(getattr(narr_msg, "raw", False)),
                    )
                )
                messages.append(narr_msg)

            for sys_msg in context.changeset.system_messages:
                db.add(
                    ChatMessage(
                        session_id=state.session_id,
                        role="system",
                        content=sys_msg,
                    )
                )
                messages.append(sys_msg)

            await insert_cloned_entities(db, state, context.changeset)
            cls._persist_entity_states(state, context.changeset)
            cls._persist_exit_states(state, context.changeset)
            apply_player_inventory(await cls._load_avatar(db, state), context.changeset)
            await cls._sync_npc_personas(db, state, context.changeset)
            await sync_entity_rows(db, state, context.changeset)

        return messages

    @staticmethod
    async def _load_avatar(db: AsyncSession, state: SessionState) -> Optional[Avatar]:
        res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
        return res.scalars().first()

    @staticmethod
    async def _session_runner(db: AsyncSession, state: SessionState) -> ScriptRunner:
        """A runner with the session's init_script and sequence/scene helpers (from its snapshot)."""
        # Imported lazily: the session snapshot lives in the API layer, which imports this module.
        from backend.api.routes.adventures.session_adventure import load_session_adventure

        adventure = await load_session_adventure(db, state)
        manifest = getattr(adventure, "original_manifest", None)
        return runner_for_manifest(
            manifest if isinstance(manifest, dict) else {},
            sequences=getattr(adventure, "sequences", None),
        )

    @staticmethod
    def _persist_entity_states(state: SessionState, changeset: ScriptChangeset) -> None:
        """Writes variable, movement, entity, flag and dialog updates of a trigger script."""
        if changeset.teleport_scene_id:
            state.current_scene_id = changeset.teleport_scene_id
        if not (
            changeset.var_updates
            or changeset.entity_movements
            or changeset.entity_updates
            or changeset.story_flag_updates
            or changeset.exit_updates
            or changeset.pending_dialog
            or changeset.gm_directions
        ):
            return
        cur_states = dict(state.entity_states or {})
        if changeset.var_updates:
            sv = dict(cur_states.get("__script_vars__", {}))
            sv.update(changeset.var_updates)
            cur_states["__script_vars__"] = sv
        if changeset.story_flag_updates:
            flags = dict(cur_states.get("__switch_story_flags__", {}))
            flags.update(changeset.story_flag_updates)
            cur_states["__switch_story_flags__"] = flags
        for move in (m for m in changeset.entity_movements if m.get("entity_id")):
            st = dict(cur_states.get(move["entity_id"], {}))
            st["current_scene_id"] = move["to_scene_id"]
            if move.get("to_spatial_position"):
                st["spatial_position"] = move["to_spatial_position"]
            cur_states[move["entity_id"]] = st
        for upd in (u for u in changeset.entity_updates if u.get("entity_id")):
            st = dict(cur_states.get(upd["entity_id"], {}))
            st.update({k: v for k, v in upd.items() if k != "entity_id"})
            cur_states[upd["entity_id"]] = st
        store_pending_dialog(cur_states, changeset.pending_dialog)
        store_gm_directions(cur_states, changeset.gm_directions)
        state.entity_states = cur_states
        flag_modified(state, "entity_states")

    @staticmethod
    async def _sync_npc_personas(
        db: AsyncSession, state: SessionState, changeset: ScriptChangeset
    ) -> None:
        """The GM prompt reads NPC rows, so script-changed personas are written to them."""
        changed = {
            u["entity_id"]: u
            for u in changeset.entity_updates
            if u.get("entity_id") and any(f in u for f in PERSONA_FIELDS)
        }
        if not changed:
            return
        res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == state.session_id, WorldEntity.id.in_(changed)
            )
        )
        states: dict[str, Any] = dict(state.entity_states or {})
        for ent in res.scalars().all():
            apply_persona(ent, states.get(str(ent.id), {}))

    @staticmethod
    def _persist_exit_states(state: SessionState, changeset: ScriptChangeset) -> None:
        if not changeset.exit_updates:
            return
        exit_states = dict(state.exit_states or {})
        for eu in changeset.exit_updates:
            k = f"{eu['from_scene_id']}:{eu['to_scene_id']}"
            st_item = dict(exit_states.get(k, {}))
            st_item["is_locked"] = eu["is_locked"]
            if "lock_description" in eu:
                st_item["lock_description"] = eu["lock_description"]
            exit_states[k] = st_item
        state.exit_states = exit_states
        flag_modified(state, "exit_states")
