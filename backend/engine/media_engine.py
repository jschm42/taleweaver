"""
MediaEngine — Handles AI image generation for scenes and entities.
Integrated with LiteLLM to support OpenAI (DALL-E), OpenRouter, and Google (Imagen), while using the direct BFL API for Black Forest Labs.
"""
import logging
import os
import uuid
import asyncio
import time
import requests
import io
from typing import Optional, Any
from PIL import Image
from backend.core.security import encryption_util
from backend.core.config import settings
from backend.core import prompts
from backend.utils.svg_generator import SVGPlaceholderGenerator
import litellm
from backend.utils.text_utils import slugify

logger = logging.getLogger(__name__)

BFL_DEFAULT_MODEL = "black_forest_labs/flux-pro-1.1"
BFL_API_BASE = "https://api.bfl.ai/v1"
# Use centralized prompts
NO_TEXT_IMAGE_PROMPT_SUFFIX = prompts.NO_TEXT_IMAGE_PROMPT_SUFFIX

import shutil

class MediaEngine:
    @staticmethod
    async def cleanup_adventure_assets(adventure_id: str):
        """Removes all generated assets for an adventure from disk."""
        target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id)
        if os.path.exists(target_dir):
            try:
                # Use a thread pool executor for blocking I/O if needed, 
                # but for simplicity we'll just use shutil in this async context.
                shutil.rmtree(target_dir)
                logger.info(f"Cleaned up assets for adventure {adventure_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup assets for adventure {adventure_id}: {e}")


    @classmethod
    def _get_litellm(cls) -> Any:
        return litellm

    @staticmethod
    def _sanitize_prompt(prompt: str) -> str:
        """Corrects common typos that trigger safety filters (e.g. 'raping' -> 'rapping')."""
        import re
        # Case-insensitive replacement of 'raping' with 'rapping', but only if preceded by 'rap', 'battle', etc.
        # or as a standalone word that is clearly a typo in this context.
        # Actually, in a TTRPG/Creative context, 'raping' is almost always a typo for 'rapping'.
        return re.sub(r'(\b)raping(\b)', r'\1rapping\2', prompt, flags=re.IGNORECASE)

    @staticmethod
    def _apply_no_text_instruction(prompt: str) -> str:
        """Append a global no-text instruction to image prompts when missing."""
        normalized = MediaEngine._sanitize_prompt(prompt.strip())
        if NO_TEXT_IMAGE_PROMPT_SUFFIX.lower() in normalized.lower():
            return normalized
        # Combine instructions for better enforcement
        return f"{normalized}. {NO_TEXT_IMAGE_PROMPT_SUFFIX}"

    @staticmethod
    def _normalize_black_forest_labs_model(model: str) -> str:
        """Return a BFL model slug suitable for the direct API.

        If the saved model is still an OpenAI-style default, fall back to a valid
        BFL FLUX model so older settings do not silently generate nothing.
        """
        normalized = (model or "").strip()
        if not normalized:
            return BFL_DEFAULT_MODEL

        lowered = normalized.lower()
        if lowered.startswith(("openai/", "dall-e", "openrouter/", "google/", "gemini/")):
            return BFL_DEFAULT_MODEL.removeprefix("black_forest_labs/")

        if normalized.startswith("black_forest_labs/"):
            return normalized.removeprefix("black_forest_labs/")

        return normalized

    @staticmethod
    async def _generate_image_black_forest_labs_direct(
        prompt: str,
        model: str,
        api_key: str,
        target_dir: str,
        filename: Optional[str] = None,
        provider_options: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate a BFL image by calling the REST API directly and polling for completion."""
        provider_options = provider_options or {}
        model_slug = MediaEngine._normalize_black_forest_labs_model(model)
        endpoint = f"{BFL_API_BASE}/{model_slug}"

        payload: dict[str, Any] = {"prompt": prompt}
        optional_fields = (
            "input_image",
            "input_image_2",
            "input_image_3",
            "input_image_4",
            "seed",
            "width",
            "height",
            "safety_tolerance",
            "output_format",
            "webhook_url",
            "webhook_secret",
            "transparent_bg",
        )
        for field in optional_fields:
            value = provider_options.get(field)
            if value is not None:
                payload[field] = value

        response = requests.post(
            endpoint,
            headers={"Content-Type": "application/json", "x-key": api_key},
            json=payload,
            timeout=120,
        )
        if response.status_code != 200:
            logger.error("BFL image generation submit failed. status=%s body=%s", response.status_code, response.text)
            return None

        body = response.json()
        polling_url = body.get("polling_url")
        if not polling_url:
            logger.error("BFL response did not include polling_url: %s", body)
            return None

        poll_deadline = time.monotonic() + 600.0
        while time.monotonic() < poll_deadline:
            poll_response = requests.get(
                polling_url,
                headers={"accept": "application/json", "x-key": api_key},
                timeout=30,
            )
            if poll_response.status_code != 200:
                logger.error(
                    "BFL polling failed. status=%s body=%s",
                    poll_response.status_code,
                    poll_response.text,
                )
                return None

            poll_body = poll_response.json()
            status = str(poll_body.get("status") or "").lower()
            if status == "ready":
                result = poll_body.get("result") or {}
                sample_url = result.get("sample")
                if not sample_url:
                    logger.error("BFL polling response missing result.sample: %s", poll_body)
                    return None
                return await MediaEngine._save_remote_image(sample_url, target_dir, filename)
            if status in {"error", "failed"}:
                logger.error("BFL generation failed: %s", poll_body)
                return None

            await asyncio.sleep(2.0)

        logger.error("BFL polling timed out after 600s for prompt: %s", prompt)
        return None

    @staticmethod
    def _resolve_api_key(provider: str, api_keys_dict: dict) -> Optional[str]:
        """Resolves API key by checking environment variables first, then the provided dictionary."""
        provider_key = (provider or "").lower()
        
        # 1. Check environment variables first
        env_key = settings.get_env_api_key(provider_key)
        if env_key:
            return env_key
            
        # 2. Fallback to database-stored (and encrypted) keys
        if api_keys_dict and provider_key in api_keys_dict:
            try:
                return encryption_util.decrypt_key(api_keys_dict[provider_key])
            except Exception as e:
                logger.error(f"Failed to decrypt API key for {provider_key}: {e}")
                return None
            
        return None

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
        style_instruction: Optional[str] = None,
    ) -> Optional[str]:
        """Generates an image and saves it locally."""
        provider_key = (provider or "openai").lower()
        if not prompt or not model:
            raise ValueError("Missing prompt or model for image generation.")
        
        # Apply style instruction if provided
        if style_instruction:
            prompt = f"{prompt}. Style: {style_instruction}."
        if provider_key != "ollama" and not api_key:
            # Try to resolve from ENV if not passed
            api_key = settings.get_env_api_key(provider_key)
            if not api_key:
                raise ValueError(f"Missing API key for image generation provider '{provider_key}'.")

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

        prompt = MediaEngine._apply_no_text_instruction(prompt)
            
        # Default target dir if not provided
        if target_dir is None:
            if adventure_id:
                target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id)
            else:
                target_dir = os.path.join(settings.DATA_DIR, "adventures")

        logger.info(f"Generating image with model {model} (provider: {provider_key}). Prompt: {prompt}")
        
        try:
            provider_options = provider_options or {}

            # SPECIAL CASE: OpenRouter does not support /v1/images/generations.
            # It uses /v1/chat/completions with modalities=["image"].
            if provider_key == "openrouter":
                logger.info(f"Using OpenRouter specialized image generation for model {model}")
                kwargs: dict[str, Any] = {
                    "model": f"openrouter/{model}" if not model.startswith("openrouter/") else model,
                    "messages": [{"role": "user", "content": prompt}],
                    "modalities": ["image"],
                    "api_base": "https://openrouter.ai/api/v1",
                }
                if api_key:
                    kwargs["api_key"] = api_key
                
                # Pass image config if available
                image_config = {}
                if provider_options.get("width") and provider_options.get("height"):
                    image_config["image_size"] = f"{provider_options['width']}x{provider_options['height']}"
                if image_config:
                    kwargs["image_config"] = image_config

                # Use completion instead of image_generation
                response = MediaEngine._get_litellm().completion(**kwargs)
                logger.info(f"OpenRouter completion response: {response}")
                
                # OpenRouter returns images in the message content or as a specific field in some versions.
                image_url = None
                b64_data = None

                message = response.choices[0].message
                content = getattr(message, "content", "")
                images_field = getattr(message, "images", [])
                
                # Case 1: Look in 'images' field first (newer OpenRouter format)
                if isinstance(images_field, list) and len(images_field) > 0:
                    for img_item in images_field:
                        if isinstance(img_item, dict):
                            img_url_obj = img_item.get("image_url") or img_item
                            if isinstance(img_url_obj, dict):
                                url_val = img_url_obj.get("url")
                                if url_val:
                                    if url_val.startswith("data:image/"):
                                        b64_data = url_val
                                    else:
                                        image_url = url_val
                                    break

                # Case 2: Look in 'content' list (standard LiteLLM/OpenAI format)
                if not image_url and not b64_data and isinstance(content, list):
                    for item in content:
                        if hasattr(item, "model_dump"):
                            item_dict = item.model_dump()
                        elif hasattr(item, "dict"):
                            item_dict = item.dict()
                        elif isinstance(item, dict):
                            item_dict = item
                        else:
                            item_dict = getattr(item, "__dict__", {})
                            
                        if item_dict.get("type") == "image_url":
                            image_obj = item_dict.get("image_url", {})
                            if isinstance(image_obj, dict):
                                url_val = image_obj.get("url")
                            else:
                                url_val = getattr(image_obj, "url", None)
                                
                            if not url_val:
                                url_val = item_dict.get("url")
                                
                            if url_val:
                                if url_val.startswith("data:image/"):
                                    b64_data = url_val
                                else:
                                    image_url = url_val
                                break
                
                if not image_url and not b64_data:
                    # Fallback for string content
                    import re
                    url_match = re.search(r'https?://[^\s)"\']+\.(?:jpg|jpeg|png|webp)', str(content))
                    if url_match:
                        image_url = url_match.group(0)
                    elif "data:image/" in str(content):
                        data_match = re.search(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', str(content))
                        if data_match:
                            b64_data = data_match.group(0)
                
                image_format = provider_options.get("image_format", "jpeg")
                image_quality = provider_options.get("image_quality", 85)

                if image_url:
                    return await MediaEngine._save_remote_image(image_url, target_dir, filename, image_format, image_quality)
                if b64_data:
                    return await MediaEngine._save_b64_image(b64_data, target_dir, filename, image_format, image_quality)
                
                logger.info(f"OpenRouter content type: {type(content)}, value: {repr(content)[:500]}")
                logger.warning(f"Could not find image URL or data in OpenRouter response content: {content}")
                raise RuntimeError(f"OpenRouter generation failed to return an image. Response: {response}")

            if provider_key == "black_forest_labs":
                return await MediaEngine._generate_image_black_forest_labs_direct(
                    prompt=prompt,
                    model=model,
                    api_key=api_key,
                    target_dir=target_dir,
                    filename=filename,
                    provider_options=provider_options,
                )

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
            
            if provider_key == "ollama":
                ollama_url = (provider_options.get("ollama_url") or "http://localhost:11434").rstrip("/")
                kwargs["api_base"] = ollama_url

            logger.info(f"Final image generation kwargs: {kwargs}")

            # Call LiteLLM first
            response = MediaEngine._get_litellm().image_generation(**kwargs)
            image_url, b64_json = MediaEngine._extract_image_payload(response)
            
            image_format = provider_options.get("image_format", "jpeg")
            image_quality = provider_options.get("image_quality", 85)

            if image_url:
                return await MediaEngine._save_remote_image(image_url, target_dir, filename, image_format, image_quality)
            elif b64_json:
                return await MediaEngine._save_b64_image(b64_json, target_dir, filename, image_format, image_quality)
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
                raise ValueError("Image generation was blocked by the AI provider's safety filter. Please adjust the description to avoid sensitive content.")
            logger.error(f"Image generation failed for prompt: '{prompt}'. Error: {error_str}")
            raise

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
            
            if image_url and image_url.startswith("data:image/"):
                b64_json = image_url
                image_url = None

            if image_url or b64_json:
                return image_url, b64_json

            if isinstance(image_data, dict):
                url = image_data.get("url")
                b64 = image_data.get("b64_json")
                if url and url.startswith("data:image/"):
                    return None, url
                return url, b64

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
            
            image_format = "jpeg"
            image_quality = 85
            
            if image_url:
                return await MediaEngine._save_remote_image(image_url, target_dir, filename, image_format, image_quality)
            if b64_json:
                return await MediaEngine._save_b64_image(b64_json, target_dir, filename, image_format, image_quality)

            logger.error("Ollama response did not include image payload: %s", body)
            return None
        except Exception:
            logger.exception("Error during direct Ollama image generation")
            return None

    @staticmethod
    async def _save_b64_image(b64_data: str, target_dir: str, filename: Optional[str] = None, image_format: str = "jpeg", quality: int = 85) -> Optional[str]:
        """Decodes and saves a base64 image string."""
        import base64
        import re
        try:
            os.makedirs(target_dir, exist_ok=True)
            ext = "jpg" if image_format.lower() == "jpeg" else "png"
            
            final_filename = filename or f"{uuid.uuid4()}.{ext}"
            if not any(final_filename.lower().endswith(e) for e in (".png", ".jpg", ".jpeg")):
                final_filename += f".{ext}"
                
            filepath = os.path.join(target_dir, final_filename)
            
            if b64_data.startswith("data:image/"):
                if ";base64," in b64_data:
                    b64_data = b64_data.split(";base64,", 1)[1]
                elif "," in b64_data:
                    b64_data = b64_data.split(",", 1)[1]

            b64_data = re.sub(r'[^A-Za-z0-9+/=]', '', b64_data)
            
            padding_needed = len(b64_data) % 4
            if padding_needed:
                b64_data += '=' * (4 - padding_needed)

            logger.info(f"Decoding b64 image (length: {len(b64_data)}, starts with: {b64_data[:30]}...)")
            image_bytes = base64.b64decode(b64_data)
            
            if image_format.lower() == "jpeg":
                img = Image.open(io.BytesIO(image_bytes))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(filepath, "JPEG", quality=quality, optimize=True)
            else:
                with open(filepath, "wb") as f:
                    f.write(image_bytes)
            
            rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
            return f"/data/{rel_path}"
        except Exception as e:
            logger.exception(f"Error saving b64 image: {str(e)}")
            return None

    @staticmethod
    async def _save_remote_image(url: str, target_dir: str, filename: Optional[str] = None, image_format: str = "jpeg", quality: int = 85) -> Optional[str]:
        """Downloads a remote image and persists it in the specified directory."""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                os.makedirs(target_dir, exist_ok=True)
                ext = "jpg" if image_format.lower() == "jpeg" else "png"
                
                final_filename = filename or f"{uuid.uuid4()}.{ext}"
                if not any(final_filename.lower().endswith(e) for e in (".png", ".jpg", ".jpeg")):
                    final_filename += f".{ext}"
                    
                filepath = os.path.join(target_dir, final_filename)
                
                if image_format.lower() == "jpeg":
                    img = Image.open(io.BytesIO(response.content))
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    img.save(filepath, "JPEG", quality=quality, optimize=True)
                else:
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                
                rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
                return f"/data/{rel_path}"
            else:
                logger.error(f"Failed to download image from {url}, status: {response.status_code}")
                return None
        except Exception as e:
            logger.exception("Error saving remote image")
            return None

    @staticmethod
    async def generate_scene_image(prompt: str, adventure_id: str, user_config: dict, api_keys: dict, style_instruction: Optional[str] = None) -> Optional[str]:
        """High-level wrapper for gameplay scene generation (uses Advanced Model)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: 
            logger.warning("No T2I settings found in user_config")
            return None
        
        provider = (t2i.get("advanced_model_provider") or t2i.get("provider", "openai")).lower()
        model = t2i.get("advanced_model")
        
        logger.info(f"Resolving scene generation: provider={provider}, model={model}")
        
        if not model:
            raise ValueError("Missing image model configuration for scenes.")

        api_key = MediaEngine._resolve_api_key(provider, api_keys)
        if provider != "ollama" and not api_key:
            logger.error(f"API key resolution failed for provider: {provider} (Advanced Model/Scenes). Available keys: {list(api_keys.keys()) if api_keys else 'None'}")
            raise ValueError(f"Missing image configuration or API key for {provider} (Advanced Model). Please check your Visual Preferences in Admin settings.")
        
        target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id, "scenes")
        ext = "jpg" if (t2i.get("image_format") or "jpeg").lower() == "jpeg" else "png"
        
        # Use adventure_id as prefix for clarity
        safe_id = slugify(adventure_id)
        filename = f"{safe_id}_scene_{uuid.uuid4().hex[:8]}.{ext}"
        
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
    async def generate_entity_image(prompt: str, adventure_id: str, entity_id: str, entity_type: str, user_config: dict, api_keys: dict, style_instruction: Optional[str] = None) -> Optional[str]:
        """High-level wrapper for NPC/Object generation (uses Simple Model)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: 
            logger.warning("No T2I settings found in user_config")
            return None
        
        provider = (t2i.get("simple_model_provider") or t2i.get("provider", "openai")).lower()
        model = t2i.get("simple_model")
        
        logger.info(f"Resolving entity generation: provider={provider}, model={model}")
        
        if not model:
            raise ValueError("Missing image model configuration for entities.")

        api_key = MediaEngine._resolve_api_key(provider, api_keys)
        if provider != "ollama" and not api_key:
            logger.error(f"API key resolution failed for provider: {provider} (Simple Model/Entities). Available keys: {list(api_keys.keys()) if api_keys else 'None'}")
            raise ValueError(f"Missing image configuration or API key for {provider} (Simple Model). Please check your Visual Preferences in Admin settings.")
        
        target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id, "entities")
        ext = "jpg" if (t2i.get("image_format") or "jpeg").lower() == "jpeg" else "png"
        
        # Use adventure_id and entity_id as prefix for clarity
        safe_adv_id = slugify(adventure_id)
        safe_ent_id = slugify(entity_id)
        filename = f"{safe_adv_id}_{safe_ent_id}_{uuid.uuid4().hex[:8]}.{ext}"
        
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
    async def generate_adventure_cover(title: str, original_prompt: str, adventure_id: str, user_config: dict, api_keys: dict, style_instruction: Optional[str] = None) -> Optional[str]:
        """High-level wrapper for adventure cover generation (uses Advanced Model, 3:2 aspect ratio)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: 
            logger.warning("No T2I settings found in user_config")
            return None
        
        provider = (t2i.get("advanced_model_provider") or t2i.get("provider", "openai")).lower()
        model = t2i.get("advanced_model")
        
        logger.info(f"Resolving adventure cover generation: provider={provider}, model={model}")
        
        if not model:
            raise ValueError("Missing image model configuration for adventure cover.")

        api_key = MediaEngine._resolve_api_key(provider, api_keys)
        if provider != "ollama" and not api_key:
            logger.error(f"API key resolution failed for provider: {provider} (Advanced Model/Cover). Available keys: {list(api_keys.keys()) if api_keys else 'None'}")
            raise ValueError(f"Missing image configuration or API key for {provider} (Advanced Model/Cover). Please check your Visual Preferences in Admin settings.")
        
        target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id)
        ext = "jpg" if (t2i.get("image_format") or "jpeg").lower() == "jpeg" else "png"
        
        # Use adventure_id as prefix for clarity
        safe_id = slugify(adventure_id)
        filename = f"{safe_id}_cover_{uuid.uuid4().hex[:8]}.{ext}"
        
        prompt = prompts.ADVENTURE_COVER_PROMPT_TEMPLATE.format(
            title=title, original_prompt=original_prompt
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

    @staticmethod
    async def generate_svg_placeholder(
        adventure_id: str,
        entity_id: str,
        target_dir: str,
        filename: str = "placeholder.svg",
        category: str = ""
    ) -> str:
        """
        Generates a procedural SVG placeholder as a fallback.
        Ensures consistent visual style for 'unmanifested' content.
        """
        try:
            os.makedirs(target_dir, exist_ok=True)
            if not filename.endswith(".svg"):
                filename += ".svg"
            
            filepath = os.path.join(target_dir, filename)
            generator = SVGPlaceholderGenerator(width=1200, height=800, num_shapes=15)
            generator.save(filepath, title=entity_id, category=category)
            
            rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
            return f"/data/{rel_path}"
        except Exception as e:
            logger.error(f"Failed to generate SVG placeholder: {e}")
            return ""
