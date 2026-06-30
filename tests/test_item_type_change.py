"""Tests for changing an item's type via PATCH /editor/entity.

Mirrors the frontend's "Change Type…" flow inside ItemsTab.vue's context menu:
the backend must (a) persist the new item_type, (b) recompute the cascade
flags (is_readable_object etc.) against the NEW value, and (c) clean up
metadata that no longer applies to the new type.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import create_access_token
from backend.main import app
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal


def _auth_headers(username: str) -> dict:
    token = create_access_token(data={"sub": username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


async def _seed_template_with_item(item_kwargs: dict) -> tuple[str, str, str, int]:
    """Insert user + template + scene + OBJECT item.

    Returns (user_id, tpl_id, item_id_string, item_pk) — the integer pk is the
    World's primary key (autoincrement). Tests must use it with `db.get(WorldEntity, pk)`.
    """
    user = User(username="type_change_user", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        user_id = user.id
        tpl_id = "tpl-type-change"
        tpl = AdventureTemplate(
            id=tpl_id,
            owner_id=user_id,
            title="Type Change Test",
            version="1.0",
            rule_enforcement_mode="rpg",
            is_ready=True,
            creation_status="Ready",
            generate_scene_images=False,
            generate_npc_images=False,
            generate_item_images=False,
            teaser="t",
            rules="r",
            plot="p",
            intro_text="i",
            walkthrough="w",
            completed_condition="done",
            gameover_condition="lost",
            tts_director_notes="notes",
            quests=[],
        )
        db.add(tpl)
        scene = WorldScene(id="SCENE_X", template_id=tpl_id, label="X", description="X")
        db.add(scene)
        item_id = "OBJ_TEST"
        item = WorldEntity(
            id=item_id,
            template_id=tpl_id,
            entity_type="OBJECT",
            name="Test Object",
            description="Test desc",
            current_scene_id="SCENE_X",
            **item_kwargs,
        )
        db.add(item)
        await db.commit()
        item_pk = item.pk
    return user_id, tpl_id, item_id, item_pk


async def test_change_item_type_preserves_pickable_to_readable_metadata(client, setup_test_db):
    """PICKABLE (DEFAULT) -> READABLE: text_log_content added, no other cleanup needed."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({
        "item_type": "DEFAULT",
        "metadata_json": {"is_portable_extra": "keep_me"},
    })
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "item_type": "READABLE",
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert str(item.item_type or "").upper() == "READABLE"
        assert item.metadata_json.get("is_portable_extra") == "keep_me"


async def test_change_item_type_container_to_default_strips_lock(client, setup_test_db):
    """CONTAINER -> DEFAULT: lock fields and unlock_rule must be cleared."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({
        "item_type": "CONTAINER",
        "metadata_json": {
            "code_to_unlock": "1337",
            "item_to_unlock": "",
            "rule_to_unlock": "",
            "locked": True,
        },
    })
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "item_type": "DEFAULT",
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert str(item.item_type or "").upper() == "DEFAULT"
        for stripped_key in ("code_to_unlock", "item_to_unlock", "rule_to_unlock", "locked"):
            assert stripped_key not in (item.metadata_json or {}), (
                f"lock key {stripped_key!r} should be cleared on CONTAINER -> DEFAULT"
            )


async def test_change_item_type_readable_to_switch_strips_text_log(client, setup_test_db):
    """READABLE -> SWITCH: text_log_content + text_log_format must be cleared."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({
        "item_type": "READABLE",
        "metadata_json": {"text_log_content": "ancient runes", "text_log_format": "SCROLL"},
    })
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "item_type": "SWITCH",
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert str(item.item_type or "").upper() == "SWITCH"
        for stripped_key in ("text_log_content", "text_log_format"):
            assert stripped_key not in (item.metadata_json or {}), (
                f"readable key {stripped_key!r} should be cleared on READABLE -> SWITCH"
            )


async def test_change_item_type_consumable_to_default_strips_effects(client, setup_test_db):
    """CONSUMABLE -> DEFAULT: effects metadata must be cleared."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({
        "item_type": "CONSUMABLE",
        "metadata_json": {"effects": {"heal": 50}},
    })
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "item_type": "DEFAULT",
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert str(item.item_type or "").upper() == "DEFAULT"
        assert "effects" not in (item.metadata_json or {})


async def test_change_item_type_rejects_unknown_type(client, setup_test_db):
    """Belt-and-suspenders: PATCH must reject invalid item_type values."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({"item_type": "DEFAULT"})
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "item_type": "BANANA",
        },
    )
    assert res.status_code == 400, res.text
    assert "item_type must be one of" in res.text


async def test_change_item_type_same_value_is_noop(client, setup_test_db):
    """Setting item_type to the same value must be a clean no-op (no extra writes)."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({
        "item_type": "DEFAULT",
        "metadata_json": {"keep": True},
    })
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "item_type": "DEFAULT",
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert str(item.item_type or "").upper() == "DEFAULT"
        assert item.metadata_json.get("keep") is True


async def test_move_item_to_new_scene(client, setup_test_db):
    """PATCH current_scene_id must move the item to a valid existing scene."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({"item_type": "DEFAULT"})
    headers = _auth_headers("type_change_user")
    async with TestSessionLocal() as db:
        db.add(WorldScene(id="SCENE_Y", template_id=tpl_id, label="Y", description="Y"))
        await db.commit()

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "current_scene_id": "SCENE_Y",
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert item.current_scene_id == "SCENE_Y"


async def test_move_item_to_invalid_scene_rejected(client, setup_test_db):
    """Backend must 400 if the destination scene does not exist."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({"item_type": "DEFAULT"})
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "current_scene_id": "DOES_NOT_EXIST",
        },
    )
    assert res.status_code == 400, res.text


async def test_text_log_content_allows_up_to_1000_characters(client, setup_test_db):
    """Storage limit for READABLE.text_log_content must be 1000 (was 500)."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({"item_type": "READABLE"})
    headers = _auth_headers("type_change_user")
    body = "Z" * 1000

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "text_log_content": body,
            "text_log_format": "SCROLL",
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert item.metadata_json.get("text_log_content") == body


async def test_text_log_content_rejects_over_1000_characters(client, setup_test_db):
    """Hard limit guard at the PATCH endpoint — 1001 chars must be rejected."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({"item_type": "READABLE"})
    headers = _auth_headers("type_change_user")
    body = "Z" * 1001

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "text_log_content": body,
        },
    )
    assert res.status_code == 400, res.text
    assert "1000" in res.text


async def test_combinable_supports_single_ingredient(client, setup_test_db):
    """Combinable items must accept any non-negative number of ingredients (min = 1)."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({"item_type": "COMBINABLE"})
    headers = _auth_headers("type_change_user")

    res_single = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "combination_ingredients": ["SINGLE_INGREDIENT"],
        },
    )
    assert res_single.status_code == 200, res_single.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert item.combination_ingredients == ["SINGLE_INGREDIENT"]


async def test_combinable_supports_empty_ingredient_list(client, setup_test_db):
    """Wiping ingredients must succeed — the field is fully optional."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({
        "item_type": "COMBINABLE",
        "combination_ingredients": ["WILL_BE_WIPED"],
    })
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "combination_ingredients": [],
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert item.combination_ingredients == []


async def test_persist_combinable_metadata_fields(client, setup_test_db):
    """reveal_rule, is_hidden, spatial_position, reveals_item_id all round-trip cleanly."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({"item_type": "COMBINABLE"})
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "combination_ingredients": ["a", "b"],
            "reveal_rule": "If the prot searches under the table",
            "is_hidden": True,
            "spatial_position": "behind the vault",
            "reveals_item_id": "ancient_key",
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert item.reveal_rule == "If the prot searches under the table"
        assert item.is_hidden is True
        assert item.spatial_position == "behind the vault"
        # Backend normalizes to upper-case to match entity-id convention.
        assert item.reveals_item_id == "ANCIENT_KEY"


async def test_combinable_metadata_fields_can_be_cleared(client, setup_test_db):
    """Setting each field to its zero-value (empty string / False) must persist cleanly."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({
        "item_type": "COMBINABLE",
        "reveal_rule": "old",
        "is_hidden": True,
        "spatial_position": "old place",
        "reveals_item_id": "OLD_KEY",
    })
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "reveal_rule": "",
            "is_hidden": False,
            "spatial_position": "",
            "reveals_item_id": "",
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert item.reveal_rule is None
        assert item.is_hidden is False
        assert item.spatial_position is None
        assert item.reveals_item_id is None


async def test_combinable_metadata_fields_omitted_unchanged(client, setup_test_db):
    """Omitting fields in PATCH must NOT clear them — empty values are explicit."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({
        "item_type": "COMBINABLE",
        "reveal_rule": "untouched",
        "spatial_position": "untouched",
    })
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "combination_ingredients": ["x"],
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        # reveal_rule / spatial_position were not in payload, must remain.
        assert item.reveal_rule == "untouched"
        assert item.spatial_position == "untouched"


async def test_combinable_reveal_rule_length_capped_at_500(client, setup_test_db):
    """Hard cap mirrors the schema column size to prevent DB errors."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({"item_type": "COMBINABLE"})
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "reveal_rule": "z" * 600,
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert len(item.reveal_rule) == 500


async def test_combinable_spatial_position_length_capped_at_255(client, setup_test_db):
    """Hard cap mirrors the schema column size to prevent DB errors."""
    user_id, tpl_id, item_id, item_pk = await _seed_template_with_item({"item_type": "COMBINABLE"})
    headers = _auth_headers("type_change_user")

    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": item_id,
            "spatial_position": "z" * 400,
        },
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        item = await db.get(WorldEntity, item_pk)
        assert item is not None
        assert len(item.spatial_position) == 255
