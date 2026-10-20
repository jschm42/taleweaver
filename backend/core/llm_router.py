import asyncio
import json
import logging
import re
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Optional, TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from backend.core.llm_errors import LLMTruncatedResponseError, build_truncation_error
from backend.core.llm_json_repair import (
    attempt_repair_truncated_json,
    is_truncated_json,
    repair_json,
)
from backend.core.llm_logger import log_llm_interaction, log_structured_event
from backend.core.llm_provider_config import (
    apply_provider_endpoint,
    is_minimax_model,
    json_schema_instruction,
    normalize_model,
    uses_json_mode_fallback,
)
from backend.core.llm_request_tuning import apply_prompt_cache_markers
from backend.core.llm_stream_filters import clean_stream_thinking, clean_stream_voice_tags
from backend.core.security import encryption_util
from backend.core.voice_tags import VOICE_TAG_SET
from backend.models.user import User

T = TypeVar("T", bound=BaseModel)

_TRUNCATED_RESPONSE_MESSAGE = (
    "LLM response was truncated (token limit). "
    "Please increase the token limit in Settings (Intelligence) and retry."
)


@dataclass
class _StructuredRequest:
    kwargs: dict[str, Any]
    normalized_model: str
    json_mode: bool
    system_prompt: str


logger = logging.getLogger(__name__)

# Compile regex pattern to match (English-only) voice tags.
# Sort by length descending to match longest first
_sorted_tags = sorted(VOICE_TAG_SET, key=len, reverse=True)
_tag_pattern = "|".join(re.escape(t) for t in _sorted_tags)

BRACKETED_RE = re.compile(
    rf"^\s*\[(?P<tag>{_tag_pattern})\]\s*:?\s*(?P<rest>.*)", re.IGNORECASE | re.DOTALL
)

UNBRACKETED_RE = re.compile(
    rf"^\s*(?P<tag>{_tag_pattern})\s*:?\s*\n\s*(?P<rest>.*)", re.IGNORECASE | re.DOTALL
)


class GameMasterLLM:
    DEFAULT_SMALL_MAX_TOKENS = 4096
    DEFAULT_COMPLEX_MAX_TOKENS = 8192
    DEFAULT_GENERATOR_MAX_TOKENS = 16384
    DEFAULT_COMPRESSION_MAX_TOKENS = 4096

    @staticmethod
    def _is_transient_llm_error(exc: Exception) -> bool:
        """Check if an exception is likely a transient connection drop, socket timeout or stale pool connection."""
        err_type = type(exc).__name__.lower()
        err_msg = str(exc or "").lower()
        return (
            "timeout" in err_type
            or "connection" in err_type
            or "apiconnectionerror" in err_type
            or "timeouterror" in err_type
            or "connecterror" in err_type
            or "readtimeout" in err_type
            or "connecttimeout" in err_type
            or (
                "deepseekexception" in err_type
                and ("timeout" in err_msg or "connection" in err_msg)
            )
            or "disconnected" in err_msg
            or "connection reset" in err_msg
            or "connection timed out" in err_msg
            or "time taken=0." in err_msg
            or "time taken=0" in err_msg
            or "serverdisconnected" in err_msg
            or "payloaderror" in err_msg
            or "remote disconnected" in err_msg
            or "broken pipe" in err_msg
            or "connection closed" in err_msg
        )

    @staticmethod
    def _extract_openrouter_available_providers(exc: Exception) -> list[str]:
        """Parse OpenRouter provider metadata from LiteLLM/OpenAI-style exceptions."""
        message = str(exc or "")
        if "No allowed providers are available for the selected model" not in message:
            return []

        match = re.search(r"'available_providers'\s*:\s*\[([^\]]*)\]", message)
        if not match:
            return []

        providers = re.findall(r"'([^']+)'", match.group(1))
        # Keep deterministic order and de-duplicate just in case.
        seen: set[str] = set()
        unique: list[str] = []
        for provider in providers:
            if provider and provider not in seen:
                seen.add(provider)
                unique.append(provider)
        return unique

    def _retry_kwargs_with_openrouter_provider_order(
        self, kwargs: dict, providers: list[str]
    ) -> dict:
        """Build retry kwargs that explicitly prefer providers OpenRouter says are available."""
        retry_kwargs = dict(kwargs)
        extra_body = dict(retry_kwargs.get("extra_body") or {})
        provider_block = dict(extra_body.get("provider") or {})
        provider_block["order"] = providers
        provider_block.setdefault("allow_fallbacks", True)
        extra_body["provider"] = provider_block
        retry_kwargs["extra_body"] = extra_body
        return retry_kwargs

    def _completion_with_openrouter_fallback(self, kwargs: dict):
        """Call LiteLLM completion and retry for OpenRouter provider-order mismatches and transient connection drops (up to 3 retries)."""
        if self.provider == "custom_openai":
            from backend.core.custom_openai import complete

            return complete(self, kwargs)
        max_transient_retries = 4
        for attempt in range(max_transient_retries):
            try:
                return self._get_litellm().completion(
                    **kwargs, request_timeout=self.request_timeout
                )
            except Exception as exc:
                if self.provider == "openrouter":
                    available_providers = self._extract_openrouter_available_providers(exc)
                    if available_providers:
                        logger.warning(
                            "OpenRouter provider mismatch for model '%s'. Retrying with provider order: %s",
                            kwargs.get("model"),
                            ",".join(available_providers),
                        )
                        retry_kwargs = self._retry_kwargs_with_openrouter_provider_order(
                            kwargs, available_providers
                        )
                        return self._get_litellm().completion(
                            **retry_kwargs, request_timeout=self.request_timeout
                        )

                    err_str = str(exc)
                    if "removed during routing" in err_str or "No endpoints found" in err_str:
                        extra_body = dict(kwargs.get("extra_body") or {})
                        if "provider" in extra_body:
                            logger.warning(
                                "OpenRouter provider routing failed for model '%s'. Retrying with unrestricted fallback routing.",
                                kwargs.get("model"),
                            )
                            retry_kwargs = dict(kwargs)
                            new_extra_body = dict(extra_body)
                            new_extra_body.pop("provider", None)
                            retry_kwargs["extra_body"] = new_extra_body
                            return self._get_litellm().completion(
                                **retry_kwargs, request_timeout=self.request_timeout
                            )

                if attempt < max_transient_retries - 1 and self._is_transient_llm_error(exc):
                    backoff_delay = 0.75 * (attempt + 1)
                    logger.warning(
                        "Transient LLM connection/timeout error on attempt %d/%d (retry %d/%d) (%s: %s). Retrying with fresh connection in %.2fs...",
                        attempt + 1,
                        max_transient_retries,
                        attempt + 1,
                        max_transient_retries - 1,
                        type(exc).__name__,
                        exc,
                        backoff_delay,
                    )
                    time.sleep(backoff_delay)
                    continue

                raise

    async def _acompletion_with_openrouter_fallback(self, kwargs: dict):
        """Async variant of completion retry for OpenRouter provider-order mismatches and transient connection drops (up to 3 retries)."""
        if self.provider == "custom_openai":
            from backend.core.custom_openai import acomplete

            return await acomplete(self, kwargs)
        max_transient_retries = 4
        for attempt in range(max_transient_retries):
            try:
                logger.info(
                    "GameMasterLLM calling LLM for user %s with model %s (attempt %d/%d)",
                    self.user.id,
                    kwargs.get("model"),
                    attempt + 1,
                    max_transient_retries,
                )
                return await self._get_litellm().acompletion(
                    **kwargs, request_timeout=self.request_timeout
                )
            except Exception as exc:
                if self.provider == "openrouter":
                    available_providers = self._extract_openrouter_available_providers(exc)
                    if available_providers:
                        logger.warning(
                            "OpenRouter provider mismatch for model '%s'. Retrying with provider order: %s",
                            kwargs.get("model"),
                            ",".join(available_providers),
                        )
                        retry_kwargs = self._retry_kwargs_with_openrouter_provider_order(
                            kwargs, available_providers
                        )
                        logger.info(
                            "GameMasterLLM calling LLM (Fallback) for user %s with model %s",
                            self.user.id,
                            kwargs.get("model"),
                        )
                        return await self._get_litellm().acompletion(
                            **retry_kwargs, request_timeout=self.request_timeout
                        )

                    err_str = str(exc)
                    if "removed during routing" in err_str or "No endpoints found" in err_str:
                        extra_body = dict(kwargs.get("extra_body") or {})
                        if "provider" in extra_body:
                            logger.warning(
                                "OpenRouter provider routing failed for model '%s'. Retrying with unrestricted fallback routing.",
                                kwargs.get("model"),
                            )
                            retry_kwargs = dict(kwargs)
                            new_extra_body = dict(extra_body)
                            new_extra_body.pop("provider", None)
                            retry_kwargs["extra_body"] = new_extra_body
                            return await self._get_litellm().acompletion(
                                **retry_kwargs, request_timeout=self.request_timeout
                            )

                if attempt < max_transient_retries - 1 and self._is_transient_llm_error(exc):
                    backoff_delay = 0.75 * (attempt + 1)
                    logger.warning(
                        "Transient LLM connection/timeout error on attempt %d/%d (retry %d/%d) (%s: %s). Retrying with fresh connection in %.2fs...",
                        attempt + 1,
                        max_transient_retries,
                        attempt + 1,
                        max_transient_retries - 1,
                        type(exc).__name__,
                        exc,
                        backoff_delay,
                    )
                    await asyncio.sleep(backoff_delay)
                    continue

                raise

    @staticmethod
    def _clean_json_string(content: str) -> str:
        """
        Extracts JSON/List from Markdown code blocks or strips leading/trailing junk.
        """
        content = content.strip()

        # Check for markdown code blocks first
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            # Check if there are at least two sets of backticks
            parts = content.split("```")
            if len(parts) >= 3:
                content = parts[1]

        content = content.strip()

        # Further refine: find first [ or { and last ] or }
        first_json_char = -1
        for i, char in enumerate(content):
            if char in ("{", "["):
                first_json_char = i
                break

        last_json_char = -1
        for i, char in enumerate(reversed(content)):
            if char in ("}", "]"):
                last_json_char = len(content) - 1 - i
                break

        if first_json_char != -1 and last_json_char != -1 and last_json_char > first_json_char:
            return content[first_json_char : last_json_char + 1]

        return content

    @staticmethod
    def _is_truncated_json(content: str) -> bool:
        """Heuristic: True when the JSON content looks cut off (e.g. token limit)."""
        return is_truncated_json(content)

    @staticmethod
    def _attempt_repair_truncated_json(content: str) -> str:
        """Best-effort close-out of a truncated JSON document (see llm_json_repair)."""
        return attempt_repair_truncated_json(content)

    @staticmethod
    def _repair_json(content: str) -> str:
        """Repairs common minor JSON syntax errors (see llm_json_repair)."""
        return repair_json(content)

    @staticmethod
    def clean_thinking_tags(text: str) -> str:
        """Strip <think>...</think> tags and the reasoning text inside them."""
        if not text:
            return ""
        # Remove completed think blocks
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        # Also strip any dangling open think tag to the end of the text (in case of truncation/interruption)
        cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL)
        return cleaned.strip()

    @staticmethod
    def extract_thinking(content: str, message: Any = None) -> str:
        """Extract thinking/reasoning text from the message content or reasoning fields."""
        # Check explicit reasoning field first
        reasoning = GameMasterLLM._extract_reasoning_content(message) if message else ""
        if reasoning and reasoning.strip():
            return reasoning.strip()

        # Fallback to extracting <think>...</think> blocks from content
        if content and "<think>" in content:
            matches = re.findall(r"<think>(.*?)</think>", content, flags=re.DOTALL)
            if matches:
                return "\n".join(matches).strip()
            # Handle incomplete/dangling think tags
            m = re.search(r"<think>(.*)", content, flags=re.DOTALL)
            if m:
                return m.group(1).strip()
        return ""

    @staticmethod
    async def _append_generation_log_async(
        adventure_id: Optional[str], log_type: str, content: str, image_url: Optional[str] = None
    ):
        """Append a status, thinking, or image generation log to the adventure template's generation_logs list."""
        if not adventure_id:
            return
        try:
            import datetime

            from sqlalchemy import select

            from backend.core.database import AsyncSessionLocal
            from backend.models.adventure_template import AdventureTemplate

            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    select(AdventureTemplate).where(AdventureTemplate.id == adventure_id)
                )
                adv = res.scalars().first()
                if adv:
                    logs = list(adv.generation_logs or [])
                    logs.append(
                        {
                            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            "type": log_type,
                            "content": content,
                            "image_url": image_url,
                        }
                    )
                    adv.generation_logs = logs
                    await db.commit()
        except Exception as e:
            logger.warning("Failed to append generation log: %s", e)

    @staticmethod
    def _to_canonical_voice_tag(tag: str) -> str:
        return tag.strip().lower()

    @staticmethod
    def normalize_voice_tags(text: str) -> str:
        """
        Normalizes voice/emotion tags at the beginning of the text, in paragraphs,
        and in character dialogue lines to standard English [tag] format.
        """
        if not text:
            return text

        # 1. Normalize leading tag of the whole text
        m = BRACKETED_RE.match(text)
        if m:
            tag = GameMasterLLM._to_canonical_voice_tag(m.group("tag"))
            rest = m.group("rest")
            text = f"[{tag}] {rest.lstrip()}" if rest.strip() else f"[{tag}]"
        else:
            m = UNBRACKETED_RE.match(text)
            if m:
                tag = GameMasterLLM._to_canonical_voice_tag(m.group("tag"))
                rest = m.group("rest")
                text = f"[{tag}] {rest.lstrip()}" if rest.strip() else f"[{tag}]"

        # 2. Line-by-line normalization for dialogue and paragraph voice tags
        lines = text.split("\n")
        normalized_lines: list[str] = []

        speaker_re = re.compile(
            r"^(?P<speaker>\s*(?:\*\*[^*:\n]+?\*\*|[^\n:]{1,60}):\s*)(?P<speech>.*)$"
        )
        tag_extract_re = re.compile(r'^"?\[(?P<tag>[^\]\n]+)\]"?\s*"?\s*(?P<body>.*)$')
        para_tag_re = re.compile(r"^\s*\[(?P<tag>[^\]\n]+)\]\s*(?P<body>.*)$")

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                normalized_lines.append(line)
                continue

            sp_match = speaker_re.match(line)
            if sp_match:
                speaker_part = sp_match.group("speaker")
                speech_part = sp_match.group("speech").strip()
                tag_match = tag_extract_re.match(speech_part)
                if tag_match:
                    canon_tag = GameMasterLLM._to_canonical_voice_tag(tag_match.group("tag"))
                    body = tag_match.group("body").strip()
                    body = (
                        body.rstrip('"')
                        .rstrip("”")
                        .rstrip("»")
                        .lstrip('"')
                        .lstrip("“")
                        .lstrip("„")
                        .lstrip("«")
                        .strip()
                    )
                    normalized_lines.append(f'{speaker_part}[{canon_tag}] "{body}"')
                    continue
                normalized_lines.append(line)
                continue

            # Paragraph leading tag normalization (e.g. German tag [neugierig] -> [curious])
            p_match = para_tag_re.match(line)
            if p_match:
                raw_tag = p_match.group("tag").strip()
                canon_tag = GameMasterLLM._to_canonical_voice_tag(raw_tag)
                if canon_tag != raw_tag:
                    body = p_match.group("body").strip()
                    normalized_lines.append(f"[{canon_tag}] {body}".strip())
                    continue

            normalized_lines.append(line)

        return "\n".join(normalized_lines)

    @staticmethod
    async def _clean_stream_voice_tags(stream):
        """Async generator that buffers the start of the stream and normalizes voice tags."""
        async for chunk in clean_stream_voice_tags(stream, GameMasterLLM.normalize_voice_tags):
            yield chunk

    @staticmethod
    async def _with_stream_timeout(
        stream,
        initial_timeout: float = 40.0,
        chunk_timeout: float = 12.0,
    ):
        """Async generator that enforces timeouts between streaming chunks.

        - initial_timeout: Max wait for the first chunk (time to first token).
        - chunk_timeout: Max wait between subsequent chunks (inactivity timeout).
        If chunk_timeout expires AFTER content has already been received, the stream
        terminates gracefully (as LLMs often complete without sending EOF or [DONE]).
        """
        has_content = False
        iterator = aiter(stream)

        while True:
            current_timeout = chunk_timeout if has_content else initial_timeout
            try:
                chunk = await asyncio.wait_for(anext(iterator), timeout=current_timeout)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                if has_content:
                    logger.warning(
                        "Stream stalled for %.1fs after receiving content; terminating stream gracefully.",
                        chunk_timeout,
                    )
                    break
                logger.error(
                    "Stream timed out after %.1fs without generating any content.",
                    initial_timeout,
                )
                raise TimeoutError("The AI model did not respond in time.") from None
            except Exception as e:
                if has_content:
                    logger.warning(
                        "Stream interrupted by %s after receiving content; preserving received narrative: %s",
                        type(e).__name__,
                        e,
                    )
                    break
                raise

            try:
                delta = chunk.choices[0].delta.content
                if delta and delta.strip():
                    has_content = True
            except (AttributeError, IndexError, TypeError):
                pass

            yield chunk

    @staticmethod
    async def _clean_stream_thinking(stream):
        """Async generator that strips <think>...</think> blocks from stream chunks on-the-fly."""
        async for chunk in clean_stream_thinking(stream):
            yield chunk

    @staticmethod
    def _extract_reasoning_content(message: Any) -> str:
        """Extract provider-specific reasoning text from a LiteLLM message object or dict."""
        if message is None:
            return ""

        direct = getattr(message, "reasoning_content", None)
        if isinstance(direct, str) and direct.strip():
            return direct

        if isinstance(message, dict):
            direct = message.get("reasoning_content")
            if isinstance(direct, str) and direct.strip():
                return direct
            provider_specific = message.get("provider_specific_fields") or {}
        else:
            provider_specific = getattr(message, "provider_specific_fields", None) or {}

        nested = (
            provider_specific.get("reasoning_content")
            if isinstance(provider_specific, dict)
            else None
        )
        if isinstance(nested, str) and nested.strip():
            return nested
        return ""

    @staticmethod
    def _build_blank_content_retry_kwargs(kwargs: dict) -> dict:
        """Return retry kwargs that explicitly force JSON into the assistant content channel."""
        retry_kwargs = deepcopy(kwargs)
        retry_messages = [dict(message) for message in retry_kwargs.get("messages", [])]
        if retry_messages:
            retry_messages[0]["content"] = (
                f"{retry_messages[0].get('content', '')}"
                "\n\nRETRY INSTRUCTION: Your previous reply left the assistant content empty or whitespace-only. "
                "Reply again with the final JSON object in the assistant content field itself. "
                "Do not put the answer only into reasoning_content. "
                "Do not include any explanation, prose, or markdown."
            )
        retry_kwargs["messages"] = retry_messages
        return retry_kwargs

    async def _retry_blank_json_content_async(self, kwargs: dict, response: Any):
        """Retry once when JSON-mode providers return only reasoning_content and an empty content channel."""
        try:
            message = response.choices[0].message
        except (AttributeError, IndexError, TypeError):
            return response

        reasoning_content = self._extract_reasoning_content(message)
        if not reasoning_content:
            return response

        logger.warning(
            "LLM returned empty assistant content but reasoning_content was populated. Retrying once with explicit content-channel instruction."
        )
        retry_kwargs = self._build_blank_content_retry_kwargs(kwargs)
        return await self._acompletion_with_openrouter_fallback(retry_kwargs)

    def _retry_blank_json_content(self, kwargs: dict, response: Any):
        """Sync variant of retry for empty content with populated reasoning_content."""
        try:
            message = response.choices[0].message
        except (AttributeError, IndexError, TypeError):
            return response

        reasoning_content = self._extract_reasoning_content(message)
        if not reasoning_content:
            return response

        logger.warning(
            "LLM returned empty assistant content but reasoning_content was populated. Retrying once with explicit content-channel instruction."
        )
        retry_kwargs = self._build_blank_content_retry_kwargs(kwargs)
        return self._completion_with_openrouter_fallback(retry_kwargs)

    @staticmethod
    def _is_supported_bool_value(value: Any) -> bool:
        """Return True when the value is a supported persisted bool representation."""
        if isinstance(value, bool):
            return True
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized in {
                "1",
                "true",
                "yes",
                "on",
                "enabled",
                "0",
                "false",
                "no",
                "off",
                "disabled",
                "",
                "none",
                "null",
            }
        return False

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        """Safely coerce persisted setting values to booleans."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "enabled"}:
                return True
            if normalized in {"0", "false", "no", "off", "disabled", "", "none", "null"}:
                return False
        return default

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        """Safely coerce persisted setting values to ints with sane fallback."""
        try:
            coerced = int(value)
            return coerced if coerced > 0 else default
        except (TypeError, ValueError):
            return default

    @classmethod
    def _get_litellm(cls) -> Any:
        # Configuration is handled once
        litellm.drop_params = True
        litellm.add_usage = False
        return litellm

    _CATEGORY_PREFIXES = {
        "generator": "generator_",
        "complex": "complex_",
        "compression": "compression_",
    }

    @staticmethod
    def _category_setting(llm_settings: dict, prefix: str, key: str) -> Any:
        """Granular per-category setting with a fallback to the global/legacy name."""
        value = llm_settings.get(f"{prefix}{key}")
        return llm_settings.get(key) if value is None else value

    def _default_max_tokens(self, model_category: str) -> int:
        defaults = {
            "generator": self.DEFAULT_GENERATOR_MAX_TOKENS,
            "complex": self.DEFAULT_COMPLEX_MAX_TOKENS,
            "compression": self.DEFAULT_COMPRESSION_MAX_TOKENS,
        }
        return defaults.get(model_category, self.DEFAULT_SMALL_MAX_TOKENS)

    def _load_runtime_settings(self, model_category: str) -> None:
        """Timeouts and OpenAI-compatible endpoint bases from the app settings."""
        from backend.core.config import settings

        raw_timeout = settings.INTELLIGENCE_TIMEOUT
        if model_category == "generator":
            raw_timeout = getattr(settings, "WORLDBUILDING_TIMEOUT", settings.INTELLIGENCE_TIMEOUT)
        self.request_timeout = self._coerce_int(raw_timeout, default=settings.INTELLIGENCE_TIMEOUT)
        self.stream_chunk_timeout = float(getattr(settings, "STREAM_CHUNK_TIMEOUT", 12.0) or 12.0)
        self.stream_initial_timeout = float(
            getattr(settings, "STREAM_INITIAL_TIMEOUT", 40.0) or 40.0
        )
        self.kimi_api_base = (
            getattr(settings, "KIMI_API_BASE", "https://api.moonshot.ai/v1")
            or "https://api.moonshot.ai/v1"
        ).rstrip("/")
        self.minimax_api_base = (
            getattr(settings, "MINIMAX_API_BASE", "https://api.minimax.io/v1")
            or "https://api.minimax.io/v1"
        ).rstrip("/")

    def _resolve_enable_thinking(
        self, llm_settings: dict, prefix: str, model_category: str
    ) -> bool:
        """Thinking stays disabled unless explicitly configured truthy.

        The small model (fast structured extraction) never inherits the global flag:
        thinking there only adds latency before the narration can start.
        """
        key = f"{prefix}enable_thinking"
        raw_value = llm_settings.get(key)
        if raw_value is None and model_category != "small":
            key = "enable_thinking"
            raw_value = llm_settings.get(key)
        if raw_value is not None and not self._is_supported_bool_value(raw_value):
            logger.warning(
                "Invalid thinking setting '%s'=%r for user '%s'. Falling back to False.",
                key,
                raw_value,
                getattr(self.user, "username", "unknown"),
            )
            return False
        return self._coerce_bool(raw_value, default=False)

    def __init__(self, user: User, provider: str = "openai", model_category: str = "small"):
        """
        Initialize the router for a specific user, provider and model category (small/complex).
        """
        self.user = user
        self.provider = (provider or "openai").lower()
        self.api_key = None
        self.api_base = None

        llm_settings = self.user.llm_settings or {}
        prefix = self._CATEGORY_PREFIXES.get(model_category, "small_")
        self._load_runtime_settings(model_category)

        self.enable_thinking = self._resolve_enable_thinking(llm_settings, prefix, model_category)
        self.max_thinking_tokens = self._coerce_int(
            self._category_setting(llm_settings, prefix, "max_thinking_tokens"), default=1024
        )
        self.max_tokens = self._coerce_int(
            self._category_setting(llm_settings, prefix, "max_tokens"),
            default=self._default_max_tokens(model_category),
        )
        # OpenRouter provider routing preferences
        self.openrouter_provider = (
            self._category_setting(llm_settings, prefix, "openrouter_provider") or ""
        ).strip()

        if self.provider == "custom_openai":
            from backend.core.custom_openai import configure_custom_router

            configure_custom_router(self, llm_settings)
        elif self.provider == "ollama":
            self.api_base = (llm_settings.get("ollama_url") or "http://localhost:11434").rstrip("/")
        else:
            self.api_key = self._get_decrypted_key(self.provider)

        self.model_category = model_category
        logger.info(
            "Router initialized: category=%s, provider=%s, thinking=%s, max_tokens=%s, timeout=%ss",
            model_category,
            self.provider,
            self.enable_thinking,
            self.max_tokens,
            self.request_timeout,
        )

    def _normalize_model(self, model: str) -> str:
        """Return a LiteLLM-friendly model slug for the configured provider."""
        return normalize_model(self.provider, model)

    def _prepare_cacheable_messages(self, kwargs: dict, normalized_model: str) -> None:
        """Adds prompt-cache breakpoints on a copy of the messages (caller lists stay untouched)."""
        messages = kwargs.get("messages")
        if not messages:
            return
        kwargs["messages"] = deepcopy(messages)
        apply_prompt_cache_markers(kwargs["messages"], self.provider, normalized_model)

    def _apply_thinking_settings(self, kwargs: dict) -> None:
        """Inject thinking parameters based on user settings and provider."""
        # MiniMax defaults to thinking-on server-side, so we must explicitly opt-out
        # when the user has not enabled thinking in their settings.
        if self.provider == "minimax":
            kwargs["thinking"] = (
                {"type": "adaptive"} if self.enable_thinking else {"type": "disabled"}
            )
            return

        if not self.enable_thinking:
            return

        # LiteLLM maps 'thinking' to provider-specific params (budget_tokens for Anthropic, etc.)
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": self.max_thinking_tokens}

    def _apply_openrouter_provider_routing(self, kwargs: dict) -> None:
        """Inject provider routing ordering into OpenRouter requests if configured."""
        if self.provider == "custom_openai":
            return
        if self.provider != "openrouter" and not (
            isinstance(self.api_key, str) and self.api_key.startswith("sk-or-v1")
        ):
            return

        if not self.openrouter_provider:
            return

        providers = [
            p.strip() for p in self.openrouter_provider.split(",") if p.strip() and "/" not in p
        ]
        if not providers:
            return

        extra_body = dict(kwargs.get("extra_body") or {})
        provider_block = dict(extra_body.get("provider") or {})
        provider_block["order"] = providers
        provider_block["allow_fallbacks"] = False
        extra_body["provider"] = provider_block
        kwargs["extra_body"] = extra_body

    def _get_decrypted_key(self, provider: str) -> str:
        from backend.core.config import settings

        # 1. Check environment variables first (precedence)
        env_key = settings.get_env_api_key(provider)
        if env_key:
            return env_key

        # 2. Fallback to database
        if not self.user.encrypted_api_keys or provider not in self.user.encrypted_api_keys:
            raise ValueError(f"No API key configured for provider: {provider}")

        encrypted_key = self.user.encrypted_api_keys[provider]
        return encryption_util.decrypt_key(encrypted_key)

    def _validate_ollama_model(self, model: str) -> None:
        """Ensure local Ollama mode never silently routes to cloud models."""
        if self.provider != "ollama":
            return
        if not model or not model.strip():
            raise ValueError("No model configured for provider 'ollama'.")

        remote_prefixes = (
            "openai/",
            "openrouter/",
            "anthropic/",
            "deepseek/",
            "google/",
            "gemini/",
            "bedrock/",
            "azure/",
            "cohere/",
        )
        if model.startswith(remote_prefixes):
            raise ValueError(
                f"Provider is 'ollama' but model '{model}' looks like a remote/cloud model. "
                "Configure a local Ollama model (for example: llama3.2, qwen2.5, mistral)."
            )

    def execute_simple_task(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        *,
        adventure_id: Optional[str] = None,
        game_id: Optional[str] = None,
        operation: Optional[str] = None,
        phase: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Free narrative task (Hallucination Mode).
        Provides a plain text output from the model.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        normalized_model = self._normalize_model(model)

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "max_tokens": self.max_tokens
            + (self.max_thinking_tokens if self.enable_thinking else 0),
        }
        self._apply_thinking_settings(kwargs)

        if self.provider == "ollama":
            self._validate_ollama_model(model)
        apply_provider_endpoint(
            kwargs,
            provider=self.provider,
            api_key=self.api_key,
            api_base=self.api_base,
            kimi_api_base=self.kimi_api_base,
            minimax_api_base=self.minimax_api_base,
        )

        self._apply_openrouter_provider_routing(kwargs)

        log_structured_event(
            "gm.turn.request",
            model=normalized_model,
            provider=self.provider,
            adventure_id=adventure_id,
            game_id=game_id,
            operation=operation,
            phase=phase,
            metadata=metadata,
        )

        response = self._completion_with_openrouter_fallback(kwargs)

        result = response.choices[0].message.content or ""
        result = self.clean_thinking_tags(result)
        result = self.normalize_voice_tags(result)

        log_llm_interaction(
            model=model,
            provider=self.provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_content=result,
            raw_response=response.model_dump(),
            event_type="gm.turn.response",
            adventure_id=adventure_id,
            game_id=game_id,
            operation=operation,
            phase=phase,
            metadata=metadata,
        )

        return result

    async def aexecute_simple_task(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        *,
        adventure_id: Optional[str] = None,
        game_id: Optional[str] = None,
        operation: Optional[str] = None,
        phase: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Async version of execute_simple_task.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        normalized_model = self._normalize_model(model)

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "max_tokens": self.max_tokens
            + (self.max_thinking_tokens if self.enable_thinking else 0),
        }
        self._apply_thinking_settings(kwargs)

        if self.provider == "ollama":
            self._validate_ollama_model(model)
        apply_provider_endpoint(
            kwargs,
            provider=self.provider,
            api_key=self.api_key,
            api_base=self.api_base,
            kimi_api_base=self.kimi_api_base,
            minimax_api_base=self.minimax_api_base,
        )

        self._apply_openrouter_provider_routing(kwargs)

        log_structured_event(
            "gm.turn.request",
            model=normalized_model,
            provider=self.provider,
            adventure_id=adventure_id,
            game_id=game_id,
            operation=operation,
            phase=phase,
            metadata=metadata,
        )

        response = await self._acompletion_with_openrouter_fallback(kwargs)

        result = response.choices[0].message.content or ""
        result = self.clean_thinking_tags(result)
        result = self.normalize_voice_tags(result)

        log_llm_interaction(
            model=model,
            provider=self.provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_content=result,
            raw_response=response.model_dump(),
            event_type="gm.turn.response",
            adventure_id=adventure_id,
            game_id=game_id,
            operation=operation,
            phase=phase,
            metadata=metadata,
        )

        return result

    async def stream_simple_task(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        *,
        messages: Optional[list[dict[str, Any]]] = None,
        adventure_id: Optional[str] = None,
        game_id: Optional[str] = None,
        operation: Optional[str] = None,
        phase: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """
        Streams a free narrative task.
        """
        if messages is None:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

        normalized_model = self._normalize_model(model)

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "max_tokens": self.max_tokens
            + (self.max_thinking_tokens if self.enable_thinking else 0),
            "stream": True,
            # Report token usage (incl. cached prompt tokens) in the final stream chunk.
            "stream_options": {"include_usage": True},
        }
        self._apply_thinking_settings(kwargs)

        if self.provider == "ollama":
            self._validate_ollama_model(model)
        apply_provider_endpoint(
            kwargs,
            provider=self.provider,
            api_key=self.api_key,
            api_base=self.api_base,
            kimi_api_base=self.kimi_api_base,
            minimax_api_base=self.minimax_api_base,
        )

        self._apply_openrouter_provider_routing(kwargs)

        log_structured_event(
            "gm.turn.stream.request",
            model=normalized_model,
            provider=self.provider,
            adventure_id=adventure_id,
            game_id=game_id,
            operation=operation,
            phase=phase,
            metadata=metadata,
        )

        self._prepare_cacheable_messages(kwargs, normalized_model)
        raw_stream = await self._acompletion_with_openrouter_fallback(kwargs)
        timed_stream = self._with_stream_timeout(
            raw_stream,
            initial_timeout=self.stream_initial_timeout,
            chunk_timeout=self.stream_chunk_timeout,
        )
        stream = self._clean_stream_thinking(timed_stream)
        return self._clean_stream_voice_tags(stream)

    @staticmethod
    def _structured_response_format(json_mode: bool, minimax: bool, response_model: type[T]) -> Any:
        """MiniMax rejects response_format; JSON-mode providers get json_object."""
        if minimax:
            return None
        return {"type": "json_object"} if json_mode else response_model

    def _build_structured_request(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str,
    ) -> _StructuredRequest:
        """Builds LiteLLM kwargs for a structured-output (Pydantic) task."""
        normalized_model = self._normalize_model(model)
        json_mode = uses_json_mode_fallback(self.provider, normalized_model)
        if json_mode:
            # Inject the schema into the prompt since strict enforcement is bypassed.
            system_prompt += json_schema_instruction(response_model)

        kwargs: dict[str, Any] = {
            "model": normalized_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens
            + (self.max_thinking_tokens if self.enable_thinking and not json_mode else 0),
        }
        response_format = self._structured_response_format(
            json_mode, is_minimax_model(self.provider, normalized_model), response_model
        )
        if self.provider == "custom_openai":
            from backend.core.custom_openai import structured_response_format

            response_format = structured_response_format(self, response_model)
        if response_format is not None:
            kwargs["response_format"] = response_format
        if not json_mode:
            self._apply_thinking_settings(kwargs)
        if self.provider == "ollama":
            self._validate_ollama_model(model)
        apply_provider_endpoint(
            kwargs,
            provider=self.provider,
            api_key=self.api_key,
            api_base=self.api_base,
            kimi_api_base=self.kimi_api_base,
            minimax_api_base=self.minimax_api_base,
        )
        self._apply_openrouter_provider_routing(kwargs)
        self._prepare_cacheable_messages(kwargs, normalized_model)
        return _StructuredRequest(kwargs, normalized_model, json_mode, system_prompt)

    def _log_structured_request(
        self, request: _StructuredRequest, response_model: type[T], log_context: dict[str, Any]
    ) -> None:
        log_structured_event(
            "gm.turn.request",
            model=request.normalized_model,
            provider=self.provider,
            response_model=response_model.__name__,
            **log_context,
        )

    def _log_structured_response(
        self,
        request: _StructuredRequest,
        response: Any,
        model: str,
        user_prompt: str,
        response_model: type[T],
        log_context: dict[str, Any],
    ) -> None:
        log_llm_interaction(
            model=model,
            provider=self.provider,
            system_prompt=request.system_prompt,
            user_prompt=user_prompt,
            response_content=response.choices[0].message.content or "",
            raw_response=response.model_dump(),
            event_type="gm.turn.response",
            adventure_id=log_context["adventure_id"],
            game_id=log_context["game_id"],
            operation=log_context["operation"],
            phase=log_context["phase"],
            metadata={
                **(log_context["metadata"] or {}),
                "response_model": response_model.__name__,
            },
        )

    @staticmethod
    def _is_blank_response(response: Any) -> bool:
        content = response.choices[0].message.content
        return content is None or not str(content).strip()

    def _truncation_error(self, response: Any) -> LLMTruncatedResponseError:
        return build_truncation_error(
            response,
            model_category=getattr(self, "model_category", "small"),
            provider=self.provider,
            max_tokens=self.max_tokens,
        )

    def _empty_content_error(self, response: Any, finish_reason: Any) -> ValueError:
        if finish_reason == "length":
            return self._truncation_error(response)
        return ValueError("No content returned from LLM for complex task.")

    @staticmethod
    def _content_preview(content: str) -> str:
        return content[:280].replace("\n", " ").strip()

    def _parse_json_payload(self, content: str, finish_reason: Any) -> Any:
        """Parses LLM JSON, attempting a best-effort repair of malformed documents."""
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            if finish_reason == "length" or self._is_truncated_json(content):
                logger.error(
                    "LLM response appears truncated. Length: %d, finish_reason: %s. Full content: %s",
                    len(content),
                    finish_reason,
                    content,
                )
                raise LLMTruncatedResponseError(_TRUNCATED_RESPONSE_MESSAGE) from exc
            repaired = self._attempt_repair_truncated_json(content)
            data = None
            if repaired != content:
                try:
                    data = json.loads(repaired)
                    logger.warning(
                        "LLM response was malformed but could be repaired. Original length: %d.",
                        len(content),
                    )
                except json.JSONDecodeError:
                    data = None
            if data is None:
                logger.error(
                    "LLM response was not valid JSON. Length: %d, finish_reason: %s. Full content: %s",
                    len(content),
                    finish_reason,
                    content,
                )
                raise ValueError(
                    f"Failed to parse LLM response as JSON. Preview: {self._content_preview(content)}"
                ) from exc
            return data

    @staticmethod
    def _as_mapping(data: Any, response_model: type[T]) -> dict:
        if isinstance(data, list) and data:
            logger.warning(
                f"LLM returned a list for {response_model.__name__}. Taking first element."
            )
            data = data[0]
        if not isinstance(data, dict):
            raise ValueError(
                f"LLM returned {type(data).__name__} but a mapping was expected for {response_model.__name__}."
            )
        return data

    def _parse_structured_content(self, response: Any, response_model: type[T]) -> T:
        """Turns a completion response into the requested Pydantic model."""
        content = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        if not content:
            logger.error(f"LLM returned empty content. Raw response: {response.model_dump()}")
            raise self._empty_content_error(response, finish_reason)

        try:
            content = self._clean_json_string(self.clean_thinking_tags(content))
            if not content:
                logger.error(
                    "LLM returned content that was empty after JSON cleanup. Raw response: %s",
                    response.model_dump(),
                )
                raise self._empty_content_error(response, finish_reason)
            data = self._parse_json_payload(self._repair_json(content), finish_reason)
            return response_model(**self._as_mapping(data, response_model))
        except LLMTruncatedResponseError as exc:
            if exc.diagnostics:
                raise
            raise self._truncation_error(response) from exc
        except json.JSONDecodeError as exc:
            if finish_reason == "length" or self._is_truncated_json(content):
                raise self._truncation_error(response) from exc
            raise ValueError(
                f"Failed to parse LLM response as JSON. Preview: {self._content_preview(content)}"
            ) from exc
        except ValidationError as exc:
            raise ValueError(
                f"LLM returned JSON that does not match expected schema {response_model.__name__}. "
                f"Preview: {self._content_preview(content)}. Validation: {exc}"
            ) from exc

    async def aexecute_complex_task(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str,
        *,
        adventure_id: Optional[str] = None,
        game_id: Optional[str] = None,
        operation: Optional[str] = None,
        phase: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> T:
        """
        Async version of execute_complex_task.
        """
        log_context = {
            "adventure_id": adventure_id,
            "game_id": game_id,
            "operation": operation,
            "phase": phase,
            "metadata": metadata,
        }
        request = self._build_structured_request(system_prompt, user_prompt, response_model, model)
        self._log_structured_request(request, response_model, log_context)

        response = await self._acompletion_with_openrouter_fallback(request.kwargs)
        if request.json_mode and self._is_blank_response(response):
            response = await self._retry_blank_json_content_async(request.kwargs, response)

        # Log thinking/reasoning if present
        if adventure_id:
            message = response.choices[0].message
            thinking_text = self.extract_thinking(message.content or "", message)
            if thinking_text:
                await self._append_generation_log_async(adventure_id, "thinking", thinking_text)

        self._log_structured_response(
            request, response, model, user_prompt, response_model, log_context
        )
        return self._parse_structured_content(response, response_model)

    def execute_complex_task(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str,
        *,
        adventure_id: Optional[str] = None,
        game_id: Optional[str] = None,
        operation: Optional[str] = None,
        phase: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> T:
        """
        Strict mechanics task (Strict Mode).
        Uses 'response_format' to force the LLM to return standard JSON
        that matches the given Pydantic model.
        """
        log_context = {
            "adventure_id": adventure_id,
            "game_id": game_id,
            "operation": operation,
            "phase": phase,
            "metadata": metadata,
        }
        request = self._build_structured_request(system_prompt, user_prompt, response_model, model)
        self._log_structured_request(request, response_model, log_context)

        response = self._completion_with_openrouter_fallback(request.kwargs)
        if request.json_mode and self._is_blank_response(response):
            response = self._retry_blank_json_content(request.kwargs, response)

        self._log_structured_response(
            request, response, model, user_prompt, response_model, log_context
        )
        return self._parse_structured_content(response, response_model)
