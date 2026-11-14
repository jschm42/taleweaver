from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.core.config import settings
from backend.engine.audio.audio_state import apply_audio_ops, read_audio_state
from backend.engine.interaction.script_item_apply import (
    apply_player_inventory,
    insert_cloned_entities,
    sync_entity_rows,
    sync_exit_rows,
)
from backend.engine.interaction.switch_service import SwitchService
from backend.engine.party.follow import bring_companion_along
from backend.engine.party.party_ops import apply_party_ops
from backend.engine.party.party_state import PARTY_KEY
from backend.engine.rules.game_clock import apply_changeset_clock, clock_view
from backend.engine.scripting.context import GameContext, ScriptChangeset
from backend.engine.scripting.dialog import store_pending_dialog
from backend.engine.scripting.gm_directions import store_gm_directions
from backend.engine.scripting.llm_proxy import LlmAsker
from backend.engine.scripting.narration_skip import store_skip_narration
from backend.engine.scripting.npc_persona import PERSONA_FIELDS, apply_persona
from backend.engine.scripting.runner import ScriptRunner
from backend.engine.scripting.scene_helpers import runner_for_manifest
from backend.engine.sessions.session_checkpoint_service import SessionCheckpointService
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

        from backend.api.routes.adventures.session_adventure import load_session_adventure

        adventure = await load_session_adventure(db, state)
        sequences = getattr(adventure, "sequences", None) if adventure else None

        return GameContext(
            avatar_data=avatar_dict,
            current_scene_id=state.current_scene_id,
            entities=entities_map,
            exit_states=state.exit_states or {},
            quests=state.quests or [],
            script_vars=script_vars,
            in_game_time=state.in_game_time,
            clock=clock_view(state),
            audio=read_audio_state(state.entity_states),
            audio_library=getattr(adventure, "audio_tracks", None) if adventure else None,
            party=session_overrides.get(PARTY_KEY),
            story_flags=story_flags,
            is_debug_enabled=cls.is_debug_mode(state),
            llm_asker=llm_asker,
            active_sequence_id=state.active_sequence_id,
            sequences=sequences,
            sequence_progression_mode=getattr(adventure, "sequence_progression_mode", "linear")
            if adventure
            else "linear",
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
        extra_scope: Optional[dict[str, Any]] = None,
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
            if extra_scope and "generated_scene" in extra_scope:
                context.generated_scene = extra_scope["generated_scene"]
            runner = await cls._session_runner(db, state)
            scope: dict[str, Any] = {"tw": context, "game": context}
            if extra_scope:
                scope.update(extra_scope)
            runner.execute_code(code, scope, script_id=f"trigger_{trigger_name}_{target_id}")

            if getattr(context.changeset, "ordered_messages", None):
                for msg in context.changeset.ordered_messages:
                    role = str(getattr(msg, "role", "system"))
                    raw = bool(getattr(msg, "raw", False))
                    db.add(
                        ChatMessage(
                            session_id=state.session_id,
                            role=role,
                            content=msg,
                            is_raw=raw,
                        )
                    )
                    messages.append(msg)
            else:
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

            from backend.api.routes.adventures.sequence_progress import apply_sequence_changeset
            from backend.api.routes.adventures.session_adventure import load_session_adventure

            adventure = await load_session_adventure(db, state)
            await cls._apply_trigger_teleport_and_entities(
                db, state, context.changeset, adventure, messages
            )
            cls._persist_exit_states(state, context.changeset)
            apply_player_inventory(await cls._load_avatar(db, state), context.changeset)
            await cls._sync_npc_personas(db, state, context.changeset)
            await sync_entity_rows(db, state, context.changeset)
            await sync_exit_rows(db, state, context.changeset)

            avatar = await cls._load_avatar(db, state)
            seq_msgs = await apply_sequence_changeset(adventure, state, avatar, context.changeset)
            messages.extend(seq_msgs)
            messages.extend(
                await SessionCheckpointService.save_from_script(
                    db, state.session_id, context.changeset.save_requests
                )
            )

        return messages

    @classmethod
    async def _apply_trigger_teleport_and_entities(
        cls,
        db: AsyncSession,
        state: SessionState,
        changeset: Any,
        adventure: Any,
        messages: list[str],
    ) -> None:
        """Apply script teleport, cloned/updated entities, and companion follow-along."""
        from backend.api.routes.adventures.dynamic_teleport import apply_script_teleport

        left_scene_id = state.current_scene_id
        await apply_script_teleport(db, state, changeset, adventure=adventure)
        await insert_cloned_entities(db, state, changeset)
        cls._persist_entity_states(state, changeset)
        if state.current_scene_id != left_scene_id:
            for msg in await bring_companion_along(db, state, left_scene_id, adventure=adventure):
                db.add(ChatMessage(session_id=state.session_id, role="system", content=msg))
                messages.append(msg)

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
        if not (
            changeset.var_updates
            or changeset.entity_movements
            or changeset.entity_updates
            or changeset.story_flag_updates
            or changeset.exit_updates
            or changeset.pending_dialog
            or changeset.gm_directions
            or changeset.after_narration
            or changeset.clock_ops
            or changeset.audio_ops
            or changeset.party_ops
            or changeset.skip_narration
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
        store_gm_directions(cur_states, changeset.gm_directions, changeset.after_narration)
        apply_changeset_clock(state, cur_states, changeset.clock_ops)
        apply_audio_ops(cur_states, changeset.audio_ops)
        apply_party_ops(cur_states, changeset.party_ops)
        store_skip_narration(cur_states, changeset.skip_narration)
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
