"""
MediaEngine — Handles AI image generation for scenes and entities.
Integrated with LiteLLM to support OpenAI (DALL-E), OpenRouter, and Google (Imagen), while using the direct BFL API for Black Forest Labs.
"""
import asyncio
import base64
import io
import logging
import os
import re
import shutil
import time
import uuid
from urllib.parse import urlsplit, urlunsplit
from typing import Any

import litellm
import requests
from PIL import Image

from backend.core import prompts
from backend.core.config import settings
from backend.core.security import encryption_util
from backend.utils.image_generator import (
    ColorTheme,
    OrganicGradientStrategy,
    PlaceholderImageGenerator,
)
from backend.utils.svg_generator import SVGPlaceholderGenerator
from backend.utils.text_utils import slugify

logger = logging.getLogger(__name__)

BFL_DEFAULT_MODEL = "black_forest_labs/flux-pro-1.1"
BFL_API_BASE = "https://api.bfl.ai/v1"
# Use centralized prompts
NO_TEXT_IMAGE_PROMPT_SUFFIX = prompts.NO_TEXT_IMAGE_PROMPT_SUFFIX


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _ensure_within_data_dir(path: str) -> str:
    """Validate that a path resolves inside DATA_DIR and return its absolute form."""
    data_root = os.path.abspath(settings.DATA_DIR)
    resolved = os.path.abspath(path)
    try:
        if os.path.commonpath([resolved, data_root]) != data_root:
            raise ValueError("Resolved path escapes DATA_DIR.")
    except ValueError as exc:
        raise ValueError("Invalid path: cannot resolve against DATA_DIR.") from exc
    return resolved


def _safe_data_path(*parts: str) -> str:
    """Build a safe path under DATA_DIR."""
    return _ensure_within_data_dir(os.path.join(settings.DATA_DIR, *parts))


def _normalize_output_filename(filename: str | None, extension: str) -> str:
    """Return a sanitized output filename with a safe image extension."""
    ext = "jpg" if extension.lower() == "jpeg" else extension.lower()
    candidate = (filename or "").strip()
    if not candidate:
        return f"{uuid.uuid4()}.{ext}"

    # Keep only the final segment to prevent directory traversal.
    candidate = os.path.basename(candidate)
    stem, original_ext = os.path.splitext(candidate)
    stem = _SAFE_FILENAME_RE.sub("_", stem).strip("._")
    if not stem:
        stem = str(uuid.uuid4())

    normalized_ext = original_ext.lower().lstrip(".")
    if normalized_ext not in {"png", "jpg", "jpeg"}:
        normalized_ext = ext
    return f"{stem}.{normalized_ext}"


def _resolve_output_dir(target_dir: str) -> str:
    """Resolve an output directory to a validated location inside DATA_DIR."""
    candidate = str(target_dir or "").strip()
    if not candidate:
        raise ValueError("Target directory is required.")
    if os.path.isabs(candidate):
        return _ensure_within_data_dir(candidate)

    parts = [part for part in re.split(r"[\\/]+", candidate) if part and part not in {".", ".."}]
    if not parts:
        raise ValueError("Invalid target directory.")
    return _safe_data_path(*parts)


def _build_output_filepath(target_dir: str, filename: str | None, extension: str) -> str:
    """Build a validated output file path inside DATA_DIR."""
    resolved_dir = _resolve_output_dir(target_dir)
    os.makedirs(resolved_dir, exist_ok=True)
    safe_filename = _normalize_output_filename(filename, extension)
    return _ensure_within_data_dir(os.path.join(resolved_dir, safe_filename))


def _redact_url_for_logs(url: str) -> str:
    """Redact URL query/fragment so signed tokens are not logged."""
    try:
        parts = urlsplit(url or "")
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except ValueError:
        return "<invalid-url>"


def _safe_prompt_summary(prompt: str) -> str:
    """Return a non-sensitive summary of a prompt for logging."""
    return f"len={len(prompt or '')}"


def _sanitize_generation_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Return generation kwargs safe for logs."""
    sanitized = dict(kwargs)
    if "api_key" in sanitized:
        sanitized["api_key"] = "<redacted>"
    if "prompt" in sanitized:
        sanitized["prompt"] = _safe_prompt_summary(str(sanitized.get("prompt") or ""))
    if "messages" in sanitized:
        sanitized["messages"] = "<redacted>"
    return sanitized


class MediaEngine:
    @staticmethod
    async def cleanup_adventure_assets(adventure_id: str):
        """Removes all generated assets for an adventure from disk."""
        target_dir = _safe_data_path("adventures", "library", adventure_id)
        if os.path.exists(target_dir):
            try:
                # Use a thread pool executor for blocking I/O if needed, 
                # but for simplicity we'll just use shutil in this async context.
                shutil.rmtree(target_dir)
                logger.info("Cleaned up assets for adventure %s", adventure_id)
            except OSError as e:
                logger.error("Failed to cleanup assets for adventure %s: %s", adventure_id, e)


    @classmethod
    def _get_litellm(cls) -> Any:
        return litellm

    @staticmethod
    def _sanitize_prompt(prompt: str) -> str:
        """Corrects common typos that trigger safety filters (e.g. 'raping' -> 'rapping')."""
        # Case-insensitive replacement of 'raping' with 'rapping', but only if preceded by 'rap', 'battle', etc.
        # or as a standalone word that is clearly a typo in this context.
        # Actually, in a TTRPG/Creative context, 'raping' is almost always a typo for 'rapping'.
        return re.sub(r'(\b)raping(\b)', r'\1rapping\2', prompt, flags=re.IGNORECASE)

    @staticmethod
    def _apply_no_text_instruction(prompt: str) -> str:
        """Append a global no-text instruction to image prompts when missing."""
        prompt = prompt.strip()
        # Remove trailing dots to avoid double dots when appending suffix
        while prompt.endswith("."):
            prompt = prompt[:-1].strip()

        normalized = MediaEngine._sanitize_prompt(prompt)
        if prompts.NO_TEXT_IMAGE_PROMPT_SUFFIX.lower() in normalized.lower():
            return normalized
        # Combine instructions for better enforcement
        return f"{normalized}. {prompts.NO_TEXT_IMAGE_PROMPT_SUFFIX}"

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
        filename: str | None = None,
        provider_options: dict[str, Any | None] = None,
    ) -> str | None:
        """Generate a BFL image by calling the REST API directly and polling for completion."""
        provider_options = provider_options or {}
        model_slug = MediaEngine._normalize_black_forest_labs_model(model)
        endpoint = f"{BFL_API_BASE}/{model_slug}"

        payload: dict[str, Any] = {"prompt": prompt[:1500]}
        logger.info("BFL submission payload prepared (prompt_%s)", _safe_prompt_summary(prompt))
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

        response = await asyncio.to_thread(
            requests.post,
            endpoint,
            headers={"Content-Type": "application/json", "x-key": api_key},
            json=payload,
            timeout=settings.VISUAL_TIMEOUT,
        )
        if response.status_code != 200:
            logger.error("BFL image generation submit failed. status=%s", response.status_code)
            return None

        body = response.json()
        polling_url = body.get("polling_url")
        if not polling_url:
            logger.error("BFL response did not include polling_url")
            return None

        poll_deadline = time.monotonic() + 600.0
        while time.monotonic() < poll_deadline:
            poll_response = await asyncio.to_thread(
                requests.get,
                polling_url,
                headers={"accept": "application/json", "x-key": api_key},
                timeout=max(30, settings.VISUAL_TIMEOUT),
            )
            if poll_response.status_code != 200:
                logger.error(
                    "BFL polling failed. status=%s",
                    poll_response.status_code,
                )
                return None

            poll_body = poll_response.json()
            status = str(poll_body.get("status") or "").lower()
            logger.info("BFL polling status: %s", status)
            if status == "ready":
                result = poll_body.get("result") or {}
                sample_url = result.get("sample")
                if not sample_url:
                    logger.error("BFL polling response missing result.sample")
                    return None
                return await MediaEngine._save_remote_image(sample_url, target_dir, filename)
            
            if "moderated" in status:
                logger.warning("BFL generation moderated")
                raise ValueError(f"BFL Image Generation blocked by safety filter: {status}")

            if status in {"error", "failed", "expired", "task not found", "tasknotfound"}:
                logger.error("BFL generation failed, expired or not found")
                return None

            await asyncio.sleep(2.0)

        logger.error("BFL polling timed out after 600s")
        return None

    @staticmethod
    def _resolve_api_key(provider: str, api_keys_dict: dict) -> str | None:
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
            except (ValueError, TypeError, KeyError):
                logger.error("Failed to decrypt API key for provider '%s'", provider_key)
                return None
            
        return None

    @staticmethod
    async def generate_image(
        prompt: str, 
        model: str, 
        api_key: str | None, 
        provider: str = "openai",
        adventure_id: str | None = None,
        target_dir: str | None = None,
        filename: str | None = None,
        provider_options: dict[str, Any | None] = None,
        style_instruction: str | None = None,
    ) -> str | None:
        """Generates an image and saves it locally."""
        provider_key = (provider or "openai").lower()
        if not prompt or not model:
            raise ValueError("Missing prompt or model for image generation.")
        
        # Inject style instruction if provided
        if style_instruction:
            # Ensure we don't have multiple dots
            prompt = prompt.strip()
            while prompt.endswith("."):
                prompt = prompt[:-1].strip()
            prompt += f". Style: {style_instruction}."
            logger.info("Style instruction injected")

        prompt = MediaEngine._apply_no_text_instruction(prompt)
        logger.info("Image prompt prepared (%s)", _safe_prompt_summary(prompt))

        if provider_key != "ollama" and not api_key:
            # Try to resolve from ENV if not passed
            api_key = settings.get_env_api_key(provider_key)
            if not api_key:
                raise ValueError(f"Missing API key for image generation provider '{provider_key}'.")

        if provider_key == "ollama":
            logger.info("Generating image with local Ollama (%s)", _safe_prompt_summary(prompt))
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

        # Default target dir if not provided
        if target_dir is None:
            if adventure_id:
                target_dir = _safe_data_path("adventures", "library", adventure_id)
            else:
                target_dir = _safe_data_path("adventures", "library")
        else:
            target_dir = _resolve_output_dir(target_dir)

        logger.info(
            "Generating image with model %s (provider: %s, prompt_%s)",
            model,
            provider_key,
            _safe_prompt_summary(prompt),
        )
        
        try:
            provider_options = provider_options or {}

            # SPECIAL CASE: OpenRouter does not support /v1/images/generations.
            # It uses /v1/chat/completions with modalities=["image"].
            if provider_key == "openrouter":
                logger.info("Using OpenRouter specialized image generation for model %s", model)
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
                logger.info("OpenRouter completion finished")
                
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
                
                logger.info("OpenRouter response content type: %s", type(content).__name__)
                logger.warning("Could not find image URL or image data in OpenRouter response")
                raise RuntimeError("OpenRouter generation failed to return an image.")

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

            logger.info("Final image generation kwargs: %s", _sanitize_generation_kwargs(kwargs))

            # Call LiteLLM first - wrap in to_thread because LiteLLM image_generation is synchronous
            response = await asyncio.to_thread(
                MediaEngine._get_litellm().image_generation,
                **kwargs, 
                request_timeout=settings.VISUAL_TIMEOUT
            )
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
                logger.error("No image data in provider response")
                return None

        except Exception as e:
            error_str = str(e)
            if provider_key == "ollama":
                logger.warning("LiteLLM ollama path failed; trying direct Ollama API fallback.")
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
                ) from e
            err_lower = error_str.lower()
            if "content moderated" in err_lower or "safety filter" in err_lower or "moderated" in err_lower:
                logger.warning("Image generation was moderated (Safety Filter).")
                raise ValueError(
                    "Image generation was blocked by the AI provider's safety filter. "
                    "Please adjust the description to avoid sensitive content."
                ) from e
            logger.error("Image generation failed (%s)", type(e).__name__)
            raise

    @staticmethod
    def _extract_image_payload(response: Any) -> tuple[str | None, str | None]:
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
        filename: str | None = None,
        width: int | None = None,
        height: int | None = None,
        steps: int | None = None,
        seed: int | None = None,
        negative_prompt: str | None = None,
    ) -> str | None:
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

            response = await asyncio.to_thread(requests.post, endpoint, json=payload, timeout=120)
            if response.status_code != 200:
                logger.error(
                    "Ollama direct image generation failed. status=%s",
                    response.status_code,
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

            logger.error("Ollama response did not include image payload")
            return None
        except (requests.RequestException, OSError, TypeError, ValueError):
            logger.exception("Error during direct Ollama image generation")
            return None

    @staticmethod
    async def _save_b64_image(b64_data: str, target_dir: str, filename: str | None = None, image_format: str = "jpeg", quality: int = 85) -> str | None:
        """Decodes and saves a base64 image string."""
        try:
            ext = "jpg" if image_format.lower() == "jpeg" else "png"
            filepath = _build_output_filepath(target_dir, filename, ext)
            
            if b64_data.startswith("data:image/"):
                if ";base64," in b64_data:
                    b64_data = b64_data.split(";base64,", 1)[1]
                elif "," in b64_data:
                    b64_data = b64_data.split(",", 1)[1]

            b64_data = re.sub(r'[^A-Za-z0-9+/=]', '', b64_data)
            
            padding_needed = len(b64_data) % 4
            if padding_needed:
                b64_data += '=' * (4 - padding_needed)

            logger.info("Decoding base64 image payload (length=%d)", len(b64_data))
            image_bytes = base64.b64decode(b64_data)
            
            if image_format.lower() == "jpeg":
                img = Image.open(io.BytesIO(image_bytes))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                # Image.save is CPU bound, wrap in to_thread
                await asyncio.to_thread(img.save, filepath, "JPEG", quality=quality, optimize=True)
            else:
                with open(filepath, "wb") as f:
                    f.write(image_bytes)
            
            rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
            return f"/data/{rel_path}"
        except (ValueError, OSError, TypeError):
            logger.exception("Error saving b64 image")
            return None

    @staticmethod
    async def _save_remote_image(url: str, target_dir: str, filename: str | None = None, image_format: str = "jpeg", quality: int = 85) -> str | None:
        """Downloads a remote image and persists it in the specified directory."""
        try:
            response = await asyncio.to_thread(requests.get, url, timeout=30)
            if response.status_code == 200:
                ext = "jpg" if image_format.lower() == "jpeg" else "png"
                filepath = _build_output_filepath(target_dir, filename, ext)
                
                if image_format.lower() == "jpeg":
                    img = Image.open(io.BytesIO(response.content))
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    # Image.save is CPU bound, wrap in to_thread
                    await asyncio.to_thread(img.save, filepath, "JPEG", quality=quality, optimize=True)
                else:
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                
                rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
                return f"/data/{rel_path}"
            else:
                logger.error(
                    "Failed to download image from %s, status: %s",
                    _redact_url_for_logs(url),
                    response.status_code,
                )
                return None
        except (requests.RequestException, OSError, ValueError):
            logger.exception("Error saving remote image")
            return None

    @staticmethod
    async def generate_scene_image(prompt: str, adventure_id: str, user_config: dict, api_keys: dict, style_instruction: str | None = None, use_advanced_model: bool = True) -> str | None:
        """High-level wrapper for gameplay scene generation (uses Advanced Model by default)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: 
            logger.warning("No T2I settings found in user_config")
            return None
        
        if use_advanced_model:
            provider = (t2i.get("advanced_model_provider") or t2i.get("provider", "openai")).lower()
            model = t2i.get("advanced_model")
        else:
            provider = (t2i.get("simple_model_provider") or t2i.get("provider", "openai")).lower()
            model = t2i.get("simple_model")
        
        logger.info("Resolving scene generation: provider=%s, model=%s", provider, model)
        
        if not model:
            raise ValueError("Missing image model configuration for scenes.")

        api_key = MediaEngine._resolve_api_key(provider, api_keys)
        if provider != "ollama" and not api_key:
            logger.error("API key resolution failed for provider: %s (Advanced Model/Scenes)", provider)
            raise ValueError(f"Missing image configuration or API key for {provider} (Advanced Model). Please check your Visual Preferences in Admin settings.")
        
        target_dir = _safe_data_path("adventures", "library", adventure_id, "scenes")
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
            style_instruction=style_instruction,
        )

    @staticmethod
    async def generate_entity_image(prompt: str, adventure_id: str, entity_id: str, entity_type: str, user_config: dict, api_keys: dict, style_instruction: str | None = None, use_advanced_model: bool = False) -> str | None:
        """High-level wrapper for NPC/Object generation (uses Simple Model by default)."""
        _ = entity_type
        t2i = user_config.get("t2i_settings")
        if not t2i: 
            logger.warning("No T2I settings found in user_config")
            return None
        
        if use_advanced_model:
            provider = (t2i.get("advanced_model_provider") or t2i.get("provider", "openai")).lower()
            model = t2i.get("advanced_model")
        else:
            provider = (t2i.get("simple_model_provider") or t2i.get("provider", "openai")).lower()
            model = t2i.get("simple_model")
        
        logger.info("Resolving entity generation: provider=%s, model=%s", provider, model)
        
        if not model:
            raise ValueError("Missing image model configuration for entities.")

        api_key = MediaEngine._resolve_api_key(provider, api_keys)
        if provider != "ollama" and not api_key:
            logger.error("API key resolution failed for provider: %s (Simple Model/Entities)", provider)
            raise ValueError(f"Missing image configuration or API key for {provider} (Simple Model). Please check your Visual Preferences in Admin settings.")
        
        target_dir = _safe_data_path("adventures", "library", adventure_id, "entities")
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
            style_instruction=style_instruction,
        )

    @staticmethod
    async def generate_adventure_cover(title: str, original_prompt: str, adventure_id: str, user_config: dict, api_keys: dict, style_instruction: str | None = None) -> str | None:
        """High-level wrapper for adventure cover generation (uses Advanced Model, 3:2 aspect ratio)."""
        t2i = user_config.get("t2i_settings")
        if not t2i: 
            logger.warning("No T2I settings found in user_config")
            return None
        
        provider = (t2i.get("advanced_model_provider") or t2i.get("provider", "openai")).lower()
        model = t2i.get("advanced_model")
        
        logger.info("Resolving adventure cover generation: provider=%s, model=%s", provider, model)
        
        if not model:
            raise ValueError("Missing image model configuration for adventure cover.")

        api_key = MediaEngine._resolve_api_key(provider, api_keys)
        if provider != "ollama" and not api_key:
            logger.error("API key resolution failed for provider: %s (Advanced Model/Cover)", provider)
            raise ValueError(f"Missing image configuration or API key for {provider} (Advanced Model/Cover). Please check your Visual Preferences in Admin settings.")
        
        target_dir = _safe_data_path("adventures", "library", adventure_id)
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
            style_instruction=style_instruction,
        )

    @staticmethod
    async def generate_placeholder(
        adventure_id: str,
        entity_id: str,
        target_dir: str,
        filename: str | None = None,
        category: str = "",
        theme: str | None = None
    ) -> str:
        """
        Generates a high-quality PIL-based placeholder image.
        Uses organic gradients for scenes and blob-icons for entities.
        """
        try:
            target_dir = _ensure_within_data_dir(target_dir)
            os.makedirs(target_dir, exist_ok=True)
            
            # Determine format and extension
            # Default to PNG for placeholders to preserve transparency if needed, 
            # though we currently convert to RGB in the strategy.
            ext = "png"
            if filename:
                if filename.lower().endswith((".jpg", ".jpeg")):
                    ext = "jpg"
                elif filename.lower().endswith(".png"):
                    ext = "png"
            
            if not filename:
                filename = f"placeholder_{entity_id}_{uuid.uuid4().hex[:6]}.{ext}"
            filename = _normalize_output_filename(filename, ext)
            
            filepath = _ensure_within_data_dir(os.path.join(target_dir, filename))
            
            # Select strategy and theme based on category
            cat = category.upper()
            
            # Map theme string to ColorTheme enum
            color_theme = ColorTheme.COLORFUL
            if theme:
                try:
                    color_theme = ColorTheme[theme.upper()]
                except (KeyError, AttributeError):
                    pass
            
            if cat in ["SCENE", "COVER", "LANDSCAPE"]:
                # Scenes use random generation with subtle blur
                strategy = OrganicGradientStrategy(theme=color_theme)
                width, height = 1200, 800
            elif cat in ["NPC", "CHARACTER", "ITEM", "AVATAR"]:
                # NPCs, Items, and Avatars (Protagonist) use the classic SVG system with margins
                return await MediaEngine.generate_svg_placeholder(adventure_id, entity_id, target_dir, filename, category)
            else:
                strategy = OrganicGradientStrategy(theme=color_theme)
                width, height = 800, 600

            generator = PlaceholderImageGenerator(strategy=strategy)
            
            # Run in thread pool as PIL operations are blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                generator.create_and_save, 
                filepath, 
                (width, height)
            )
            
            rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
            return f"/data/{rel_path}"
        except (OSError, ValueError, TypeError) as e:
            logger.error("Failed to generate high-quality placeholder: %s", e)
            # Fallback to SVG if PIL fails
            return await MediaEngine.generate_svg_placeholder(adventure_id, entity_id, target_dir, filename, category)

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
        _ = adventure_id
        try:
            target_dir = _ensure_within_data_dir(target_dir)
            os.makedirs(target_dir, exist_ok=True)
            filename = os.path.basename(filename)
            if not filename.endswith(".svg"):
                filename += ".svg"
            
            filepath = _ensure_within_data_dir(os.path.join(target_dir, filename))
            generator = SVGPlaceholderGenerator(width=1200, height=800, num_shapes=15)
            generator.save(filepath, title=entity_id, category=category)
            
            rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
            return f"/data/{rel_path}"
        except (OSError, ValueError, TypeError) as e:
            logger.error("Failed to generate SVG placeholder: %s", e)
            return ""

