"""
MediaEngine — Handles AI image generation for scenes and entities.
Integrated with LiteLLM to support OpenAI (DALL-E), OpenRouter, and Midjourney.
"""
import logging
import os
import uuid
import requests
import litellm
from typing import Optional, Any
from backend.core.security import encryption_util
from backend.core.config import settings

logger = logging.getLogger(__name__)

class MediaEngine:
    @staticmethod
    async def generate_image(
        prompt: str, 
        model: str, 
        api_key: Optional[str], 
        provider: str = "openai",
        adventure_id: Optional[str] = None,
        target_dir: Optional[str] = None,
        filename: Optional[str] = None,
        provider_options: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Calls LiteLLM to generate an image and saves it locally.
        """
        provider_key = (provider or "openai").lower()
        if not prompt or not model:
            raise ValueError("Missing prompt or model for image generation.")
        if provider_key == "ollama":
            remote_prefixes = (
                "openai/",
                "openrouter/",
                "anthropic/",
                "google/",
                "gemini/",
                "azure/",
                "bedrock/",
                "cohere/",
            )
            if model.startswith(remote_prefixes):
                raise ValueError(
                    f"Provider is 'ollama' but image model '{model}' looks like a remote/cloud model. "
                    "Configure a local Ollama image model (for example: x/flux2-klein)."
                )
        if provider_key != "ollama" and not api_key:
            raise ValueError(f"Missing API key for image generation provider '{provider_key}'.")
            
        # Default target dir if not provided
        if target_dir is None:
            if adventure_id:
                target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id)
            else:
                target_dir = os.path.join(settings.DATA_DIR, "adventures")

        logger.info(f"Generating image with model {model} (provider: {provider_key}). Prompt: {prompt}")
        
        try:
            provider_options = provider_options or {}

            kwargs: dict[str, Any] = {
                "prompt": prompt,
                "model": model,
                "custom_llm_provider": provider_key,
            }
            if api_key:
                kwargs["api_key"] = api_key

            # Pass common optional generation controls through when available.
            optional_fields = ("width", "height", "steps", "seed", "negative_prompt")
            for field in optional_fields:
                value = provider_options.get(field)
                if value is not None:
                    kwargs[field] = value
            
            # Handle OpenRouter specifics
            if provider_key == "openrouter":
                if not model.startswith("openrouter/"):
                    kwargs["model"] = f"openrouter/{model}"
                # Remove provider override to let LiteLLM use the prefix-based routing
                kwargs.pop("custom_llm_provider", None)

            if provider_key == "ollama":
                ollama_url = (provider_options.get("ollama_url") or "http://localhost:11434").rstrip("/")
                kwargs["api_base"] = ollama_url

            # Call LiteLLM first
            response = litellm.image_generation(**kwargs)
            image_url, b64_json = MediaEngine._extract_image_payload(response)
            
            if image_url:
                return await MediaEngine._save_remote_image(image_url, target_dir, filename)
            elif b64_json:
                return await MediaEngine._save_b64_image(b64_json, target_dir, filename)
            elif provider_key == "ollama":
                logger.warning("LiteLLM returned no image payload for ollama; trying direct Ollama API fallback.")
                direct_result = await MediaEngine._generate_image_ollama_direct(
                    prompt=prompt,
                    model=model,
                    ollama_url=provider_options.get("ollama_url") or "http://localhost:11434",
                    target_dir=target_dir,
                    filename=filename,
                    width=provider_options.get("width"),
                    height=provider_options.get("height"),
                    steps=provider_options.get("steps"),
                    seed=provider_options.get("seed"),
                    negative_prompt=provider_options.get("negative_prompt"),
                )
                if direct_result:
                    return direct_result
                raise RuntimeError("Ollama image generation returned no image payload.")
            else:
                logger.error(f"No image data in response: {response}")
                return None

        except Exception as e:
            error_str = str(e)
            if provider_key == "ollama":
                logger.warning(f"LiteLLM ollama path failed ({error_str}); trying direct Ollama API fallback.")
                direct_result = await MediaEngine._generate_image_ollama_direct(
                    prompt=prompt,
                    model=model,
                    ollama_url=(provider_options or {}).get("ollama_url") or "http://localhost:11434",
                    target_dir=target_dir,
                    filename=filename,
                    width=(provider_options or {}).get("width"),
                    height=(provider_options or {}).get("height"),
                    steps=(provider_options or {}).get("steps"),
                    seed=(provider_options or {}).get("seed"),
                    negative_prompt=(provider_options or {}).get("negative_prompt"),
                )
                if direct_result:
                    return direct_result
                raise RuntimeError(
                    f"Ollama image generation failed for model '{model}'. "
                    f"Original error: {error_str}"
                )
            if "Content Moderated" in error_str or "Safety Filter" in error_str:
                logger.warning(f"Image generation was moderated (Safety Filter) for prompt: '{prompt}'. Error: {error_str}")
                return None
            logger.error(f"Image generation failed for prompt: '{prompt}'. Error: {error_str}")
            # Instead of raising, we return None to allow the engine to use placeholders
            return None

    @staticmethod
    def _extract_image_payload(response: Any) -> tuple[Optional[str], Optional[str]]:
        """Extract URL or base64 image payload from provider responses."""
        if not response:
            return None, None

        data = getattr(response, "data", None)
        if isinstance(data, list) and data:
            image_data = data[0]
            image_url = getattr(image_data, "url", None)
            b64_json = getattr(image_data, "b64_json", None)
            if image_url or b64_json:
                return image_url, b64_json

            if isinstance(image_data, dict):
                return image_data.get("url"), image_data.get("b64_json")

        if isinstance(response, dict):
            images = response.get("images")
            if isinstance(images, list) and images:
                first = images[0]
                if isinstance(first, str):
                    return None, first
            return response.get("url"), response.get("b64_json")

        return None, None

    @staticmethod
    async def _generate_image_ollama_direct(
        prompt: str,
        model: str,
        ollama_url: str,
        target_dir: str,
        filename: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        steps: Optional[int] = None,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """Generate an image through Ollama's local HTTP API."""
        try:
            base = ollama_url.rstrip("/")
            if not base.endswith("/api"):
                base = f"{base}/api"
            endpoint = f"{base}/generate"

            options: dict[str, Any] = {}
            if width is not None:
                options["width"] = width
            if height is not None:
                options["height"] = height
            if steps is not None:
                options["steps"] = steps
            if seed is not None:
                options["seed"] = seed
            if negative_prompt:
                options["negative_prompt"] = negative_prompt

            payload: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
            if options:
                payload["options"] = options

            response = requests.post(endpoint, json=payload, timeout=120)
            if response.status_code != 200:
                logger.error(
                    "Ollama direct image generation failed. status=%s body=%s",
                    response.status_code,
                    response.text,
                )
                return None

            body = response.json()
            image_url, b64_json = MediaEngine._extract_image_payload(body)
            if image_url:
                return await MediaEngine._save_remote_image(image_url, target_dir, filename)
            if b64_json:
                return await MediaEngine._save_b64_image(b64_json, target_dir, filename)

            logger.error("Ollama response did not include image payload: %s", body)
            return None
        except Exception:
            logger.exception("Error during direct Ollama image generation")
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
        
        provider = (t2i.get("provider", "openai") or "openai").lower()
        model = t2i.get("advanced_model")
        
        if not model:
            raise ValueError("Missing image model configuration.")
        if provider != "ollama" and provider not in api_keys:
            raise ValueError(f"Missing image configuration or API key for {provider}")

        api_key = encryption_util.decrypt_key(api_keys[provider]) if provider in api_keys else None
        
        target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id, "scenes")
        filename = f"{uuid.uuid4().hex}.png"
        
        return await MediaEngine.generate_image(
            prompt=prompt, 
            model=model, 
            api_key=api_key, 
            provider=provider, 
            adventure_id=adventure_id,
            target_dir=target_dir, 
            filename=filename,
            provider_options=t2i,
        )

    @staticmethod
    async def generate_entity_image(prompt: str, adventure_id: str, entity_id: str, entity_type: str, user_config: dict, api_keys: dict) -> Optional[str]:
        """High-level wrapper for NPC/Object generation (uses Simple Model)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: return None
        
        provider = (t2i.get("provider", "openai") or "openai").lower()
        model = t2i.get("simple_model")
        
        if not model:
            raise ValueError("Missing image model configuration.")
        if provider != "ollama" and provider not in api_keys:
            raise ValueError(f"Missing image configuration or API key for {provider}")

        api_key = encryption_util.decrypt_key(api_keys[provider]) if provider in api_keys else None
        
        target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id, "entities")
        filename = f"{entity_id}.png"
        
        return await MediaEngine.generate_image(
            prompt=prompt, 
            model=model, 
            api_key=api_key, 
            provider=provider, 
            adventure_id=adventure_id,
            target_dir=target_dir, 
            filename=filename,
            provider_options=t2i,
        )

    @staticmethod
    async def generate_adventure_cover(title: str, context: str, adventure_id: str, user_config: dict, api_keys: dict) -> Optional[str]:
        """High-level wrapper for adventure cover generation (uses Advanced Model, 2:1 aspect ratio)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: return None
        
        provider = (t2i.get("provider", "openai") or "openai").lower()
        model = t2i.get("advanced_model")
        
        if not model:
            raise ValueError("Missing image model configuration.")
        if provider != "ollama" and provider not in api_keys:
            raise ValueError(f"Missing image configuration or API key for {provider}")

        api_key = encryption_util.decrypt_key(api_keys[provider]) if provider in api_keys else None
        
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
            filename=filename,
            provider_options=t2i,
        )
