import asyncio
import sys
import os
from backend.core.database import AsyncSessionLocal
from sqlalchemy import select
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity
from backend.engine.world_generator import WorldGenerator

async def verify_inventory():
    async with AsyncSessionLocal() as db:
        # 1. Create a dummy adventure
        template_id = "test_adv_123"
        adv = await db.get(AdventureTemplate, template_id)
        if adv:
            from sqlalchemy import delete
            from backend.models.session_state import SessionState
            await db.execute(delete(SessionState).where(SessionState.template_id == template_id))
            await db.execute(delete(Avatar).where(Avatar.template_id == template_id))
            await db.execute(delete(WorldEntity).where(WorldEntity.template_id == template_id))
            await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == template_id))
            await db.commit()

        adv = AdventureTemplate(
            id=template_id,
            title="Test Adventure",
            owner_id="system",
            is_ready=True
        )
        db.add(adv)
        await db.commit()

        # 2. Define manifest with mixed slots
        manifest = {
            "protagonist": {
                "name": "Test Hero",
                "hp": 200,
                "starting_inventory": ["ITEM_1", "ITEM_2"],
                "starting_equipment": {
                    "MainHand": "ITEM_3",
                    "Feet": "ITEM_4"
                }
            },
            "scenes": [{"id": "START", "name": "Start Room", "description": "A room."}],
            "exits": [],
            "npcs": [],
            "objects": [
                {"id": "ITEM_1", "name": "Healing Potion", "description": "Red liquid.", "start_scene_id": "START", "type": "OBJECT", "item_type": "CONSUMABLE"},
                {"id": "ITEM_2", "name": "Iron Key", "description": "Rusty.", "start_scene_id": "START", "type": "OBJECT", "item_type": "KEY"},
                {"id": "ITEM_3", "name": "Iron Sword", "description": "Sharp.", "start_scene_id": "START", "type": "OBJECT", "item_type": "WEAPON"},
                {"id": "ITEM_4", "name": "Iron Boots", "description": "Clunky.", "start_scene_id": "START", "type": "OBJECT", "item_type": "WEARABLE", "wearable_slots": ["Feet"]}
            ],
            "teaser": "Test",
            "plot": "Test",
            "rules": "Test",
            "walkthrough": "Test",
            "completed_condition": "Test",
            "gameover_condition": "Test"
        }

        # 3. Apply manifest
        print(f"Applying manifest for {template_id}...")
        await WorldGenerator.apply_manifest(db, template_id, manifest)
        await db.commit()

        # 4. Check Avatar
        av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
        avatar = av_res.scalars().first()

        print(f"Avatar Name: {avatar.name}")
        print(f"Inventory Count: {len(avatar.inventory)}")
        for item in avatar.inventory:
            print(f" - Found in inventory: {item['name']} (ID: {item['id']})")

        print(f"Equipment MainHand: {avatar.equipment.get('MainHand', {}).get('name') if avatar.equipment.get('MainHand') else 'EMPTY'}")
        print(f"Equipment Feet: {avatar.equipment.get('Feet', {}).get('name') if avatar.equipment.get('Feet') else 'EMPTY'}")

        # Verification
        assert len(avatar.inventory) == 2, "Inventory should have 2 items"
        assert any(i['id'] == "ITEM_1" for i in avatar.inventory)
        assert any(i['id'] == "ITEM_2" for i in avatar.inventory)
        assert avatar.equipment.get("MainHand", {}).get("id") == "ITEM_3", "MainHand should have ITEM_3"
        assert avatar.equipment.get("Feet", {}).get("id") == "ITEM_4", "Feet should have ITEM_4"

        print("SUCCESS: Inventory and Equipment initialization verified!")

if __name__ == "__main__":
    asyncio.run(verify_inventory())
