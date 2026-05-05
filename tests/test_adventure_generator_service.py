import pytest

from backend.engine.adventure_generator_service import AdventureGeneratorService
from backend.engine.rule_engine import AdventureGenerationRequest
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

pytestmark = pytest.mark.asyncio


async def test_service_disables_all_image_generation_when_scene_images_disabled(setup_test_db, monkeypatch):
    """A text-only generation request must disable every AI image-generation branch."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = User(username="imgless_user", hashed_password="pw", role="user")
        db.add(user)
        await db.commit()

        captured_kwargs = {}

        async def fake_generate_world(*_args, **kwargs):
            captured_kwargs.update(kwargs)
            return None

        monkeypatch.setattr(
            "backend.engine.adventure_generator_service.WorldGenerator.generate_world",
            fake_generate_world,
        )

        req = AdventureGenerationRequest(
            title="Text-Only Adventure",
            prompt="Generate a cozy mystery world without images.",
            min_scenes=3,
            max_scenes=5,
            generate_scene_images=False,
            selected_image_styles=["cinematic-realism"],
            selected_tone="mystery",
            min_awards=1,
            max_awards=3,
            award_generation_enabled=True,
        )

        new_id = await AdventureGeneratorService.generate_adventure(db, user, req)

        assert captured_kwargs.get("generate_scene_images") is False
        assert captured_kwargs.get("generate_npc_images") is False
        assert captured_kwargs.get("generate_item_images") is False

        adventure = await db.get(AdventureTemplate, new_id)
        assert adventure is not None
        assert adventure.generate_scene_images is False
