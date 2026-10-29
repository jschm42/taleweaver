"""Tests for the author-defined dialog skin (``ui_theme``) of adventures."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.core.ui_theme import normalize_ui_theme
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from tests.test_adventures_api import _create_adventure


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"skin": "noir", "accent": "#C8102E"}, {"skin": "noir", "accent": "#c8102e"}),
        ({"skin": " Chronicle "}, {"skin": "chronicle"}),
        ("terminal", {"skin": "terminal"}),
        ({"accent": "#123abc"}, {"accent": "#123abc"}),
        ({"skin": "neon-dreams", "accent": "#123abc"}, {"accent": "#123abc"}),
        ({"skin": "noir", "accent": "red; background:url(https://evil)"}, {"skin": "noir"}),
        ({"skin": "noir", "css": "body{display:none}"}, {"skin": "noir"}),
        ({"skin": "unknown"}, None),
        ({}, None),
        (None, None),
        (42, None),
    ],
)
def test_normalize_ui_theme_keeps_only_whitelisted_values(raw, expected):
    # Arrange / Act
    result = normalize_ui_theme(raw)

    # Assert
    assert result == expected


async def test_update_adventure_ui_theme_is_validated(auth_client: AsyncClient):
    """PATCH stores only the whitelisted skin and accent and returns them."""
    # Arrange
    ids = await _create_adventure(auth_client, "Skinned Quest")

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/{ids['adventure_id']}",
        json={"ui_theme": {"skin": "grimoire", "accent": "#B91C1C", "css": "*{}"}},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json()["ui_theme"] == {"skin": "grimoire", "accent": "#b91c1c"}


async def test_update_adventure_ui_theme_can_be_cleared(auth_client: AsyncClient):
    """Sending null (or only invalid values) resets the adventure to the automatic skin."""
    # Arrange
    ids = await _create_adventure(auth_client, "Unskinned Quest")
    await auth_client.patch(
        f"/api/adventures/{ids['adventure_id']}", json={"ui_theme": {"skin": "noir"}}
    )

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/{ids['adventure_id']}", json={"ui_theme": {"skin": "not-a-skin"}}
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json()["ui_theme"] is None


async def test_import_adv_manifest_reads_nested_ui_theme(auth_client, setup_test_db):
    """The importer keeps a valid ``adventure.ui_theme`` and drops anything else."""
    # Arrange
    from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
    from tests.conftest import TestSessionLocal

    payload = {
        "format": "TaleWeaver",
        "version": "1.2",
        "adventure": {
            "title": "Skin Import Quest",
            "rule_enforcement_mode": "rpg",
            "ui_theme": {"skin": "terminal", "accent": "#22D3EE", "stylesheet": "evil.css"},
        },
        "protagonist": {"name": "Hero", "role": "Adventurer", "description": "Brave"},
        "scenes": [{"id": "START", "label": "Start", "description": "Begin"}],
        "exits": [],
        "npcs": [],
        "objects": [],
        "quests": [],
        "awards": [],
    }

    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()

        # Act
        success = await AdventureTemplateImporter.import_adv_manifest(
            db, payload, owner_id=user.id, allow_session=False
        )
        adv = (
            (
                await db.execute(
                    select(AdventureTemplate).where(AdventureTemplate.title == "Skin Import Quest")
                )
            )
            .scalars()
            .first()
        )

    # Assert
    assert success
    assert adv is not None
    assert adv.ui_theme == {"skin": "terminal", "accent": "#22d3ee"}
