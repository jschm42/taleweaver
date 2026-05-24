import pytest
import asyncio
from unittest.mock import AsyncMock

from backend.engine.world_generator import WorldGenerator
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from sqlalchemy.future import select

pytestmark = pytest.mark.asyncio


async def test_duplicate_media_reuse_npcs_and_objects(setup_test_db, monkeypatch):
    """Verify that duplicate NPCs and objects reuse the first resolved image and do not trigger extra generation calls."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Create test user
        user = User(
            username="test_media_user",
            hashed_password="pw",
            role="user",
            t2i_settings={"provider": "ollama", "advanced_model": "stable-diffusion", "basic_model": "stable-diffusion", "simple_model": "stable-diffusion"},
            image_styles_catalog={},
        )
        db.add(user)
        await db.commit()

        # Create test adventure template
        template = AdventureTemplate(
            title="House of Rats",
            owner_id=user.id,
            original_prompt="A scary cellar filled with rats and health potions.",
            teaser="A scary cellar.",
            selected_image_styles=["cinematic"],
        )
        db.add(template)
        await db.commit()

        # Set up manifest with duplicate NPCs and duplicate objects
        manifest_dict = {
            "teaser": "House of Rats",
            "plot": "Explore a rat-infested cellar.",
            "rules": "Be careful of multiple rats.",
            "intro_text": "You enter the dark cellar...",
            "walkthrough": "Kill the rats and use the potions.",
            "completed_condition": "All rats are defeated.",
            "gameover_condition": "Player HP drops to 0.",
            "tts_director_notes": "Solemn tone.",
            "can_damage_npcs": True,
            "npcs_can_damage_protagonist": True,
            "language": "English",
            "origin_id": "",
            "protagonist": {
                "name": "Hero",
                "role": "Adventurer",
                "description": "A brave fighter.",
                "goal": "Survive the cellar.",
                "character": "Brave and strong.",
                "strength": 12,
                "dexterity": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
                "armor_class": 10,
                "hp": 100,
                "mana": 50,
                "stamina": 100,
                "starting_inventory": [],
                "starting_equipment": {
                    "Head": "", "Chest": "", "Hands": "", "Legs": "", "Feet": "",
                    "Neck": "", "Ring_1": "", "Ring_2": "", "MainHand": "", "OffHand": ""
                }
            },
            "scenes": [
                {"id": "CELLAR", "name": "Dark Cellar", "description": "A damp and creepy underground space."}
            ],
            "exits": [],
            "npcs": [
                {
                    "id": "RAT_1",
                    "name": "Scurrying Rat",
                    "description": "A dirty rat with sharp teeth.",
                    "goal": "Bite invaders.",
                    "character": "Aggressive.",
                    "start_scene_id": "CELLAR",
                    "spatial_position": "in the corner",
                    "npc_type": "ANIMAL",
                    "movement_type": "MOVABLE",
                    "hp": 15,
                    "mana": 0,
                    "stamina": 50,
                    "is_attackable": True,
                    "is_killable": True,
                    "is_hidden": False,
                    "reveal_rule": "",
                    "inventory": []
                },
                {
                    "id": "RAT_2",
                    "name": "Scurrying Rat",
                    "description": "A dirty rat with sharp teeth.",
                    "goal": "Bite invaders.",
                    "character": "Aggressive.",
                    "start_scene_id": "CELLAR",
                    "spatial_position": "near the shelf",
                    "npc_type": "ANIMAL",
                    "movement_type": "MOVABLE",
                    "hp": 12,  # slightly different HP
                    "mana": 0,
                    "stamina": 50,
                    "is_attackable": True,
                    "is_killable": True,
                    "is_hidden": False,
                    "reveal_rule": "",
                    "inventory": []
                }
            ],
            "objects": [
                {
                    "id": "POTION_1",
                    "name": "Health Potion",
                    "description": "A small vial filled with sparkling red liquid.",
                    "start_scene_id": "CELLAR",
                    "spatial_position": "on the shelf",
                    "item_type": "CONSUMABLE",
                    "wearable_slots": [],
                    "is_hidden": False,
                    "reveal_rule": "",
                    "is_portable": True,
                    "stat_modifier_strength": 0,
                    "stat_modifier_dexterity": 0,
                    "stat_modifier_intelligence": 0,
                    "stat_modifier_wisdom": 0,
                    "stat_modifier_charisma": 0,
                    "stat_modifier_armor_class": 0,
                    "hp_change": 50,
                    "stamina_change": 0,
                    "mana_change": 0,
                    "inventory": [],
                    "combination_ingredients": [],
                    "reveals_item_id": ""
                },
                {
                    "id": "POTION_2",
                    "name": "Health Potion",
                    "description": "A small vial filled with sparkling red liquid.",
                    "start_scene_id": "CELLAR",
                    "spatial_position": "in the chest",
                    "item_type": "CONSUMABLE",
                    "wearable_slots": [],
                    "is_hidden": False,
                    "reveal_rule": "",
                    "is_portable": True,
                    "stat_modifier_strength": 0,
                    "stat_modifier_dexterity": 0,
                    "stat_modifier_intelligence": 0,
                    "stat_modifier_wisdom": 0,
                    "stat_modifier_charisma": 0,
                    "stat_modifier_armor_class": 0,
                    "hp_change": 50,
                    "stamina_change": 0,
                    "mana_change": 0,
                    "inventory": [],
                    "combination_ingredients": [],
                    "reveals_item_id": ""
                }
            ],
            "quests": [],
            "awards": []
        }

        # Track media generation calls
        generate_npc_calls = []
        generate_object_calls = []

        async def fake_generate_entity_image(prompt, adventure_id, entity_id, entity_type, *args, **kwargs):
            if entity_type == "NPC":
                generate_npc_calls.append(entity_id)
                return f"https://generated.images/npc_{entity_id}.png"
            elif entity_type == "OBJECT":
                generate_object_calls.append(entity_id)
                return f"https://generated.images/object_{entity_id}.png"
            return "https://generated.images/fallback.png"

        # Mock MediaEngine calls
        monkeypatch.setattr(
            "backend.engine.media_engine.MediaEngine.generate_entity_image",
            fake_generate_entity_image,
        )
        monkeypatch.setattr(
            "backend.engine.media_engine.MediaEngine.generate_adventure_cover",
            AsyncMock(return_value="https://generated.images/cover.png"),
        )
        monkeypatch.setattr(
            "backend.engine.media_engine.MediaEngine.generate_scene_image",
            AsyncMock(return_value="https://generated.images/scene.png"),
        )

        # Call apply_manifest
        await WorldGenerator.apply_manifest(
            db,
            template.id,
            manifest_dict,
            user=user,
            gen_npc=True,
            gen_items=True,
            gen_scenes=True,
        )

        # Retrieve entities from DB to verify image URLs
        npcs_res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == template.id,
                WorldEntity.entity_type == "NPC"
            )
        )
        npcs_in_db = {n.id: n for n in npcs_res.scalars().all()}

        objects_res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == template.id,
                WorldEntity.entity_type == "OBJECT"
            )
        )
        objects_in_db = {o.id: o for o in objects_res.scalars().all()}

        # Assertions for NPCs
        assert "RAT_1" in npcs_in_db
        assert "RAT_2" in npcs_in_db
        assert npcs_in_db["RAT_1"].image_url == "https://generated.images/npc_RAT_1.png"
        # RAT_2 should have copied the visual from RAT_1
        assert npcs_in_db["RAT_2"].image_url == "https://generated.images/npc_RAT_1.png"
        
        # Verify that generate_entity_image was only called once for the rat NPC (for RAT_1)
        assert len(generate_npc_calls) == 1
        assert "RAT_1" in generate_npc_calls
        assert "RAT_2" not in generate_npc_calls

        # Assertions for Objects
        assert "POTION_1" in objects_in_db
        assert "POTION_2" in objects_in_db
        assert objects_in_db["POTION_1"].image_url == "https://generated.images/object_POTION_1.png"
        # POTION_2 should have copied the visual from POTION_1
        assert objects_in_db["POTION_2"].image_url == "https://generated.images/object_POTION_1.png"
        
        # Verify that generate_entity_image was only called once for the potion object (for POTION_1)
        assert len(generate_object_calls) == 1
        assert "POTION_1" in generate_object_calls
        assert "POTION_2" not in generate_object_calls
