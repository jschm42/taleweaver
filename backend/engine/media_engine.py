"""
MediaEngine — Handles AI image generation for scenes and entities.
Integrated with LiteLLM to support OpenAI (DALL-E), OpenRouter, and Midjourney.
"""
import logging
import os
import uuid
import requests
import litellm
from typing import Optional
from backend.core.security import encryption_util
from backend.core.config import settings

logger = logging.getLogger(__name__)

class MediaEngine:
    @staticmethod
    async def generate_image(
        prompt: str, 
        model: str, 
        api_key: str, 
        provider: str = "openai",
        adventure_id: Optional[str] = None,
        target_dir: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Optional[str]:
        """
        Calls LiteLLM to generate an image and saves it locally.
        """
        if not prompt or not model or not api_key:
            raise ValueError("Missing prompt, model, or API key for image generation.")
            
        # Default target dir if not provided
        if target_dir is None:
            if adventure_id:
                target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id)
            else:
                target_dir = os.path.join(settings.DATA_DIR, "adventures")

        logger.info(f"Generating image with model {model} (provider: {provider}). Prompt: {prompt}")
        
        try:
            kwargs = {
                "prompt": prompt,
                "model": model,
                "api_key": api_key,
                "custom_llm_provider": provider
            }
            
            # Handle OpenRouter specifics
            if provider == "openrouter":
                if not model.startswith("openrouter/"):
                    kwargs["model"] = f"openrouter/{model}"
                # Remove provider override to let LiteLLM use the prefix-based routing
                kwargs.pop("custom_llm_provider", None)

            # Call LiteLLM
            response = litellm.image_generation(**kwargs)
            
            # Check for URL or Base64 data
            image_data = response.data[0]
            image_url = getattr(image_data, 'url', None)
            b64_json = getattr(image_data, 'b64_json', None)
            
            if image_url:
                return await MediaEngine._save_remote_image(image_url, target_dir, filename)
            elif b64_json:
                return await MediaEngine._save_b64_image(b64_json, target_dir, filename)
            else:
                logger.error(f"No image data in response: {response}")
                return None

        except Exception as e:
            error_str = str(e)
            if "Content Moderated" in error_str or "Safety Filter" in error_str:
                logger.warning(f"Image generation was moderated (Safety Filter) for prompt: '{prompt}'. Error: {error_str}")
                return None
            logger.error(f"Image generation failed for prompt: '{prompt}'. Error: {error_str}")
            # Instead of raising, we return None to allow the engine to use placeholders
            return None

    @staticmethod
    async def _save_b64_image(b64_data: str, target_dir: str, filename: Optional[str] = None) -> Optional[str]:
        """Decodes and saves a base64 image string."""
        import base64
        try:
            os.makedirs(target_dir, exist_ok=True)
            final_filename = filename or f"{uuid.uuid4()}.png"
            if not final_filename.endswith(".png"):
                final_filename += ".png"
                
            filepath = os.path.join(target_dir, final_filename)
            
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(b64_data))
            
            # Convert to relative path for URL
            rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
            return f"/data/{rel_path}"
        except Exception as e:
            logger.exception("Error saving b64 image")
            return None

    @staticmethod
    async def _save_remote_image(url: str, target_dir: str, filename: Optional[str] = None) -> Optional[str]:
        """Downloads a remote image and persists it in the specified directory."""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                os.makedirs(target_dir, exist_ok=True)
                final_filename = filename or f"{uuid.uuid4()}.png"
                if not final_filename.endswith(".png"):
                    final_filename += ".png"
                    
                filepath = os.path.join(target_dir, final_filename)
                
                with open(filepath, "wb") as f:
                    f.write(response.content)
                
                # Convert absolute path to relative for frontend
                rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
                return f"/data/{rel_path}"
            else:
                logger.error(f"Failed to download image from {url}, status: {response.status_code}")
                return None
        except Exception as e:
            logger.exception("Error saving remote image")
            return None

    @staticmethod
    async def generate_scene_image(prompt: str, adventure_id: str, user_config: dict, api_keys: dict) -> Optional[str]:
        """High-level wrapper for gameplay scene generation (uses Advanced Model)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: return None
        
        provider = t2i.get("provider", "openai")
        model = t2i.get("advanced_model")
        
        if not model or provider not in api_keys:
            raise ValueError(f"Missing image configuration or API key for {provider}")
            
        api_key = encryption_util.decrypt_key(api_keys[provider])
        
        target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id, "scenes")
        filename = f"{int(uuid.uuid4())}.png"
        
        return await MediaEngine.generate_image(
            prompt=prompt, 
            model=model, 
            api_key=api_key, 
            provider=provider, 
            adventure_id=adventure_id,
            target_dir=target_dir, 
            filename=filename
        )

    @staticmethod
    async def generate_entity_image(prompt: str, adventure_id: str, entity_id: str, entity_type: str, user_config: dict, api_keys: dict) -> Optional[str]:
        """High-level wrapper for NPC/Object generation (uses Simple Model)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: return None
        
        provider = t2i.get("provider", "openai")
        model = t2i.get("simple_model")
        
        if not model or provider not in api_keys:
            raise ValueError(f"Missing image configuration or API key for {provider}")
            
        api_key = encryption_util.decrypt_key(api_keys[provider])
        
        target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id, "entities")
        filename = f"{entity_id}.png"
        
        return await MediaEngine.generate_image(
            prompt=prompt, 
            model=model, 
            api_key=api_key, 
            provider=provider, 
            adventure_id=adventure_id,
            target_dir=target_dir, 
            filename=filename
        )

    @staticmethod
    async def generate_adventure_cover(title: str, context: str, adventure_id: str, user_config: dict, api_keys: dict) -> Optional[str]:
        """High-level wrapper for adventure cover generation (uses Advanced Model, 2:1 aspect ratio)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: return None
        
        provider = t2i.get("provider", "openai")
        model = t2i.get("advanced_model")
        
        if not model or provider not in api_keys:
            raise ValueError(f"Missing image configuration or API key for {provider}")
            
        api_key = encryption_util.decrypt_key(api_keys[provider])
        
        target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id)
        filename = "cover.png"
        
        # Craft a prompt specifically requesting landscape/2:1 ratio
        prompt = (
            f"Epic cinematic adventure cover: {title}. {context}. "
            "Landscape format, 2:1 aspect ratio, high fantasy art style, immersive atmosphere, detailed concept art."
        )
        
        return await MediaEngine.generate_image(
            prompt=prompt, 
            model=model, 
            api_key=api_key, 
            provider=provider, 
            adventure_id=adventure_id,
            target_dir=target_dir, 
            filename=filename
        )
