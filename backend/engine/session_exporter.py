import io
import json
import logging
import os
import zipfile
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.world_map import WorldMap

logger = logging.getLogger(__name__)


def _ensure_within_data_dir(path: str) -> str:
    """Validate that a path resolves inside DATA_DIR and return absolute path."""
    data_root = os.path.abspath(settings.DATA_DIR)
    resolved = os.path.abspath(path)
    try:
        if os.path.commonpath([resolved, data_root]) != data_root:
            raise ValueError("Resolved path escapes DATA_DIR.")
    except ValueError as exc:
        raise ValueError("Invalid path: cannot resolve against DATA_DIR.") from exc
    return resolved


def _safe_data_path(*parts: str) -> str:
    """Build a safe path rooted at DATA_DIR."""
    return _ensure_within_data_dir(os.path.join(settings.DATA_DIR, *parts))


def localize_session_paths(data: Any, session_id: str) -> Any:
    """
    Recursively replaces session-specific data paths with relative assets/ paths.
    E.g., /data/adventures/sessions/{session_id}/tts/abc.mp3 -> assets/tts/abc.mp3
    """
    prefix = f"/data/adventures/sessions/{session_id}/"

    if isinstance(data, dict):
        return {k: localize_session_paths(v, session_id) for k, v in data.items()}
    elif isinstance(data, list):
        return [localize_session_paths(item, session_id) for item in data]
    elif isinstance(data, str):
        if data.startswith(prefix):
            return data.replace(prefix, "assets/", 1)
        return data
    return data


class SessionExporter:
    @staticmethod
    async def build_session_manifest(db: AsyncSession, session_id: str) -> dict[str, Any]:
        """
        Gathers all database entities for a game session and builds a single JSON manifest.
        """
        # 1. Fetch core session
        session_res = await db.execute(select(GameSession).where(GameSession.id == session_id))
        game_session = session_res.scalars().first()
        if not game_session:
            raise ValueError(f"GameSession {session_id} not found")

        # 2. Fetch associated state
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == session_id))
        session_state = state_res.scalars().first()

        # 3. Fetch avatar
        avatar = None
        if game_session.avatar_id:
            avatar_res = await db.execute(select(Avatar).where(Avatar.id == game_session.avatar_id))
            avatar = avatar_res.scalars().first()

        # 4. Fetch chat messages
        chat_res = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        chat_messages = chat_res.scalars().all()

        # 5. Fetch world scenes, exits, entities, and map
        scenes_res = await db.execute(select(WorldScene).where(WorldScene.session_id == session_id))
        world_scenes = scenes_res.scalars().all()

        exits_res = await db.execute(select(WorldExit).where(WorldExit.session_id == session_id))
        world_exits = exits_res.scalars().all()

        entities_res = await db.execute(select(WorldEntity).where(WorldEntity.session_id == session_id))
        world_entities = entities_res.scalars().all()

        map_res = await db.execute(select(WorldMap).where(WorldMap.session_id == session_id))
        world_map = map_res.scalars().first()

        # Helper to convert SQL Alchemy model to dictionary
        def to_dict(obj):
            if not obj:
                return None
            return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

        # Build manifest structure
        manifest = {
            "format": "TaleWeaverSession",
            "version": "1.0",
            "original_session_id": session_id,
            "original_avatar_id": game_session.avatar_id,
            "game_session": to_dict(game_session),
            "session_state": to_dict(session_state),
            "avatar": to_dict(avatar),
            "chat_messages": [to_dict(msg) for msg in chat_messages],
            "world_scenes": [to_dict(sc) for sc in world_scenes],
            "world_exits": [to_dict(ex) for ex in world_exits],
            "world_entities": [to_dict(ent) for ent in world_entities],
            "world_map": to_dict(world_map),
        }

        # Localize any session URL paths inside the database JSON
        manifest = localize_session_paths(manifest, session_id)

        return manifest

    @staticmethod
    async def export_ads(db: AsyncSession, session_id: str) -> bytes:
        """
        Creates an ADS (Adventure Session Zip) bundle containing the manifest and all local session assets.
        """
        manifest = await SessionExporter.build_session_manifest(db, session_id)

        # Create the ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Add Manifest
            encoded_manifest = jsonable_encoder(manifest)
            zip_file.writestr("session.json", json.dumps(encoded_manifest, indent=2))

            # 2. Add local assets directory
            session_dir = _safe_data_path("adventures", "sessions", session_id)
            if os.path.exists(session_dir):
                for root, _, files in os.walk(session_dir):
                    for file in files:
                        local_full = os.path.join(root, file)
                        safe_local_full = _ensure_within_data_dir(local_full)
                        # Compute relative path within zip
                        rel_path = os.path.relpath(safe_local_full, session_dir)
                        zip_rel = f"assets/{rel_path.replace(os.sep, '/')}"
                        zip_file.write(safe_local_full, zip_rel)

        return zip_buffer.getvalue()
