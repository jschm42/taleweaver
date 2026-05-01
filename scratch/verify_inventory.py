import asyncio
import uuid
import json
from sqlalchemy import select
from backend.core.database import AsyncSessionLocal
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity
from backend.engine.world_generator import WorldGenerator

async def test_inventory_init():
    async with AsyncSessionLocal() as db:
        # 1. Setup a test user and adventure
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        if not user:
            print("No user found!")
            return

        template_id = str(uuid.uuid4())
        adv = AdventureTemplate(
            id=template_id,
            owner_id=user.id,
            title="Inventory Test Adventure",
            is_ready=True
        )
        db.add(adv)
        await db.flush()

        # 2. Create a manifest with items in starting_inventory
        manifest = {
            "adventure": {"title": "Inventory Test Adventure"},
            "protagonist": {
                "name": "Test Hero",
                "hp": 200,
                "starting_inventory": ["ITEM_1", "ITEM_2"],
                "starting_equipment": {"Main_Hand": "ITEM_3"}
            },
            "scenes": [{"id": "START", "name": "Start Scene", "description": "Start"}],
            "objects": [
                {"id": "ITEM_1", "name": "Healing Potion", "description": "Heals you.", "item_type": "CONSUMABLE", "start_scene_id": "START"},
                {"id": "ITEM_2", "name": "Iron Key", "description": "Opens a door.", "item_type": "KEY", "start_scene_id": "START"},
                {"id": "ITEM_3", "name": "Iron Sword", "description": "Sharp.", "item_type": "WEAPON", "start_scene_id": "START", "wearable_slots": ["Main_Hand"]}
            ]
        }

        # 3. Apply manifest
        print(f"Applying manifest for template {template_id}...")
        await WorldGenerator.apply_manifest(db, template_id, manifest, user=user)
        await db.commit()

        # 4. Verify results
        av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
        avatar = av_res.scalars().first()
        
        print(f"Avatar Name: {avatar.name}")
        print(f"Inventory Count: {len(avatar.inventory)}")
        for item in avatar.inventory:
            print(f" - Found in inventory: {item.get('name')} (ID: {item.get('id')})")
            
        print(f"Equipment: {avatar.equipment.get('Main_Hand', {}).get('name') if avatar.equipment.get('Main_Hand') else 'None'}")

        # Assertions (simulated)
        inv_ids = [i.get("id") for i in avatar.inventory]
        assert "ITEM_1" in inv_ids, "ITEM_1 missing from inventory"
        assert "ITEM_2" in inv_ids, "ITEM_2 missing from inventory"
        assert avatar.equipment.get("Main_Hand", {}).get("id") == "ITEM_3", "ITEM_3 missing from equipment"
        
        print("SUCCESS: Inventory initialization verified!")

if __name__ == "__main__":
    asyncio.run(test_inventory_init())
