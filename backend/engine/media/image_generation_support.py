"""Provider-agnostic helpers for MediaEngine image generation.

Pure request building and response parsing for the image providers (OpenRouter,
Black Forest Labs, Ollama, Stable Diffusion, LiteLLM), kept out of
``media_engine`` so the engine methods stay small orchestration steps.
"""

import asyncio
import contextlib
import logging
import re
import time
from typing import Any, Optional

import requests

from backend.core.config import settings
from backend.utils.image_generator import ColorTheme

logger = logging.getLogger(__name__)

OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"
BFL_POLL_TIMEOUT_SECONDS = 600.0

_REMOTE_MODEL_PREFIXES = (
    "openai/",
    "openrouter/",
    "anthropic/",
    "google/",
    "gemini/",
    "azure/",
    "bedrock/",
    "cohere/",
)
_LOCAL_PROVIDERS = ("ollama", "stable_diffusion")
_BFL_FAILED_STATUSES = {"error", "failed", "expired", "task not found", "tasknotfound"}
_MODERATION_MARKERS = ("content moderated", "safety filter", "moderated")


# --- Prompt / request preparation -----------------------------------------------------


def inject_style_instruction(prompt: str, style_instruction: Optional[str]) -> str:
    """Append a style instruction to the prompt without doubling trailing dots."""
    if not style_instruction:
        return prompt
    prompt = prompt.strip()
    while prompt.endswith("."):
        prompt = prompt[:-1].strip()
    logger.info("Style instruction injected")
    return f"{prompt}. Style: {style_instruction}."


def resolve_required_api_key(provider_key: str, api_key: Optional[str]) -> Optional[str]:
    """Remote providers need a key; fall back to the environment, else fail."""
    if provider_key in _LOCAL_PROVIDERS or api_key:
        return api_key
    # Try to resolve from ENV if not passed
    env_key = settings.get_env_api_key(provider_key)
    if not env_key:
        raise ValueError(f"Missing API key for image generation provider '{provider_key}'.")
    return env_key


def ensure_local_ollama_model(model: str) -> None:
    if model.startswith(_REMOTE_MODEL_PREFIXES):
        raise ValueError(
            f"Provider is 'ollama' but image model '{model}' looks like a remote/cloud model. "
            "Configure a local Ollama image model (for example: x/flux2-klein)."
        )


def is_moderation_error(error_str: str) -> bool:
    err_lower = error_str.lower()
    return any(marker in err_lower for marker in _MODERATION_MARKERS)


def _set_if_not_none(target: dict[str, Any], values: dict[str, Any]) -> None:
    for key, value in values.items():
        if value is not None:
            target[key] = value


def _set_if_truthy(target: dict[str, Any], values: dict[str, Any]) -> None:
    for key, value in values.items():
        if value:
            target[key] = value


def build_litellm_image_kwargs(
    prompt: str,
    model: str,
    provider_key: str,
    api_key: Optional[str],
    provider_options: dict[str, Any],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "prompt": prompt,
        "model": model,
        "custom_llm_provider": provider_key,
    }
    if api_key:
        kwargs["api_key"] = api_key

    # Pass common optional generation controls through when available.
    optional_fields = ("width", "height", "steps", "seed", "negative_prompt")
    _set_if_not_none(kwargs, {field: provider_options.get(field) for field in optional_fields})

    if provider_key == "ollama":
        kwargs["api_base"] = (
            provider_options.get("ollama_url") or "http://localhost:11434"
        ).rstrip("/")
    return kwargs


def build_ollama_request(
    ollama_url: str,
    model: str,
    prompt: str,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    steps: Optional[int] = None,
    seed: Optional[int] = None,
    negative_prompt: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    """Return (endpoint, payload) for Ollama's /api/generate."""
    base = ollama_url.rstrip("/")
    if not base.endswith("/api"):
        base = f"{base}/api"

    options: dict[str, Any] = {}
    _set_if_not_none(options, {"width": width, "height": height, "steps": steps, "seed": seed})
    _set_if_truthy(options, {"negative_prompt": negative_prompt})

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if options:
        payload["options"] = options
    return f"{base}/generate", payload


def build_stable_diffusion_payload(
    prompt: str,
    model: str,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    steps: Optional[int] = None,
    cfg_scale: Optional[float] = None,
    seed: Optional[int] = None,
    negative_prompt: Optional[str] = None,
    sampler_name: Optional[str] = None,
    scheduler: Optional[str] = None,
) -> dict[str, Any]:
    """Return the txt2img payload for the Stable Diffusion WebUI API."""
    payload: dict[str, Any] = {
        "prompt": prompt,
    }
    _set_if_not_none(
        payload,
        {"width": width, "height": height, "steps": steps, "cfg_scale": cfg_scale, "seed": seed},
    )
    _set_if_truthy(
        payload,
        {"negative_prompt": negative_prompt, "sampler_name": sampler_name, "scheduler": scheduler},
    )
    if model and model != "default":
        payload["override_settings"] = {"sd_model_checkpoint": model}
    return payload


# --- Response parsing ---------------------------------------------------------------


def split_data_url(url_val: str) -> tuple[Optional[str], Optional[str]]:
    """Return (remote_url, None) or (None, data_url) depending on the URL scheme."""
    if url_val.startswith("data:image/"):
        return None, url_val
    return url_val, None


def _payload_from_data_item(image_data: Any) -> Optional[tuple[Optional[str], Optional[str]]]:
    if isinstance(image_data, dict):
        url = image_data.get("url")
        b64 = image_data.get("b64_json")
        if url and url.startswith("data:image/"):
            return None, url
        return url, b64

    image_url = getattr(image_data, "url", None)
    b64_json = getattr(image_data, "b64_json", None)
    if image_url and image_url.startswith("data:image/"):
        return None, image_url
    if image_url or b64_json:
        return image_url, b64_json
    return None


def _payload_from_dict_response(response: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    images = response.get("images")
    if isinstance(images, list) and images and isinstance(images[0], str):
        return None, images[0]
    return response.get("url"), response.get("b64_json")


def extract_image_payload(response: Any) -> tuple[Optional[str], Optional[str]]:
    """Extract URL or base64 image payload from provider responses."""
    if not response:
        return None, None

    data = getattr(response, "data", None)
    if isinstance(data, list) and data:
        return _payload_from_data_item(data[0]) or (None, None)

    if isinstance(response, dict):
        return _payload_from_dict_response(response)
    return None, None


def _item_as_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "dict"):
        return item.dict()
    if isinstance(item, dict):
        return item
    return getattr(item, "__dict__", {})


def _url_from_images_field(images_field: Any) -> Optional[str]:
    if not isinstance(images_field, list):
        return None
    for img_item in images_field:
        if not isinstance(img_item, dict):
            continue
        img_url_obj = img_item.get("image_url") or img_item
        if isinstance(img_url_obj, dict) and img_url_obj.get("url"):
            return img_url_obj["url"]
    return None


def _url_from_content_item(item: Any) -> Optional[str]:
    item_dict = _item_as_dict(item)
    if item_dict.get("type") != "image_url":
        return None
    image_obj = item_dict.get("image_url", {})
    if isinstance(image_obj, dict):
        url_val = image_obj.get("url")
    else:
        url_val = getattr(image_obj, "url", None)
    return url_val or item_dict.get("url")


def _url_from_content_list(content: Any) -> Optional[str]:
    if not isinstance(content, list):
        return None
    for item in content:
        url_val = _url_from_content_item(item)
        if url_val:
            return url_val
    return None


def _payload_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
    url_match = re.search(r'https?://[^\s)"\']+\.(?:jpg|jpeg|png|webp)', text)
    if url_match:
        return url_match.group(0), None
    if "data:image/" not in text:
        return None, None
    data_match = re.search(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", text)
    return None, data_match.group(0) if data_match else None


def extract_chat_image_payload(message: Any) -> tuple[Optional[str], Optional[str]]:
    """Find the generated image in a chat completion message (images, content parts, text)."""
    content = getattr(message, "content", "")
    images_field = getattr(message, "images", [])

    url_val = _url_from_images_field(images_field) or _url_from_content_list(content)
    if url_val:
        return split_data_url(url_val)
    return _payload_from_text(str(content))


def extract_openrouter_image(result: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Return (remote_url, b64_or_data_url) from an OpenRouter /images response."""
    data_list = result.get("data", [])
    if not data_list or not isinstance(data_list, list):
        logger.error("OpenRouter response missing 'data' list: %s", result)
        raise RuntimeError("OpenRouter response did not contain image data.")

    first_img = data_list[0]
    if isinstance(first_img, dict):
        b64_json = first_img.get("b64_json")
        if b64_json:
            return None, b64_json
        image_url = first_img.get("url")
        if image_url:
            return split_data_url(image_url)

    raise RuntimeError("No valid image data or URL found in OpenRouter response.")


# --- OpenRouter HTTP ----------------------------------------------------------------


def openrouter_headers(api_key: Optional[str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://taleweaver.local",
        "X-Title": "TaleWeaver",
    }


def build_openrouter_image_payload(
    clean_model: str, prompt: str, provider_options: dict[str, Any]
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": clean_model,
        "prompt": prompt,
    }
    width = provider_options.get("width")
    height = provider_options.get("height")
    if width and height:
        payload["size"] = f"{width}x{height}"
    elif provider_options.get("aspect_ratio"):
        payload["aspect_ratio"] = provider_options["aspect_ratio"]
    return payload


def build_openrouter_chat_kwargs(
    model: str, prompt: str, api_key: Optional[str], provider_options: dict[str, Any]
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": f"openrouter/{model}" if not model.startswith("openrouter/") else model,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image"],
        "api_base": "https://openrouter.ai/api/v1",
    }
    if api_key:
        kwargs["api_key"] = api_key
    if provider_options.get("width") and provider_options.get("height"):
        kwargs["image_config"] = {
            "image_size": f"{provider_options['width']}x{provider_options['height']}"
        }
    return kwargs


def is_chat_only_model_error(error_msg: str) -> bool:
    lowered = error_msg.lower()
    return "chat/completions" in lowered or "modalities" in lowered


def openrouter_error_message(response: Any) -> str:
    error_msg = f"HTTP {response.status_code}"
    try:
        err_data = response.json()
    except Exception:
        return response.text[:300]
    if not isinstance(err_data, dict) or "error" not in err_data:
        return error_msg
    err_obj = err_data["error"]
    if isinstance(err_obj, dict) and "message" in err_obj:
        return err_obj["message"]
    if isinstance(err_obj, str):
        return err_obj
    return error_msg


def _retry_error_message(retry_resp: Any) -> str:
    try:
        r_err = retry_resp.json().get("error", {})
        return (
            r_err.get("message", retry_resp.text[:300]) if isinstance(r_err, dict) else str(r_err)
        )
    except Exception:
        return retry_resp.text[:300]


async def post_openrouter_images(headers: dict[str, str], payload: dict[str, Any]) -> Any:
    return await asyncio.to_thread(
        requests.post,
        OPENROUTER_IMAGES_URL,
        headers=headers,
        json=payload,
        timeout=settings.VISUAL_TIMEOUT,
    )


async def retry_openrouter_minimal(
    response: Any, headers: dict[str, str], payload: dict[str, Any]
) -> tuple[Any, str]:
    """Log a failed /images call and, on a size/aspect rejection, retry with model + prompt only.

    Returns the response to continue with (the retry when it succeeded) and the latest error text.
    """
    error_msg = openrouter_error_message(response)
    logger.warning(
        "OpenRouter /api/v1/images endpoint returned error (%s): %s",
        response.status_code,
        error_msg,
    )

    # If parameter error with size/aspect_ratio, retry with minimal payload (model + prompt)
    if response.status_code != 400 or ("size" not in payload and "aspect_ratio" not in payload):
        return response, error_msg

    logger.info(
        "Retrying OpenRouter /api/v1/images with minimal payload due to parameter rejection: %s",
        error_msg,
    )
    retry_payload = {"model": payload["model"], "prompt": payload["prompt"]}
    retry_resp = await post_openrouter_images(headers, retry_payload)
    if retry_resp.status_code == 200:
        return retry_resp, error_msg
    return response, _retry_error_message(retry_resp)


# --- Black Forest Labs polling ------------------------------------------------------


async def poll_bfl_sample_url(polling_url: str, api_key: str) -> Optional[str]:
    """Poll a BFL task until ready; returns the sample URL or None on failure/timeout."""
    poll_deadline = time.monotonic() + BFL_POLL_TIMEOUT_SECONDS
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
            sample_url = (poll_body.get("result") or {}).get("sample")
            if not sample_url:
                logger.error("BFL polling response missing result.sample")
            return sample_url or None

        if "moderated" in status:
            logger.warning("BFL generation moderated")
            raise ValueError(f"BFL Image Generation blocked by safety filter: {status}")

        if status in _BFL_FAILED_STATUSES:
            logger.error("BFL generation failed, expired or not found")
            return None

        await asyncio.sleep(2.0)

    logger.error("BFL polling timed out after 600s")
    return None


# --- Placeholders -------------------------------------------------------------------


def resolve_color_theme(theme: Optional[str]) -> ColorTheme:
    """Map a theme string to ColorTheme, defaulting to COLORFUL."""
    color_theme = ColorTheme.COLORFUL
    if theme:
        with contextlib.suppress(KeyError, AttributeError):
            color_theme = ColorTheme[theme.upper()]
    return color_theme


def placeholder_extension(filename: Optional[str]) -> str:
    # Default to PNG for placeholders to preserve transparency if needed,
    # though we currently convert to RGB in the strategy.
    if filename and filename.lower().endswith((".jpg", ".jpeg")):
        return "jpg"
    return "png"


def is_static_only_placeholder_category(cat: str) -> bool:
    """NPC/item placeholders stay on curated static assets (no procedural SVG fallback)."""
    return cat in {"NPC", "ITEM"} or cat.startswith("ITEM_")
