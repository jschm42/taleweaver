import logging
from copy import deepcopy
from typing import Any, Optional

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.routes.adventures.asset_url_healing import (
    heal_template_avatar_profile_image,
    resolve_existing_data_asset_url,
)
from backend.api.routes.adventures.sequence_progress import evaluate_sequence_progress
from backend.api.routes.adventures.session_start_settings import (
    resolve_initial_scene_id,
    resolve_start_datetime,
)
from backend.api.routes.adventures.sheet_snapshot import build_sheet_snapshot
from backend.engine.map_engine import MapEngine
from backend.engine.voice_casting import CastingCandidate, cast_voices, resolve_narrator_voice
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.world_map import WorldMap

logger = logging.getLogger(__name__)
SESSION_MANIFEST_SNAPSHOT_KEY = "__manifest_snapshot__"


def _entity_override(overrides: dict[str, Any], normalized: dict[str, Any], eid: Any) -> dict:
    """Session override for an entity id (exact match first, then case-insensitive)."""
    if eid in overrides:
        return overrides[eid]
    return normalized.get(str(eid or "").strip().upper()) or {}


def _listed_in_discoveries(ent: dict[str, Any]) -> bool:
    metadata = ent.get("metadata_json") if isinstance(ent.get("metadata_json"), dict) else {}
    visibility = metadata.get("discovery_visibility")
    listed = visibility.get("listed_in_discoveries") if isinstance(visibility, dict) else None
    if isinstance(listed, bool):
        return listed
    return str(ent.get("item_type") or "").upper() != "SWITCH"


def _merge_session_entity(
    ent: dict[str, Any], overrides: dict[str, Any], normalized: dict[str, Any]
) -> dict[str, Any]:
    override = _entity_override(overrides, normalized, ent.get("id"))
    ent.update(override)
    # Constructables stay hidden until a session override reveals them.
    if str(ent.get("item_type") or "").upper() == "CONSTRUCTABLE" and "is_hidden" not in override:
        ent["is_hidden"] = True
    ent["listed_in_discoveries"] = _listed_in_discoveries(ent)
    ent["image_url"] = resolve_existing_data_asset_url(ent.get("image_url"))
    return ent


def _normalized_scene_id(scene_id: Any) -> str:
    return str(scene_id or "").strip().lower().replace("-", "_").replace(" ", "_")


def _visible_in_scene(ent: dict[str, Any], scene_key: str, contained_ids: set[str]) -> bool:
    return (
        _normalized_scene_id(ent.get("current_scene_id")) == scene_key
        and not ent.get("is_hidden")
        and not ent.get("is_in_inventory")
        and str(ent.get("id") or "") not in contained_ids
    )


class AdventureLogic:
    """Class grouping core business logic and helper functions for Adventure management."""

    SESSION_MANIFEST_SNAPSHOT_KEY = SESSION_MANIFEST_SNAPSHOT_KEY

    @staticmethod
    async def get_or_create_map(
        db: AsyncSession, template_id: Optional[str], session_id: Optional[str] = None
    ) -> WorldMap:
        """Fetch or lazily create a WorldMap row for the given adventure session."""
        if session_id:
            query = select(WorldMap).where(WorldMap.session_id == session_id)
        else:
            query = select(WorldMap).where(
                WorldMap.template_id == template_id, WorldMap.session_id.is_(None)
            )

        result = await db.execute(query)
        world_map = result.scalars().first()

        if not world_map:
            world_map = WorldMap(template_id=template_id, session_id=session_id)
            db.add(world_map)
            await db.flush()
        return world_map

    @staticmethod
    def build_session_manifest_snapshot(adventure: Optional[AdventureTemplate]) -> dict[str, Any]:
        """Capture adventure metadata required to keep sessions playable after template deletion."""
        if not adventure:
            return {}
        adventure_payload = {
            "id": adventure.id,
            "title": adventure.title,
            "teaser": adventure.teaser,
            "version": adventure.version,
            "language": adventure.language,
            "cover_source_adventure_id": adventure.cover_source_adventure_id,
            "cover_source_adventure_name": adventure.cover_source_adventure_name,
            "cover_similarity_percent": adventure.cover_similarity_percent,
            "allow_reuse_source_assets": adventure.allow_reuse_source_assets,
            "image_url": adventure.image_url,
            "strict_rules": adventure.strict_rules,
            "rule_enforcement_mode": adventure.rule_enforcement_mode,
            "time_per_turn": adventure.time_per_turn,
            "pacing_minutes": adventure.pacing_minutes,
            "clock_enabled": adventure.clock_enabled,
            "time_system": adventure.time_system,
            "time_config": deepcopy(adventure.time_config or {}),
            "selected_image_styles": deepcopy(adventure.selected_image_styles or []),
            "selected_tone": deepcopy(adventure.selected_tone or {}),
            "ui_theme": deepcopy(adventure.ui_theme),
            "quests": deepcopy(adventure.quests or []),
            "awards": deepcopy(adventure.awards or []),
            "plot": adventure.plot,
            "rules": adventure.rules,
            "intro_text": adventure.intro_text,
            "completed_condition": adventure.completed_condition,
            "gameover_condition": adventure.gameover_condition,
            "tts_director_notes": adventure.tts_director_notes,
            "original_prompt": adventure.original_prompt,
            "allow_dynamic_items": adventure.allow_dynamic_items,
            "can_damage_npcs": adventure.can_damage_npcs,
            "npcs_can_damage_protagonist": adventure.npcs_can_damage_protagonist,
            "is_adventure_generator": adventure.is_adventure_generator,
            "is_ready": True,
            "creation_status": "Ready",
        }
        return {
            "adventure": adventure_payload,
            "original_manifest": deepcopy(adventure.original_manifest or {}),
        }

    @staticmethod
    def extract_manifest_snapshot(state: Optional[SessionState]) -> dict[str, Any]:
        if not state:
            return {}
        raw = state.entity_states or {}
        if not isinstance(raw, dict):
            return {}
        snapshot = raw.get(SESSION_MANIFEST_SNAPSHOT_KEY)
        return snapshot if isinstance(snapshot, dict) else {}

    @staticmethod
    def resolve_manifest_for_state(state: SessionState) -> dict[str, Any]:
        snapshot = AdventureLogic.extract_manifest_snapshot(state)
        manifest = snapshot.get("original_manifest")
        if isinstance(manifest, dict) and manifest:
            return manifest
        adventure_meta = snapshot.get("adventure")
        if isinstance(adventure_meta, dict):
            return adventure_meta
        return {}

    @staticmethod
    def calculate_quest_progress(quests: list[dict[str, Optional[Any]]]) -> int:
        if not quests:
            return 0
        total = len(quests)
        if total == 0:
            return 0
        completed = len([q for q in quests if q.get("status") == "completed"])
        return int((completed / total) * 100)

    @staticmethod
    def extract_asset_snapshot(state: Optional[SessionState]) -> dict[str, Any]:
        if not state:
            return {}
        raw = state.entity_states or {}
        if not isinstance(raw, dict):
            return {}
        snap = raw.get("__asset_snapshot__")
        return snap if isinstance(snap, dict) else {}

    @staticmethod
    def get_combat_snapshot(state: Optional[SessionState]) -> dict[str, Optional[Any]]:
        if not state:
            return None
        raw = state.entity_states or {}
        if not isinstance(raw, dict):
            return None
        combat = raw.get("__combat__")
        if not isinstance(combat, dict):
            return None
        return combat

    @staticmethod
    def resolve_session_asset(
        state: Optional[SessionState], key: str, fallback: Optional[str] = None
    ) -> Optional[str]:
        if not state:
            return AdventureLogic.resolve_existing_data_asset_url(fallback)
        snapshot = AdventureLogic.extract_asset_snapshot(state)
        value = snapshot.get(key)
        candidate = value if isinstance(value, str) and value else fallback
        return AdventureLogic.resolve_existing_data_asset_url(candidate)

    @staticmethod
    def resolve_existing_data_asset_url(url: Optional[str]) -> Optional[str]:
        """Best-effort repair for stale /data URLs that no longer match current folders."""
        return resolve_existing_data_asset_url(url)

    @staticmethod
    def heal_template_avatar_profile_image(
        template_id: Optional[str], profile_image: Optional[str]
    ) -> Optional[str]:
        """Heals template avatar profile image if it points to a deleted session path."""
        return heal_template_avatar_profile_image(template_id, profile_image)

    @staticmethod
    async def resolve_scene_image(
        db: AsyncSession, state: SessionState, scene_id: str
    ) -> Optional[str]:
        """Resolves the image for a scene, prioritizing session overrides then template defaults."""
        # 1. Try session override (e.g. generated image)
        img = AdventureLogic.resolve_existing_data_asset_url(
            AdventureLogic.resolve_session_asset(state, scene_id)
        )
        if img:
            return img

        # 2. Try WorldScene table (template default)
        res = await db.execute(
            select(WorldScene.image_url).where(
                WorldScene.id == scene_id,
                or_(
                    WorldScene.session_id == state.session_id,
                    WorldScene.template_id == state.template_id,
                ),
            )
        )
        return AdventureLogic.resolve_existing_data_asset_url(res.scalars().first())

    @staticmethod
    def resolve_start_datetime(
        manifest: dict[str, Optional[Any]],
        state: Optional[SessionState] = None,
        time_config: Optional[dict] = None,
    ) -> Optional[str]:
        """Returns a usable ISO datetime string. Prioritizes session-specific state over manifest."""
        return resolve_start_datetime(manifest, state=state, time_config=time_config)

    @staticmethod
    async def resolve_initial_scene_id(db: AsyncSession, template_id: Optional[str]) -> str:
        """Resolve a stable initial scene for a fresh session (see session_start_settings)."""
        return await resolve_initial_scene_id(db, template_id)

    @staticmethod
    async def resolve_session_state(
        db: AsyncSession, session_or_template_id: str, user_id: Optional[str] = None
    ) -> Optional[SessionState]:
        """Resolve a session state by session id first, then by template/adventure id."""
        direct_res = await db.execute(
            select(SessionState)
            .options(selectinload(SessionState.session))
            .where(SessionState.session_id == session_or_template_id)
        )
        direct_state = direct_res.scalars().first()
        if direct_state:
            return direct_state

        session_candidate = None
        session_by_id_res = await db.execute(
            select(GameSession).where(GameSession.id == session_or_template_id)
        )
        session_candidate = session_by_id_res.scalars().first()

        if not session_candidate:
            template_session_res = await db.execute(
                select(GameSession)
                .where(GameSession.template_id == session_or_template_id)
                .order_by(GameSession.updated_at.desc())
            )
            template_sessions = template_session_res.scalars().all()
            if user_id:
                session_candidate = next(
                    (s for s in template_sessions if s.user_id == user_id), None
                )
            else:
                session_candidate = template_sessions[0] if template_sessions else None

        if session_candidate:
            if user_id and session_candidate.user_id != user_id:
                return None
            existing_for_candidate_res = await db.execute(
                select(SessionState)
                .options(selectinload(SessionState.session))
                .where(SessionState.session_id == session_candidate.id)
            )
            existing_for_candidate = existing_for_candidate_res.scalars().first()
            if existing_for_candidate:
                return existing_for_candidate

            # Auto-healing logic
            first_scene_id = await AdventureLogic.resolve_initial_scene_id(
                db, session_candidate.template_id
            )

            adv_res = await db.execute(
                select(AdventureTemplate).where(
                    AdventureTemplate.id == session_candidate.template_id
                )
            )
            adventure = adv_res.scalars().first()

            healed_state = SessionState(
                session=session_candidate,
                user_id=session_candidate.user_id,
                template_id=session_candidate.template_id,
                avatar_id=session_candidate.avatar_id,
                current_scene_id=first_scene_id,
                in_game_time=0,
                entity_states={
                    AdventureLogic.SESSION_MANIFEST_SNAPSHOT_KEY: AdventureLogic.build_session_manifest_snapshot(
                        adventure
                    )
                }
                if adventure
                else {},
                quests=adventure.quests if adventure else [],
                plot=adventure.plot if adventure else None,
                rules=adventure.rules if adventure else None,
                completed_condition=adventure.completed_condition if adventure else None,
                gameover_condition=adventure.gameover_condition if adventure else None,
                tts_director_notes=adventure.tts_director_notes if adventure else None,
            )
            db.add(healed_state)
            await db.commit()
            await db.refresh(healed_state, ["session"])
            return healed_state
        return None

    @staticmethod
    async def build_session_entities(db: AsyncSession, state: SessionState) -> list[dict[str, Any]]:
        """Fetches and processes entities for the current session, filtering for the current scene."""
        ent_res = await db.execute(
            select(WorldEntity).where(WorldEntity.session_id == state.session_id)
        )
        overrides = state.entity_states or {}
        normalized = {
            str(k).strip().upper(): v for k, v in overrides.items() if isinstance(v, dict)
        }
        merged_entities = [
            _merge_session_entity(
                {c.name: getattr(e, c.name) for c in e.__table__.columns}, overrides, normalized
            )
            for e in ent_res.scalars().all()
        ]

        entity_lookup = {str(ent.get("id")): ent for ent in merged_entities if ent.get("id")}
        contained_ids = AdventureLogic.collect_container_item_ids(merged_entities)
        scene_key = _normalized_scene_id(state.current_scene_id)
        entities: list[dict[str, Any]] = []
        for ent in merged_entities:
            if not _visible_in_scene(ent, scene_key, contained_ids):
                continue
            if str(ent.get("item_type") or "").upper() != "CONTAINER":
                entities.append(ent)
                continue
            inventory = AdventureLogic.hydrate_container_inventory(
                ent.get("inventory"), entity_lookup
            )
            entities.append({**ent, "inventory": inventory})
        return entities

    @staticmethod
    def resolve_active_sequence(adventure: Any, state: SessionState) -> dict[str, Any] | None:
        """Resolves the current active sequence dictionary from an adventure template and session state."""
        if not adventure or not getattr(adventure, "sequences", None):
            return None
        sequences = adventure.sequences
        if not isinstance(sequences, list) or len(sequences) == 0:
            return None
        active_seq_id = getattr(state, "active_sequence_id", None)
        if active_seq_id:
            for s in sequences:
                if isinstance(s, dict) and s.get("id") == active_seq_id:
                    return s
        if isinstance(sequences[0], dict):
            return sequences[0]
        return None

    @staticmethod
    def evaluate_sequence_progress(
        adventure: Any,
        state: SessionState,
        avatar: Avatar,
        new_inventory_items: Optional[list[Any]] = None,
        new_scene_id: Optional[str] = None,
        updated_entities: Optional[list[Any]] = None,
        force_complete: bool = False,
        script_context: Optional[Any] = None,
    ) -> list[str]:
        """Completes the active sequence when its hard rules (or force_complete) are met."""
        return evaluate_sequence_progress(
            adventure,
            state,
            avatar,
            new_inventory_items=new_inventory_items,
            new_scene_id=new_scene_id,
            updated_entities=updated_entities,
            force_complete=force_complete,
            script_context=script_context,
        )

    @staticmethod
    def extract_inventory_entity_ids(inventory: Any) -> set[str]:
        """Extracts entity IDs from mixed inventory payloads (string IDs or dict items)."""
        if not isinstance(inventory, list):
            return set()

        item_ids: set[str] = set()
        for entry in inventory:
            item_id = ""
            if isinstance(entry, str):
                item_id = entry.strip()
            elif isinstance(entry, dict):
                raw_id = entry.get("id")
                if isinstance(raw_id, str):
                    item_id = raw_id.strip()

            if item_id:
                item_ids.add(item_id)

        return item_ids

    @staticmethod
    def collect_container_item_ids(entities: list[dict[str, Any]]) -> set[str]:
        """Returns IDs of entities stored inside container objects."""
        contained_ids: set[str] = set()
        for entity in entities:
            if str(entity.get("item_type") or "").upper() != "CONTAINER":
                continue
            contained_ids.update(
                AdventureLogic.extract_inventory_entity_ids(entity.get("inventory"))
            )
        return contained_ids

    @staticmethod
    def hydrate_container_inventory(
        inventory: Any, entity_lookup: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Expands container inventory refs into item payloads used by the UI modal."""
        if not isinstance(inventory, list):
            return []

        hydrated: list[dict[str, Any]] = []
        for entry in inventory:
            if isinstance(entry, dict):
                item = dict(entry)
                item["image_url"] = AdventureLogic.resolve_existing_data_asset_url(
                    item.get("image_url")
                )
                hydrated.append(item)
                continue

            if isinstance(entry, str):
                item_id = entry.strip()
                if not item_id:
                    continue
                resolved = entity_lookup.get(item_id)
                if resolved:
                    hydrated.append(dict(resolved))
                else:
                    hydrated.append({"id": item_id, "name": item_id})

        return hydrated

    @staticmethod
    async def build_sheet_snapshot(avatar: Avatar, state: SessionState, db: AsyncSession) -> dict:
        """Builds a serialisable character-sheet snapshot."""
        return await build_sheet_snapshot(
            avatar,
            state,
            db,
            manifest_snapshot=AdventureLogic.extract_manifest_snapshot(state),
            session_manifest=AdventureLogic.resolve_manifest_for_state(state),
            asset_snapshot=AdventureLogic.extract_asset_snapshot(state),
            session_profile_image=AdventureLogic.resolve_session_asset(
                state, "protagonist", avatar.profile_image
            ),
        )

    @staticmethod
    async def get_all_scene_metadata(
        db: AsyncSession, template_id: Optional[str], session_id: Optional[str] = None
    ) -> dict:
        if session_id:
            scene_res = await db.execute(
                select(WorldScene).where(WorldScene.session_id == session_id)
            )
        elif template_id:
            scene_res = await db.execute(
                select(WorldScene).where(WorldScene.template_id == template_id)
            )
        else:
            return {}
        metadata = {}
        for s in scene_res.scalars().all():
            metadata[MapEngine._safe_id(s.id)] = {
                "id": s.id,
                "label": s.label,
                "description": s.description or "",
                "image_url": AdventureLogic.resolve_existing_data_asset_url(s.image_url),
                "decorative_objects": [
                    str(d) for d in (s.decorative_objects or []) if isinstance(d, (str, int, float))
                ],
            }
        return metadata

    @staticmethod
    async def get_npc_metadata(
        db: AsyncSession, template_id: Optional[str], session_id: Optional[str] = None
    ) -> dict:
        if session_id:
            npc_query = select(WorldEntity).where(
                WorldEntity.session_id == session_id, WorldEntity.entity_type.in_(["NPC", "npc"])
            )
        elif template_id:
            npc_query = select(WorldEntity).where(
                WorldEntity.template_id == template_id, WorldEntity.entity_type.in_(["NPC", "npc"])
            )
        else:
            return {}
        npcs = (await db.execute(npc_query)).scalars().all()
        # NPCs without a stored voice get a deterministic, distinct one (older adventures).
        voices = cast_voices(
            [
                CastingCandidate(
                    npc.id, f"{npc.name} {npc.description} {npc.character or ''}", npc.voice
                )
                for npc in npcs
            ],
            reserved=[await resolve_narrator_voice(db)],
        )
        return {
            npc.id: {
                "name": npc.name,
                "description": npc.description,
                "image_url": npc.image_url,
                "voice": voices.get(npc.id),
                "entity_type": "NPC",
            }
            for npc in npcs
        }

    @staticmethod
    async def delete_adventure(db: AsyncSession, template_id: str):
        """
        Deletes an adventure template and all associated content.
        Decouples game sessions so they remain playable.
        """
        from backend.engine.media_engine import MediaEngine

        # 1. Preserve session playability by detaching session-owned rows from template refs.
        session_avatar_query = select(GameSession.avatar_id).where(
            GameSession.template_id == template_id
        )
        session_avatar_ids = (await db.execute(session_avatar_query)).scalars().all()
        if session_avatar_ids:
            await db.execute(
                update(Avatar).where(Avatar.id.in_(session_avatar_ids)).values(template_id=None)
            )

        # Detach sessions and session states
        await db.execute(
            update(GameSession)
            .where(GameSession.template_id == template_id)
            .values(template_id=None)
        )
        await db.execute(
            update(SessionState)
            .where(SessionState.template_id == template_id)
            .values(template_id=None)
        )

        # Detach session maps
        await db.execute(
            update(WorldMap)
            .where(WorldMap.template_id == template_id, WorldMap.session_id.is_not(None))
            .values(template_id=None)
        )

        # 2. Delete only template-owned avatars that are not used by any session.
        await db.execute(
            delete(Avatar).where(
                Avatar.template_id == template_id,
                ~Avatar.id.in_(select(GameSession.avatar_id)),
            )
        )

        # 3. Delete World Content
        await db.execute(delete(WorldExit).where(WorldExit.template_id == template_id))
        await db.execute(delete(WorldEntity).where(WorldEntity.template_id == template_id))
        await db.execute(delete(WorldScene).where(WorldScene.template_id == template_id))
        await db.execute(
            delete(WorldMap).where(
                WorldMap.template_id == template_id, WorldMap.session_id.is_(None)
            )
        )

        # 4. Finally delete the template itself
        await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == template_id))

        await db.commit()

        # 5. Always clean up template-owned library assets.
        # Session visuals are now copied into session folders when sessions are created.
        await MediaEngine.cleanup_adventure_assets(template_id)

    @staticmethod
    def build_awards_payload(
        user_earned_awards: list[dict] | None,
        adventure_awards: list[dict] | None,
        adventure_id: str | None = None,
        session_id: str | None = None,
    ) -> list[dict]:
        """Builds an adventure's awards list including universal global awards and earned status."""
        from backend.core.awards import GLOBAL_AWARDS

        earned = user_earned_awards or []
        adv_awards = [dict(aw) for aw in (adventure_awards or [])]
        known_keys = {aw.get("key") for aw in adv_awards if aw.get("key")}

        # Include universal global awards applicable to all adventures
        for global_award in GLOBAL_AWARDS:
            g_key = global_award.get("key")
            if g_key and g_key not in known_keys:
                adv_awards.append(dict(global_award))
                known_keys.add(g_key)

        result: list[dict] = []
        for aw in adv_awards:
            k = aw.get("key")
            is_earned = any(
                ea.get("key") == k
                and (
                    ea.get("template_id") == adventure_id
                    or ea.get("adventure_id") == adventure_id
                    or (session_id and ea.get("session_id") == session_id)
                )
                for ea in earned
            )
            result.append(
                {
                    **aw,
                    "is_earned": is_earned,
                }
            )

        # Include custom or unregistered earned awards for this adventure/session
        for ea in earned:
            k = ea.get("key")
            if not k or k in known_keys:
                continue
            if (
                ea.get("template_id") == adventure_id
                or ea.get("adventure_id") == adventure_id
                or (session_id and ea.get("session_id") == session_id)
            ):
                known_keys.add(k)
                result.append(
                    {
                        **ea,
                        "is_earned": True,
                    }
                )

        return result
