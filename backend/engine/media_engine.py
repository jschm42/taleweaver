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

logger = logging.getLogger(__name__)

class MediaEngine:
    @staticmethod
    async def generate_image(
        prompt: str, 
        model: str, 
        api_key: str, 
        provider: str = "openai"
    ) -> Optional[str]:
        """
        Calls LiteLLM to generate an image and saves it locally.
        """
        if not prompt or not model or not api_key:
            return None
            
        logger.info(f"Generating image with model {model} (provider: {provider}). Prompt: {prompt}")
        
        try:
            kwargs = {
                "prompt": prompt,
                "model": model,
                "api_key": api_key,
            }
            
            # Handle OpenRouter specifics
            if provider == "openrouter":
                kwargs["api_base"] = "https://openrouter.ai/api/v1"
                if model.startswith("openrouter/"):
                    kwargs["model"] = model.replace("openrouter/", "")

            # Call LiteLLM
            response = litellm.image_generation(**kwargs)
            image_url = response.data[0].url
            
            if not image_url:
                logger.error("No image URL returned from provider.")
                return None

            # Download and save locally
            return await MediaEngine._save_remote_image(image_url)

        except Exception as e:
            logger.exception("Image generation failed")
            return None

    @staticmethod
    async def _save_remote_image(url: str) -> Optional[str]:
        """Downloads a remote image and persists it in the /uploads directory."""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                os.makedirs("uploads", exist_ok=True)
                filename = f"{uuid.uuid4()}.png"
                filepath = os.path.join("uploads", filename)
                
                with open(filepath, "wb") as f:
                    f.write(response.content)
                
                return f"/uploads/{filename}"
            else:
                logger.error(f"Failed to download image from {url}, status: {response.status_code}")
                return None
        except Exception as e:
            logger.exception("Error saving remote image")
            return None

    @staticmethod
    async def generate_scene_image(prompt: str, user_config: dict, api_keys: dict) -> Optional[str]:
        """High-level wrapper for gameplay scene generation (uses Advanced Model)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: return None
        
        provider = t2i.get("provider", "openai")
        model = t2i.get("advanced_model")
        
        if not model or provider not in api_keys:
            return None
            
        api_key = encryption_util.decrypt_key(api_keys[provider])
        return await MediaEngine.generate_image(prompt, model, api_key, provider)

    @staticmethod
    async def generate_entity_image(prompt: str, user_config: dict, api_keys: dict) -> Optional[str]:
        """High-level wrapper for NPC/Object generation (uses Simple Model)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: return None
        
        provider = t2i.get("provider", "openai")
        model = t2i.get("simple_model")
        
        if not model or provider not in api_keys:
            return None
            
        api_key = encryption_util.decrypt_key(api_keys[provider])
        return await MediaEngine.generate_image(prompt, model, api_key, provider)
