"""``tw.image`` (alias ``tw.media``): lets adventure scripts generate images and show them in chat."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from backend.engine.scripting.sandbox import in_guard_expression, refund_time_budget

if TYPE_CHECKING:
    from backend.engine.scripting.context import ScriptChangeset

logger = logging.getLogger(__name__)

# (prompt, model tier "simple" | "hq", apply_style) -> image URL. Raises on provider errors.
ImageGenerator = Callable[[str, str, bool], str]

# "advanced" is accepted as an alias for "hq" (it matches the T2I settings naming).
MODEL_TIER_ALIASES = {"simple": "simple", "hq": "hq", "advanced": "hq"}
MAX_IMAGES_PER_CONTEXT = 2
MAX_PROMPT_CHARS = 1500
MAX_CAPTION_CHARS = 200
# Only images served by TaleWeaver itself or plain web URLs may be shown in the story feed.
_SHOWABLE_URL = re.compile(r"^(/data/|https?://)[^\s()<>\"']+$", re.IGNORECASE)
_CAPTION_UNSAFE = re.compile(r"[\[\]()\r\n]+")


def normalize_model_tier(model: str, caller: str) -> str:
    """Maps ``simple`` / ``hq`` / ``advanced`` to ``simple`` or ``hq``; raises on other values."""
    tier = MODEL_TIER_ALIASES.get(str(model or "simple").strip().lower())
    if tier is None:
        raise ValueError(f"{caller}: model must be 'simple', 'hq' or 'advanced', got '{model}'.")
    return tier


def image_markdown(image_url: str, caption: str = "") -> str:
    """Builds the ``![caption](url)`` line the story feed renders as an image block."""
    words = _CAPTION_UNSAFE.sub(" ", str(caption or "")).split()
    clean_caption = " ".join(words)[:MAX_CAPTION_CHARS]
    return f"![{clean_caption}]({image_url})"


class ImageProxy:
    """Safe proxy for image generation. Every failure returns ``""`` instead of raising."""

    def __init__(
        self,
        generator: Optional[ImageGenerator],
        changeset: ScriptChangeset,
        is_debug_enabled: bool = False,
    ):
        self._generator = generator
        self._changeset = changeset
        self._is_debug_enabled = is_debug_enabled
        self._calls = 0

    @property
    def available(self) -> bool:
        """True when this script context may generate images (never inside guard expressions)."""
        return self._generator is not None and not in_guard_expression()

    def generate(
        self,
        prompt: str,
        model: str = "simple",
        apply_style: bool = True,
        show_in_chat: bool = True,
        caption: str = "",
    ) -> str:
        """Generates an image with the ``simple`` or ``hq`` (alias ``advanced``) image model.

        ``apply_style`` adds the adventure's image style to the prompt. With ``show_in_chat`` the
        image is posted to the story feed. Returns the image URL, or ``""`` when image generation
        is unavailable, the call limit is reached, or the request fails or times out.
        """
        tier = normalize_model_tier(model, "tw.image.generate")
        url = self._request("tw.image.generate", prompt, tier, bool(apply_style))
        if url and show_in_chat:
            self.show(url, caption)
        return url

    def generate_simple(
        self, prompt: str, apply_style: bool = True, show_in_chat: bool = True, caption: str = ""
    ) -> str:
        """Shortcut for ``generate(prompt, model="simple", ...)``."""
        return self.generate(prompt, "simple", apply_style, show_in_chat, caption)

    def generate_hq(
        self, prompt: str, apply_style: bool = True, show_in_chat: bool = True, caption: str = ""
    ) -> str:
        """Shortcut for ``generate(prompt, model="hq", ...)``."""
        return self.generate(prompt, "hq", apply_style, show_in_chat, caption)

    def show(self, image_url: str, caption: str = "") -> None:
        """Posts an image (``/data/...`` or ``http(s)://`` URL) with an optional caption to chat."""
        url = str(image_url or "").strip()
        if not _SHOWABLE_URL.match(url):
            self._note(f"tw.image.show skipped: unsupported image URL '{url[:80]}'.")
            return
        self._changeset.narrative_messages.append(image_markdown(url, caption))

    def _request(self, caller: str, prompt: str, tier: str, apply_style: bool) -> str:
        text = str(prompt or "").strip()
        if not text:
            return ""
        if in_guard_expression():
            self._note(f"{caller} is not available in guard expressions.")
            return ""
        if self._generator is None:
            self._note(f"{caller} is not available in this script context.")
            return ""
        if self._calls >= MAX_IMAGES_PER_CONTEXT:
            self._note(f"{caller} skipped: limit of {MAX_IMAGES_PER_CONTEXT} images reached.")
            return ""
        self._calls += 1
        return self._call(caller, text[:MAX_PROMPT_CHARS], tier, apply_style)

    def _call(self, caller: str, prompt: str, tier: str, apply_style: bool) -> str:
        started = time.monotonic()
        try:
            url = self._generator(prompt, tier, apply_style) if self._generator else ""
        except Exception as exc:
            logger.warning("[Script] %s (%s) failed: %s", caller, tier, exc)
            self._note(f"{caller} failed: {exc}")
            return ""
        finally:
            # Waiting for the image model must not count against the script's time limit.
            refund_time_budget(time.monotonic() - started)
        return str(url or "").strip()

    def _note(self, message: str) -> None:
        logger.info("[Script] %s", message)
        if self._is_debug_enabled:
            self._changeset.system_messages.append(f"[DEBUG] {message}")


# ``tw.media`` is the same proxy under a second name.
MediaProxy = ImageProxy
