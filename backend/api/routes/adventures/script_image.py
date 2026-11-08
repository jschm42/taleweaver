"""Builds the image callback behind ``tw.image.generate`` for adventure scripts.

Scripts run synchronously inside the sandbox, so the call blocks the script (and the turn
handling it) until the image is saved or ``SCRIPT_IMAGE_TIMEOUT_SECONDS`` passes. The async
``MediaEngine`` call runs on its own event loop in a worker thread, so a hanging provider can be
abandoned after the timeout. The client keeps its turn spinner up and input locked meanwhile.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from backend.core.style_catalog import resolve_style_instruction
from backend.engine.media.asset_naming import asset_filename
from backend.engine.media.media_engine import MediaEngine
from backend.engine.scripting.image_proxy import ImageGenerator
from backend.utils.path_security import safe_data_path, sanitize_path_component

logger = logging.getLogger(__name__)

# Stays below the client's 90 s turn timeout so the narrative pass can still finish.
SCRIPT_IMAGE_TIMEOUT_SECONDS = 60
LOCAL_PROVIDERS = ("ollama", "stable_diffusion", "comfyui")
# Per-tier T2I setting prefix; "hq" uses the "advanced_*" settings of the Visual Preferences.
_TIER_PREFIX = {"simple": "simple", "hq": "advanced"}

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="script-image")


def _tier_options(t2i: dict[str, Any], tier: str) -> tuple[str, str, dict[str, Any]]:
    """Returns (provider, model, provider options) for ``simple`` or ``hq``."""
    prefix = _TIER_PREFIX[tier]
    provider = str(t2i.get(f"{prefix}_model_provider") or t2i.get("provider") or "openai").lower()
    model = str(t2i.get(f"{prefix}_model") or "")
    options = dict(t2i)
    options["comfyui_profile"] = prefix
    for key in ("steps", "cfg_scale", "sampler_name", "scheduler"):
        options[key] = t2i.get(f"{prefix}_{key}")
    return provider, model, options


def _style_instruction(user: Any, adventure: Any, apply_style: bool) -> Optional[str]:
    if not apply_style:
        return None
    return (
        resolve_style_instruction(
            getattr(adventure, "selected_image_styles", None),
            getattr(user, "image_styles_catalog", None) or [],
        )
        or None
    )


def make_script_image_generator(
    user: Any,
    adventure: Any,
    game_id: str,
    on_status: Optional[Callable[[str], None]] = None,
) -> ImageGenerator:
    """Returns the callback ``tw.image.generate`` uses for this user and session.

    Images are stored in the session's own folder (``adventures/sessions/<game_id>/script_images``)
    so they never leak into the adventure template.
    """
    t2i = dict(getattr(user, "t2i_settings", None) or {})
    api_keys = dict(getattr(user, "encrypted_api_keys", None) or {})
    safe_game_id = sanitize_path_component(str(game_id or ""))
    adventure_id = str(getattr(adventure, "id", "") or "") or None

    def generate(prompt: str, tier: str, apply_style: bool) -> str:
        if not safe_game_id:
            raise ValueError("Missing game session for image generation.")
        provider, model, options = _tier_options(t2i, tier)
        if not model:
            raise ValueError(f"No {tier} image model is configured in the Visual Preferences.")
        api_key = MediaEngine._resolve_api_key(provider, api_keys)
        if provider not in LOCAL_PROVIDERS and not api_key:
            raise ValueError(f"Missing API key for image provider '{provider}'.")
        if on_status:
            on_status("Generating image...")
        coro = MediaEngine.generate_image(
            prompt=prompt,
            model=model,
            api_key=api_key,
            provider=provider,
            adventure_id=adventure_id,
            target_dir=safe_data_path("adventures", "sessions", safe_game_id, "script_images"),
            filename=asset_filename("script", t2i.get("image_format")),
            provider_options=options,
            style_instruction=_style_instruction(user, adventure, apply_style),
        )
        future = _EXECUTOR.submit(asyncio.run, coro)
        return str(future.result(timeout=SCRIPT_IMAGE_TIMEOUT_SECONDS) or "")

    return generate
