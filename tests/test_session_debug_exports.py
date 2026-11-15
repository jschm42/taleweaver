"""Debug inspector ZIP of every session image (scenes, NPCs, items, protagonist)."""

import io
import os
import zipfile

import pytest
from PIL import Image

from backend.api.routes.adventures.session_debug_exports import ImageRef, build_image_zip
from backend.core.config import settings


def _write_image(relative: str) -> str:
    path = os.path.join(settings.DATA_DIR, *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fmt = "WEBP" if relative.endswith(".webp") else "PNG"
    Image.new("RGB", (4, 4), (200, 30, 30)).save(path, format=fmt)
    return f"/data/{relative}"


def test_zip_packs_local_images_and_lists_the_rest(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    scene_url = _write_image("sessions/s1/scenes/dyn_cave.png")
    npc_url = _write_image("sessions/s1/npcs/wolf.webp")
    refs = [
        ImageRef("scenes", "DYN_CAVE", "Dripping Cave", scene_url + "?v=3"),
        ImageRef("npcs", "DIRE_WOLF", "Fang the Dire Wolf", npc_url),
        ImageRef("items", "BONE", "Bone", "/data/sessions/s1/items/missing.png"),
        ImageRef("items", "REMOTE", "Remote", "https://example.org/x.png"),
        ImageRef("items", "EVIL", "Traversal", "/data/../../etc/passwd"),
    ]

    # Act
    result = build_image_zip(refs)

    # Assert
    names = zipfile.ZipFile(io.BytesIO(result.data)).namelist()
    assert result.packed == 2
    assert "scenes/DYN_CAVE__Dripping_Cave.png" in names
    assert "npcs/DIRE_WOLF__Fang_the_Dire_Wolf.webp" in names
    assert "missing.txt" in names
    assert len(result.missing) == 3


def test_zip_never_packs_non_image_files(tmp_path, monkeypatch):
    # Arrange: an entity whose image_url points at the database (e.g. from a crafted import)
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    (tmp_path / "taleweaver.db").write_bytes(b"SQLite format 3" + bytes(100))
    disguised = tmp_path / "sessions" / "s1" / "fake.png"
    disguised.parent.mkdir(parents=True)
    disguised.write_bytes(b"SQLite format 3" + bytes(100))
    refs = [
        ImageRef("npcs", "THIEF", "Thief", "/data/taleweaver.db"),
        ImageRef("npcs", "THIEF2", "Thief", "/data/sessions/s1/fake.png"),
    ]

    # Act
    result = build_image_zip(refs)

    # Assert
    names = zipfile.ZipFile(io.BytesIO(result.data)).namelist()
    assert result.packed == 0
    assert names == ["missing.txt"]


@pytest.mark.asyncio
async def test_session_npc_exports_as_editor_bundle(client, setup_test_db):
    # Arrange: a debug session with a dynamically spawned NPC
    from sqlalchemy import select

    from backend.engine.adventures.entity_bundle import unpack_entity_bundle
    from backend.models.session_state import SessionState
    from backend.models.world_entity import WorldEntity
    from tests.conftest import TestSessionLocal
    from tests.test_session_ownership import _headers, _setup

    _template_id, game_id = await _setup(client)
    async with TestSessionLocal() as db:
        res_state = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        res_state.scalars().first().is_debug_enabled = True
        db.add(
            WorldEntity(
                id="DYN_CAVE_GOBLIN_1",
                session_id=game_id,
                entity_type="NPC",
                name="Grungle the Goblin",
                description="A sneaky goblin.",
                current_scene_id="HALL",
                hp=12,
                max_hp=12,
            )
        )
        await db.commit()

    # Act
    res = await client.get(
        f"/api/adventures/{game_id}/session-debug/export/DYN_CAVE_GOBLIN_1",
        headers=_headers("player"),
    )
    bad = await client.get(
        f"/api/adventures/{game_id}/session-debug/export/..%2F..%2Fetc", headers=_headers("player")
    )

    # Assert
    assert res.status_code == 200
    assert "npc_Grungle_the_Goblin" in res.headers["content-disposition"]
    bundle = unpack_entity_bundle(res.content)
    assert bundle.kind == "npc"
    assert bundle.entity["name"] == "Grungle the Goblin"
    assert bad.status_code in (400, 404)
