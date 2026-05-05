import uuid
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.engine.rule_engine import AdventureGenerationRequest
from backend.engine.world_generator import WorldGenerator
from backend.core.style_catalog import default_image_styles_catalog

logger = logging.getLogger(__name__)

class AdventureGeneratorService:
    @staticmethod
    async def get_available_image_styles(user: User) -> List[str]:
        """Returns the list of available image styles for the user."""
        catalog = user.image_styles_catalog or []
        if not catalog:
            catalog = default_image_styles_catalog()
        # Return names/IDs of styles
        return [s.get("id") or s.get("name") for s in catalog if s.get("id") or s.get("name")]

    @staticmethod
    async def get_available_tones(user: User) -> List[str]:
        """Returns the list of available narrative tones."""
        catalog = user.tone_catalog or []
        if not catalog:
            return ["Heroic", "Grimdark", "Whimsical", "Horror", "Satirical", "Mystery", "Serious", "Cyberpunk", "Post-Apocalyptic"]
        return [t.get("id") or t.get("name") for t in catalog if t.get("id") or t.get("name")]


    @staticmethod
    async def generate_adventure(
        db: AsyncSession,
        user: User,
        request: AdventureGenerationRequest
    ) -> str:
        """
        Triggers the world generation and saves the new template to the user's library.
        Returns the ID of the new adventure.
        """
        def clean_tone(val):
            if not val: return None
            if isinstance(val, dict):
                return val.get("id") or val.get("name") or str(val)
            return str(val)

        # 1. Create a new AdventureTemplate entry

        new_id = str(uuid.uuid4())
        new_template = AdventureTemplate(
            id=new_id,
            owner_id=user.id,
            title=request.title,
            original_prompt=request.prompt,
            min_scenes=request.min_scenes,
            max_scenes=request.max_scenes,
            generate_scene_images=request.generate_scene_images,
            selected_image_styles=request.selected_image_styles,
            selected_tone=clean_tone(request.selected_tone),


            min_awards=request.min_awards,
            max_awards=request.max_awards,
            award_generation_enabled=request.award_generation_enabled,
            creation_status="Initializing...",
            is_ready=False
        )
        db.add(new_template)
        await db.flush()

        logger.info(f"Starting background generation for adventure '{request.title}' ({new_id})")

        try:
            # Note: We await here because the GameTurnManager expects a resolution 
            # to narrate back to the player. In a production environment, this might
            # be a Celery task or similar, but for TaleWeaver's current architecture,
            # awaiting is consistent with how manual generation works.
            await WorldGenerator.generate_world(
                db=db,
                user=user,
                template_id=new_id,
                title=request.title,
                original_prompt=request.prompt,
                generate_scene_images=request.generate_scene_images,
                generate_npc_images=True, 
                generate_item_images=True, 
                min_scenes=request.min_scenes,
                max_scenes=request.max_scenes,
                award_generation_enabled=request.award_generation_enabled,
                min_awards=request.min_awards,
                max_awards=request.max_awards,
                selected_image_styles=request.selected_image_styles,
                selected_tone=new_template.selected_tone
            )

            
            # Re-fetch or refresh to ensure we have the latest state before final update
            await db.refresh(new_template)
            new_template.is_ready = True
            new_template.creation_status = "Ready"
            await db.flush()
            
            logger.info(f"Adventure generation successful: {new_id}")
            return new_id
            
        except Exception as e:
            logger.exception(f"Adventure generation failed for {new_id}: {e}")
            # Ensure we update the template status so the user doesn't see it hanging
            try:
                await db.refresh(new_template)
                new_template.creation_status = "Failed"
                new_template.creation_error = str(e)
                await db.flush()
            except:
                pass
            raise e
