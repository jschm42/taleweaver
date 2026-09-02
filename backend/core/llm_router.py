import asyncio
import json
import logging
import re
import time
from copy import deepcopy
from typing import Any, Optional, TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from backend.core.llm_logger import log_llm_interaction, log_structured_event
from backend.core.security import encryption_util
from backend.models.user import User
from backend.core.voice_tags import VOICE_TAG_SET

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

# Compile regex pattern to match voice tags.
# Sort by length descending to match longest first
_sorted_tags = sorted(VOICE_TAG_SET, key=len, reverse=True)
_tag_pattern = "|".join(re.escape(t) for t in _sorted_tags)

BRACKETED_RE = re.compile(
    rf"^\s*\[(?P<tag>{_tag_pattern})\]\s*:?\s*(?P<rest>.*)",
    re.IGNORECASE | re.DOTALL
)

UNBRACKETED_RE = re.compile(
    rf"^\s*(?P<tag>{_tag_pattern})\s*:?\s*\n\s*(?P<rest>.*)",
    re.IGNORECASE | re.DOTALL
)



class GameMasterLLM:
    DEFAULT_SMALL_MAX_TOKENS = 4096
    DEFAULT_COMPLEX_MAX_TOKENS = 8192
    DEFAULT_GENERATOR_MAX_TOKENS = 16384


    @staticmethod
    def _is_transient_llm_error(exc: Exception) -> bool:
        """Check if an exception is likely a transient connection drop, socket timeout or stale pool connection."""
        err_type = type(exc).__name__.lower()
        err_msg = str(exc or "").lower()
        return (
            "timeout" in err_type
            or "connection" in err_type
            or "disconnected" in err_msg
            or "connection reset" in err_msg
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

    def _retry_kwargs_with_openrouter_provider_order(self, kwargs: dict, providers: list[str]) -> dict:
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
        """Call LiteLLM completion and retry for OpenRouter provider-order mismatches and transient connection drops."""
        max_transient_retries = 2
        for attempt in range(max_transient_retries):
            try:
                return self._get_litellm().completion(**kwargs, request_timeout=self.request_timeout)
            except Exception as exc:
                if self.provider == "openrouter":
                    available_providers = self._extract_openrouter_available_providers(exc)
                    if available_providers:
                        logger.warning(
                            "OpenRouter provider mismatch for model '%s'. Retrying with provider order: %s",
                            kwargs.get("model"),
                            ",".join(available_providers),
                        )
                        retry_kwargs = self._retry_kwargs_with_openrouter_provider_order(kwargs, available_providers)
                        return self._get_litellm().completion(**retry_kwargs, request_timeout=self.request_timeout)

                if attempt < max_transient_retries - 1 and self._is_transient_llm_error(exc):
                    logger.warning(
                        "Transient LLM connection/timeout error on attempt %d (%s: %s). Retrying with fresh connection...",
                        attempt + 1,
                        type(exc).__name__,
                        exc,
                    )
                    time.sleep(0.5)
                    continue

                raise

    async def _acompletion_with_openrouter_fallback(self, kwargs: dict):
        """Async variant of completion retry for OpenRouter provider-order mismatches and transient connection drops."""
        max_transient_retries = 2
        for attempt in range(max_transient_retries):
            try:
                logger.info(
                    "GameMasterLLM calling LLM for user %s with model %s (attempt %d/%d)",
                    self.user.id,
                    kwargs.get("model"),
                    attempt + 1,
                    max_transient_retries,
                )
                return await self._get_litellm().acompletion(**kwargs, request_timeout=self.request_timeout)
            except Exception as exc:
                if self.provider == "openrouter":
                    available_providers = self._extract_openrouter_available_providers(exc)
                    if available_providers:
                        logger.warning(
                            "OpenRouter provider mismatch for model '%s'. Retrying with provider order: %s",
                            kwargs.get("model"),
                            ",".join(available_providers),
                        )
                        retry_kwargs = self._retry_kwargs_with_openrouter_provider_order(kwargs, available_providers)
                        logger.info(
                            "GameMasterLLM calling LLM (Fallback) for user %s with model %s",
                            self.user.id,
                            kwargs.get("model"),
                        )
                        return await self._get_litellm().acompletion(**retry_kwargs, request_timeout=self.request_timeout)

                if attempt < max_transient_retries - 1 and self._is_transient_llm_error(exc):
                    logger.warning(
                        "Transient LLM connection/timeout error on attempt %d (%s: %s). Retrying with fresh connection...",
                        attempt + 1,
                        type(exc).__name__,
                        exc,
                    )
                    await asyncio.sleep(0.5)
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
            if char in ('{', '['):
                first_json_char = i
                break

        last_json_char = -1
        for i, char in enumerate(reversed(content)):
            if char in ('}', ']'):
                last_json_char = len(content) - 1 - i
                break

        if first_json_char != -1 and last_json_char != -1 and last_json_char > first_json_char:
            return content[first_json_char : last_json_char + 1]

        return content

    @staticmethod
    def _is_truncated_json(content: str) -> bool:
        """
        Heuristic: detect whether the JSON content is truncated mid-string
        (e.g. a token-limit cutoff). Returns True when the last meaningful
        character suggests the LLM ran out of tokens before closing the JSON.
        """
        if not content:
            return False
        stripped = content.rstrip()
        if not stripped:
            return False
        # A well-formed JSON document ends with } or ]
        if stripped[-1] in (']', '}'):
            return False
        # If the last non-whitespace char is a quote followed by a colon or
        # comma, or the string appears to end mid-value, treat as truncated.
        return True

    @staticmethod
    def _attempt_repair_truncated_json(content: str) -> str:
        """
        Try to close an obviously truncated JSON document so json.loads can
        parse it. Strategy: walk the string tracking quote/escape state and
        brace/bracket depth. If we end inside an unterminated string, find
        the start of that incomplete string and truncate back to the last
        safe structural delimiter (`,`, `{`, or `[`) before it. Then close
        any unclosed braces/brackets. This is a best-effort heuristic and
        may not produce semantically valid output, but is useful for
        capturing more complete error context.
        """
        if not content:
            return content

        in_string = False
        escape_next = False
        string_open_at = -1
        stack: list[str] = []

        for i, ch in enumerate(content):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"':
                if in_string:
                    in_string = False
                    string_open_at = -1
                else:
                    in_string = True
                    string_open_at = i
                continue
            if in_string:
                continue
            if ch == '{':
                stack.append('}')
            elif ch == '[':
                stack.append(']')
            elif ch in ('}', ']'):
                if stack and stack[-1] == ch:
                    stack.pop()

        if in_string and string_open_at >= 0:
            # Look for the last safe structural delimiter before the
            # unterminated string. Safe = , { [ — a colon is unsafe
            # because it would leave a key without a value. If we land
            # on a comma we strip it (and any preceding whitespace) so
            # the resulting JSON doesn't have a trailing comma.
            last_safe = -1
            last_safe_kind = ''
            for i in range(string_open_at - 1, -1, -1):
                if content[i] in (',', '{', '['):
                    last_safe = i
                    last_safe_kind = content[i]
                    break
            if last_safe >= 0 and last_safe_kind == ',':
                # Strip the trailing comma so the result is valid JSON
                repaired = content[:last_safe].rstrip()
            elif last_safe >= 0:
                repaired = content[: last_safe + 1]
            else:
                # Nothing safe before the unterminated string at all.
                # Drop the whole document.
                repaired = ""
        else:
            repaired = content

        # Strip any trailing comma (or comma+whitespace) from the close-out
        # point so the appended closing braces/brackets produce valid JSON.
        repaired = re.sub(r',\s*$', '', repaired)

        # Close any open structures
        while stack:
            repaired += stack.pop()
        return repaired

    @staticmethod
    def _repair_json(content: str) -> str:
        """
        Attempts to repair common minor JSON syntax errors like trailing commas
        and single quotes around keys/values.
        """
        if not content:
            return ""
        
        # 1. Strip trailing commas before closing braces or brackets
        content = re.sub(r',\s*([\}\]])', r'\1', content)
        
        # 2. Try parsing to see if it is already valid
        try:
            json.loads(content)
            return content
        except json.JSONDecodeError:
            pass
            
        # 3. Handle single quotes for keys (e.g. 'key': -> "key":)
        content = re.sub(r"'\s*([a-zA-Z0-9_-]+)\s*'\s*:", r'"\1":', content)
        
        # 4. Handle single quotes for string values (e.g. : 'value' -> : "value")
        def _replace_val(match):
            val = match.group(1)
            # Escape double quotes since they will be wrapped in double quotes now
            val = val.replace('"', r'\"')
            # Unescape single quotes
            val = val.replace(r"\'", "'")
            return f': "{val}"'
            
        content = re.sub(r":\s*'([^'\\]*(?:\\.[^'\\]*)*)'", _replace_val, content)

        # 5. Try parsing again; if it still fails, attempt to fix unescaped double quotes inside values
        try:
            json.loads(content)
            return content
        except json.JSONDecodeError:
            pass

        def _fix_unescaped_line_quotes(line: str) -> str:
            # Match standard JSON field line: `"key": "..."` or `"..."` with possible trailing comma
            m = re.match(r'^(\s*"(?:[^"\\]|\\.)+"\s*:\s*")(.*)("[\s,]*)$', line)
            if m:
                prefix, val, suffix = m.group(1), m.group(2), m.group(3)
                if '"' in val:
                    # Escape any double quotes that are not already preceded by backslash
                    escaped_val = re.sub(r'(?<!\\)"', r'\"', val)
                    return f"{prefix}{escaped_val}{suffix}"
            return line

        lines = content.splitlines(keepends=True)
        content = "".join(_fix_unescaped_line_quotes(l) for l in lines)
        
        return content

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
    async def _append_generation_log_async(adventure_id: Optional[str], log_type: str, content: str, image_url: Optional[str] = None):
        """Append a status, thinking, or image generation log to the adventure template's generation_logs list."""
        if not adventure_id:
            return
        try:
            from backend.core.database import AsyncSessionLocal
            from backend.models.adventure_template import AdventureTemplate
            from sqlalchemy import select
            import datetime

            async with AsyncSessionLocal() as db:
                res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == adventure_id))
                adv = res.scalars().first()
                if adv:
                    logs = list(adv.generation_logs or [])
                    logs.append({
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "type": log_type,
                        "content": content,
                        "image_url": image_url
                    })
                    adv.generation_logs = logs
                    await db.commit()
        except Exception as e:
            logger.warning("Failed to append generation log: %s", e)

    @staticmethod
    def normalize_voice_tags(text: str) -> str:
        """
        Normalizes voice/emotion tags at the beginning of the text to bracketed format [tag]
        and removes any unnecessary newlines between the tag and the narration text.
        """
        if not text:
            return text

        # Try matching bracketed first
        m = BRACKETED_RE.match(text)
        if m:
            tag = m.group("tag")
            rest = m.group("rest")
            return f"[{tag.lower()}] {rest.lstrip()}".strip()

        # Try matching unbracketed followed by line boundary
        m = UNBRACKETED_RE.match(text)
        if m:
            tag = m.group("tag")
            rest = m.group("rest")
            return f"[{tag.lower()}] {rest.lstrip()}".strip()

        return text

    @staticmethod
    async def _clean_stream_voice_tags(stream):
        """Async generator that buffers the start of the stream and normalizes voice tags."""
        buffer = ""
        prefix_processed = False
        last_chunk = None

        async for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except (AttributeError, IndexError, TypeError):
                delta = None

            if not isinstance(delta, str) or not delta:
                yield chunk
                continue

            if prefix_processed:
                yield chunk
                continue

            buffer += delta
            last_chunk = chunk

            if len(buffer) >= 100:
                normalized = GameMasterLLM.normalize_voice_tags(buffer)
                try:
                    chunk.choices[0].delta.content = normalized
                except Exception:
                    try:
                        delta_obj = chunk.choices[0].delta
                        if hasattr(delta_obj, "model_copy"):
                            new_delta = delta_obj.model_copy(update={"content": normalized})
                        else:
                            new_delta = delta_obj.copy(update={"content": normalized})
                        chunk.choices[0].delta = new_delta
                    except Exception as e:
                        logger.warning("Failed to modify streaming chunk content: %s", e)
                yield chunk
                prefix_processed = True

        if not prefix_processed and last_chunk is not None:
            normalized = GameMasterLLM.normalize_voice_tags(buffer)
            try:
                last_chunk.choices[0].delta.content = normalized
            except Exception:
                try:
                    delta_obj = last_chunk.choices[0].delta
                    if hasattr(delta_obj, "model_copy"):
                        new_delta = delta_obj.model_copy(update={"content": normalized})
                    else:
                        new_delta = delta_obj.copy(update={"content": normalized})
                    last_chunk.choices[0].delta = new_delta
                except Exception as e:
                    logger.warning("Failed to modify streaming chunk content: %s", e)
            yield last_chunk

    @staticmethod
    async def _clean_stream_thinking(stream):
        """Async generator that strips <think>...</think> blocks from stream chunks on-the-fly."""
        in_think = False
        buffer = ""
        
        async for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except (AttributeError, IndexError, TypeError):
                delta = None
                
            if not isinstance(delta, str) or not delta:
                yield chunk
                continue
                
            buffer += delta
            cleaned_delta = ""
            
            while buffer:
                if not in_think:
                    think_idx = buffer.find("<think>")
                    if think_idx != -1:
                        cleaned_delta += buffer[:think_idx]
                        in_think = True
                        buffer = buffer[think_idx + 7:]
                    else:
                        partial_match = False
                        for i in range(1, 7):
                            tag_part = "<think"[:i]
                            if buffer.endswith(tag_part):
                                keep_len = len(buffer) - i
                                cleaned_delta += buffer[:keep_len]
                                buffer = buffer[keep_len:]
                                partial_match = True
                                break
                        if not partial_match:
                            cleaned_delta += buffer
                            buffer = ""
                else:
                    end_idx = buffer.find("</think>")
                    if end_idx != -1:
                        in_think = False
                        buffer = buffer[end_idx + 8:]
                    else:
                        partial_match = False
                        for i in range(1, 8):
                            tag_part = "</think"[:i]
                            if buffer.endswith(tag_part):
                                buffer = buffer[-i:]
                                partial_match = True
                                break
                        if not partial_match:
                            buffer = ""
            
            try:
                chunk.choices[0].delta.content = cleaned_delta
            except Exception:
                try:
                    delta_obj = chunk.choices[0].delta
                    if hasattr(delta_obj, "model_copy"):
                        new_delta = delta_obj.model_copy(update={"content": cleaned_delta})
                    else:
                        new_delta = delta_obj.copy(update={"content": cleaned_delta})
                    chunk.choices[0].delta = new_delta
                except Exception as e:
                    logger.warning("Failed to modify streaming chunk content: %s", e)
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

        nested = provider_specific.get("reasoning_content") if isinstance(provider_specific, dict) else None
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
                "1", "true", "yes", "on", "enabled",
                "0", "false", "no", "off", "disabled", "", "none", "null",
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

    def __init__(self, user: User, provider: str = "openai", model_category: str = "small"):
        """
        Initialize the router for a specific user, provider and model category (small/complex).
        """
        self.user = user
        self.provider = (provider or "openai").lower()
        self.api_key = None
        self.api_base = None
        
        llm_settings = self.user.llm_settings or {}
        
        if model_category == "generator":
            prefix = "generator_"
        elif model_category == "complex":
            prefix = "complex_"
        else:
            prefix = "small_"

        from backend.core.config import settings
        if model_category == "generator":
            self.request_timeout = self._coerce_int(
                getattr(settings, "WORLDBUILDING_TIMEOUT", settings.INTELLIGENCE_TIMEOUT),
                default=settings.INTELLIGENCE_TIMEOUT,
            )
        else:
            self.request_timeout = self._coerce_int(
                settings.INTELLIGENCE_TIMEOUT,
                default=settings.INTELLIGENCE_TIMEOUT,
            )
        self.kimi_api_base = (getattr(settings, "KIMI_API_BASE", "https://api.moonshot.ai/v1") or "https://api.moonshot.ai/v1").rstrip("/")
        self.minimax_api_base = (getattr(settings, "MINIMAX_API_BASE", "https://api.minimax.io/v1") or "https://api.minimax.io/v1").rstrip("/")
        
        # Pull granular settings with fallbacks to global/legacy names.
        # Thinking must stay disabled unless explicitly configured truthy.
        enable_thinking_key = f"{prefix}enable_thinking"
        raw_enable_thinking = llm_settings.get(enable_thinking_key)
        if raw_enable_thinking is None:
            enable_thinking_key = "enable_thinking"
            raw_enable_thinking = llm_settings.get(enable_thinking_key)

        if raw_enable_thinking is not None and not self._is_supported_bool_value(raw_enable_thinking):
            logger.warning(
                "Invalid thinking setting '%s'=%r for user '%s'. Falling back to False.",
                enable_thinking_key,
                raw_enable_thinking,
                getattr(self.user, "username", "unknown"),
            )
            self.enable_thinking = False
        else:
            self.enable_thinking = self._coerce_bool(raw_enable_thinking, default=False)

        raw_max_thinking_tokens = llm_settings.get(f"{prefix}max_thinking_tokens")
        if raw_max_thinking_tokens is None:
            raw_max_thinking_tokens = llm_settings.get("max_thinking_tokens")
        self.max_thinking_tokens = self._coerce_int(raw_max_thinking_tokens, default=1024)

        raw_max_tokens = llm_settings.get(f"{prefix}max_tokens")
        if raw_max_tokens is None:
            raw_max_tokens = llm_settings.get("max_tokens")
        
        if model_category == "generator":
            default_max_tokens = self.DEFAULT_GENERATOR_MAX_TOKENS
        elif model_category == "complex":
            default_max_tokens = self.DEFAULT_COMPLEX_MAX_TOKENS
        else:
            default_max_tokens = self.DEFAULT_SMALL_MAX_TOKENS
            
        self.max_tokens = self._coerce_int(raw_max_tokens, default=default_max_tokens)

        # OpenRouter provider routing preferences
        raw_openrouter_provider = llm_settings.get(f"{prefix}openrouter_provider")
        if raw_openrouter_provider is None:
            raw_openrouter_provider = llm_settings.get("openrouter_provider")
        self.openrouter_provider = (raw_openrouter_provider or "").strip()

        if self.provider == "ollama":
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
        normalized = (model or "").strip()
        if not normalized:
            raise ValueError(f"No model configured for provider '{self.provider}'.")

        if self.provider == "ollama":
            return normalized

        if self.provider == "google" or self.provider == "gemini":
            # LiteLLM expects 'gemini/...' for Google Gemini models.
            if not normalized.startswith("gemini/"):
                return f"gemini/{normalized}"
            return normalized

        if self.provider == "openrouter":
            # OpenRouter model ids often require provider prefixes (e.g. openai/gpt-5-mini).
            # Only strip an optional leading openrouter/ wrapper if present.
            if normalized.lower().startswith("openrouter/"):
                return normalized.split("/", 1)[1].strip()
            return normalized

        if self.provider == "anthropic":
            # Ensure Anthropic requests cannot be misrouted through OpenAI-compatible defaults.
            if normalized.startswith("anthropic/"):
                return normalized
            return f"anthropic/{normalized}"

        if self.provider == "kimi":
            # Kimi (Moonshot) uses an OpenAI-compatible endpoint and expects raw model ids.
            if normalized.lower().startswith("kimi/"):
                return normalized.split("/", 1)[1].strip()
            return normalized

        if self.provider == "minimax":
            # MiniMax uses an OpenAI-compatible endpoint and expects raw model ids.
            if normalized.lower().startswith("minimax/"):
                return normalized.split("/", 1)[1].strip()
            return normalized

        if "/" in normalized:
            return normalized.split("/", 1)[1].strip()

        return normalized
    
    def _apply_thinking_settings(self, kwargs: dict) -> None:
        """Inject thinking parameters based on user settings and provider."""
        # MiniMax defaults to thinking-on server-side, so we must explicitly opt-out
        # when the user has not enabled thinking in their settings.
        if self.provider == "minimax":
            kwargs["thinking"] = (
                {"type": "adaptive"}
                if self.enable_thinking
                else {"type": "disabled"}
            )
            return

        if not self.enable_thinking:
            return

        # LiteLLM maps 'thinking' to provider-specific params (budget_tokens for Anthropic, etc.)
        kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": self.max_thinking_tokens
        }

    def _apply_openrouter_provider_routing(self, kwargs: dict) -> None:
        """Inject provider routing ordering into OpenRouter requests if configured."""
        if self.provider != "openrouter" and not (
            isinstance(self.api_key, str) and self.api_key.startswith("sk-or-v1")
        ):
            return

        if not self.openrouter_provider:
            return

        providers = [p.strip() for p in self.openrouter_provider.split(",") if p.strip()]
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
            {"role": "user", "content": user_prompt}
        ]
        
        normalized_model = self._normalize_model(model)

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "max_tokens": self.max_tokens + (self.max_thinking_tokens if self.enable_thinking else 0),
        }
        self._apply_thinking_settings(kwargs)

        if self.provider == "ollama":
            self._validate_ollama_model(model)
            kwargs["api_base"] = self.api_base
            kwargs["custom_llm_provider"] = "ollama"
        else:
            kwargs["api_key"] = self.api_key
            if self.provider == "openrouter":
                kwargs["custom_llm_provider"] = "openrouter"
            elif self.provider == "openai":
                kwargs["custom_llm_provider"] = "openai"
            elif self.provider == "anthropic":
                kwargs["custom_llm_provider"] = "anthropic"
                kwargs["api_base"] = "https://api.anthropic.com"
            elif self.provider == "deepseek":
                kwargs["custom_llm_provider"] = "deepseek"
                kwargs["api_base"] = "https://api.deepseek.com"
            elif self.provider == "kimi":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.kimi_api_base
            elif self.provider == "minimax":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.minimax_api_base
        
        # Auto-detect OpenRouter keys (only when no other OpenAI-compatible provider is explicitly set)
        openai_compatible_providers = ("kimi", "minimax", "deepseek")
        if (
            self.provider != "ollama"
            and self.provider not in openai_compatible_providers
            and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter")
        ):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"

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
            {"role": "user", "content": user_prompt}
        ]
        
        normalized_model = self._normalize_model(model)

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "max_tokens": self.max_tokens + (self.max_thinking_tokens if self.enable_thinking else 0),
        }
        self._apply_thinking_settings(kwargs)

        if self.provider == "ollama":
            self._validate_ollama_model(model)
            kwargs["api_base"] = self.api_base
            kwargs["custom_llm_provider"] = "ollama"
        else:
            kwargs["api_key"] = self.api_key
            if self.provider == "openrouter":
                kwargs["custom_llm_provider"] = "openrouter"
            elif self.provider == "openai":
                kwargs["custom_llm_provider"] = "openai"
            elif self.provider == "anthropic":
                kwargs["custom_llm_provider"] = "anthropic"
                kwargs["api_base"] = "https://api.anthropic.com"
            elif self.provider == "deepseek":
                kwargs["custom_llm_provider"] = "deepseek"
                kwargs["api_base"] = "https://api.deepseek.com"
            elif self.provider == "kimi":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.kimi_api_base
            elif self.provider == "minimax":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.minimax_api_base
        
        # Auto-detect OpenRouter keys (only when no other OpenAI-compatible provider is explicitly set)
        openai_compatible_providers = ("kimi", "minimax", "deepseek")
        if (
            self.provider != "ollama"
            and self.provider not in openai_compatible_providers
            and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter")
        ):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"

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
        adventure_id: Optional[str] = None,
        game_id: Optional[str] = None,
        operation: Optional[str] = None,
        phase: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """
        Streams a free narrative task.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        normalized_model = self._normalize_model(model)

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "max_tokens": self.max_tokens + (self.max_thinking_tokens if self.enable_thinking else 0),
            "stream": True,
        }
        self._apply_thinking_settings(kwargs)

        if self.provider == "ollama":
            self._validate_ollama_model(model)
            kwargs["api_base"] = self.api_base
            kwargs["custom_llm_provider"] = "ollama"
        else:
            kwargs["api_key"] = self.api_key
            if self.provider == "openrouter":
                kwargs["custom_llm_provider"] = "openrouter"
            elif self.provider == "openai":
                kwargs["custom_llm_provider"] = "openai"
            elif self.provider == "anthropic":
                kwargs["custom_llm_provider"] = "anthropic"
                kwargs["api_base"] = "https://api.anthropic.com"
            elif self.provider == "deepseek":
                kwargs["custom_llm_provider"] = "deepseek"
                kwargs["api_base"] = "https://api.deepseek.com"
            elif self.provider == "kimi":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.kimi_api_base
            elif self.provider == "minimax":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.minimax_api_base
        
        # Auto-detect OpenRouter keys (only when no other OpenAI-compatible provider is explicitly set)
        openai_compatible_providers = ("kimi", "minimax", "deepseek")
        if (
            self.provider != "ollama"
            and self.provider not in openai_compatible_providers
            and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter")
        ):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"

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

        stream = await self._acompletion_with_openrouter_fallback(kwargs)
        stream = self._clean_stream_thinking(stream)
        return self._clean_stream_voice_tags(stream)

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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        normalized_model = self._normalize_model(model)
        # Gemini and Anthropic often fail with complex Pydantic schemas in strict tool-use mode
        # Anthropic has a 24-optional-parameter limit in their grammar compiler.
        # Fallback to standard JSON mode (prompt-injected schema) for these models.
        is_gemini = "gemini" in normalized_model.lower() or self.provider == "google"
        is_anthropic = "claude" in normalized_model.lower() or self.provider == "anthropic"
        is_deepseek = "deepseek" in normalized_model.lower() or self.provider == "deepseek"
        is_kimi = "kimi" in normalized_model.lower() or "moonshot" in normalized_model.lower() or self.provider == "kimi"
        is_minimax = "minimax" in normalized_model.lower() or self.provider == "minimax"
        # Only treat as OpenRouter when the provider is explicitly openrouter; key-prefix
        # detection would falsely match MiniMax/kimi/deepseek keys that also start with "sk-or-v1".
        is_openrouter = self.provider == "openrouter"

        # Many non-OpenAI providers (including DeepSeek on some platforms) do not support 
        # complex Pydantic models in response_format (structured outputs).
        # We fall back to standard JSON mode with prompt-injected schemas for these.
        # Direct Gemini (not via OpenRouter) supports response_schema perfectly and does not need fallback.
        use_json_mode_fallback = is_anthropic or is_deepseek or is_kimi or is_minimax or is_openrouter

        if use_json_mode_fallback:
            # Inject schema into prompt since we are bypassing strict tool enforcement
            schema_json = json.dumps(response_model.model_json_schema(), separators=(",", ":"))
            system_prompt += (
                f"\n\nCRITICAL: You MUST respond with a single JSON object matching this schema exactly.\n"
                f"DO NOT wrap the response in a list (no square brackets at the top level).\n"
                f"DO NOT include any markdown formatting or text outside the JSON.\n"
                f"CRITICAL: Do NOT translate the JSON key names. The JSON keys MUST be exactly identical to the schema keys in English.\n"
                f"SCHEMA:\n{schema_json}"
            )
            messages[0]["content"] = system_prompt

        allow_thinking = not use_json_mode_fallback

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "response_format": ({"type": "json_object"} if use_json_mode_fallback and not is_minimax else (None if is_minimax else response_model)),
            "max_tokens": self.max_tokens + (self.max_thinking_tokens if self.enable_thinking and allow_thinking else 0),
        }
        if kwargs.get("response_format") is None:
            kwargs.pop("response_format", None)

        if allow_thinking:
            self._apply_thinking_settings(kwargs)

        if self.provider == "ollama":
            self._validate_ollama_model(model)
            kwargs["api_base"] = self.api_base
            kwargs["custom_llm_provider"] = "ollama"
        else:
            kwargs["api_key"] = self.api_key
            if self.provider == "openrouter":
                kwargs["custom_llm_provider"] = "openrouter"
            elif self.provider == "openai":
                kwargs["custom_llm_provider"] = "openai"
            elif self.provider == "anthropic":
                kwargs["custom_llm_provider"] = "anthropic"
                kwargs["api_base"] = "https://api.anthropic.com"
            elif self.provider == "deepseek":
                kwargs["custom_llm_provider"] = "deepseek"
                kwargs["api_base"] = "https://api.deepseek.com"
            elif self.provider == "kimi":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.kimi_api_base
            elif self.provider == "minimax":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.minimax_api_base

        # Auto-detect OpenRouter keys (only when no other OpenAI-compatible provider is explicitly set)
        openai_compatible_providers = ("kimi", "minimax", "deepseek")
        if (
            self.provider != "ollama"
            and self.provider not in openai_compatible_providers
            and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter")
        ):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"

        self._apply_openrouter_provider_routing(kwargs)

        log_structured_event(
            "gm.turn.request",
            model=normalized_model,
            provider=self.provider,
            response_model=response_model.__name__,
            adventure_id=adventure_id,
            game_id=game_id,
            operation=operation,
            phase=phase,
            metadata=metadata,
        )

        response = await self._acompletion_with_openrouter_fallback(kwargs)
        
        content = response.choices[0].message.content
        if use_json_mode_fallback and (content is None or not str(content).strip()):
            response = await self._retry_blank_json_content_async(kwargs, response)
            content = response.choices[0].message.content
        
        # Log thinking/reasoning if present
        if adventure_id:
            thinking_text = self.extract_thinking(content or "", response.choices[0].message)
            if thinking_text:
                await self._append_generation_log_async(adventure_id, "thinking", thinking_text)
        
        log_llm_interaction(
            model=model,
            provider=self.provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_content=content or "",
            raw_response=response.model_dump(),
            event_type="gm.turn.response",
            adventure_id=adventure_id,
            game_id=game_id,
            operation=operation,
            phase=phase,
            metadata={
                **(metadata or {}),
                "response_model": response_model.__name__,
            },
        )
        
        finish_reason = response.choices[0].finish_reason

        if not content:
            logger.error(f"LLM returned empty content. Raw response: {response.model_dump()}")
            if finish_reason == "length":
                raise ValueError("LLM hit token limit during reasoning. Increase 'Max Tokens' in Settings.")
            raise ValueError("No content returned from LLM for complex task.")
            
        try:
            content = self.clean_thinking_tags(content)
            content = self._clean_json_string(content)
            if not content:
                logger.error("LLM returned content that was empty after JSON cleanup. Raw response: %s", response.model_dump())
                if finish_reason == "length":
                    raise ValueError("LLM hit token limit during reasoning. Increase 'Max Tokens' in Settings.")
                raise ValueError("No content returned from LLM for complex task.")
            content = self._repair_json(content)
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                if finish_reason == "length" or self._is_truncated_json(content):
                    logger.error(
                        "LLM response appears truncated. Length: %d, finish_reason: %s. Full content: %s",
                        len(content), finish_reason, content,
                    )
                    raise ValueError(
                        "LLM response was truncated (token limit). "
                        "Please increase the token limit in Settings (Intelligence) and retry."
                    ) from exc
                # Best-effort: try to close the JSON and re-parse for diagnostic purposes
                repaired = self._attempt_repair_truncated_json(content)
                if repaired != content:
                    try:
                        data = json.loads(repaired)
                        logger.warning(
                            "LLM response was malformed but could be repaired. Original length: %d.",
                            len(content),
                        )
                    except json.JSONDecodeError:
                        data = None
                else:
                    data = None
                if data is None:
                    logger.error(
                        "LLM response was not valid JSON. Length: %d, finish_reason: %s. Full content: %s",
                        len(content), finish_reason, content,
                    )
                    preview = content[:280].replace("\n", " ").strip()
                    raise ValueError(
                        f"Failed to parse LLM response as JSON. Preview: {preview}"
                    ) from exc
            if isinstance(data, list) and len(data) > 0:
                logger.warning(f"LLM returned a list for {response_model.__name__}. Taking first element.")
                data = data[0]

            if not isinstance(data, dict):
                raise ValueError(f"LLM returned {type(data).__name__} but a mapping was expected for {response_model.__name__}.")

            return response_model(**data)
        except json.JSONDecodeError as exc:
            if finish_reason == "length":
                raise ValueError(
                    "LLM response was truncated (token limit). "
                    "Please increase the token limit in Settings (Intelligence) and retry."
                ) from exc
            if self._is_truncated_json(content):
                raise ValueError(
                    "LLM response was truncated (token limit). "
                    "Please increase the token limit in Settings (Intelligence) and retry."
                ) from exc
            preview = content[:280].replace("\n", " ").strip()
            raise ValueError(f"Failed to parse LLM response as JSON. Preview: {preview}") from exc
        except ValidationError as exc:
            preview = content[:280].replace("\n", " ").strip()
            raise ValueError(
                f"LLM returned JSON that does not match expected schema {response_model.__name__}. "
                f"Preview: {preview}. Validation: {exc}"
            ) from exc

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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # litellm will translate the Pydantic model into a JSON schema 
        # for providers that support structured outputs (e.g. OpenAI).
        normalized_model = self._normalize_model(model)
        is_gemini = "gemini" in normalized_model.lower() or self.provider == "google"
        is_anthropic = "claude" in normalized_model.lower() or self.provider == "anthropic"
        is_deepseek = "deepseek" in normalized_model.lower() or self.provider == "deepseek"
        is_kimi = "kimi" in normalized_model.lower() or "moonshot" in normalized_model.lower() or self.provider == "kimi"
        is_minimax = "minimax" in normalized_model.lower() or self.provider == "minimax"
        # Only treat as OpenRouter when the provider is explicitly openrouter; key-prefix
        # detection would falsely match MiniMax/kimi/deepseek keys that also start with "sk-or-v1".
        is_openrouter = self.provider == "openrouter"

        # Direct Gemini (not via OpenRouter) supports response_schema perfectly and does not need fallback.
        use_json_mode_fallback = is_anthropic or is_deepseek or is_kimi or is_minimax or is_openrouter

        if use_json_mode_fallback:
            # Inject schema into prompt since we are bypassing strict enforcement
            schema_json = json.dumps(response_model.model_json_schema(), separators=(",", ":"))
            system_prompt += (
                f"\n\nCRITICAL: You MUST respond with a single JSON object matching this schema exactly.\n"
                f"DO NOT wrap the response in a list (no square brackets at the top level).\n"
                f"DO NOT include any markdown formatting or text outside the JSON.\n"
                f"CRITICAL: Do NOT translate the JSON key names. The JSON keys MUST be exactly identical to the schema keys in English.\n"
                f"SCHEMA:\n{schema_json}"
            )
            messages[0]["content"] = system_prompt

        allow_thinking = not use_json_mode_fallback

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "response_format": ({"type": "json_object"} if use_json_mode_fallback and not is_minimax else (None if is_minimax else response_model)),
            "max_tokens": self.max_tokens + (self.max_thinking_tokens if self.enable_thinking and allow_thinking else 0),
        }
        if kwargs.get("response_format") is None:
            kwargs.pop("response_format", None)

        if allow_thinking:
            self._apply_thinking_settings(kwargs)

        if self.provider == "ollama":
            self._validate_ollama_model(model)
            kwargs["api_base"] = self.api_base
            kwargs["custom_llm_provider"] = "ollama"
        else:
            kwargs["api_key"] = self.api_key
            if self.provider == "openrouter":
                # Route through OpenAI-compatible chat endpoint to avoid provider-specific
                # request fields that some local dependency combos reject (e.g. usage).
                kwargs["custom_llm_provider"] = "openrouter"
            elif self.provider == "openai":
                kwargs["custom_llm_provider"] = "openai"
            elif self.provider == "anthropic":
                kwargs["custom_llm_provider"] = "anthropic"
                kwargs["api_base"] = "https://api.anthropic.com"
            elif self.provider == "deepseek":
                kwargs["custom_llm_provider"] = "deepseek"
                kwargs["api_base"] = "https://api.deepseek.com"
            elif self.provider == "kimi":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.kimi_api_base
            elif self.provider == "minimax":
                kwargs["custom_llm_provider"] = "openai"
                kwargs["api_base"] = self.minimax_api_base

        # Auto-detect OpenRouter keys or provider
        # Auto-detect OpenRouter keys (only when no other OpenAI-compatible provider is explicitly set)
        openai_compatible_providers = ("kimi", "minimax", "deepseek")
        if (
            self.provider != "ollama"
            and self.provider not in openai_compatible_providers
            and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter")
        ):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"

        self._apply_openrouter_provider_routing(kwargs)

        log_structured_event(
            "gm.turn.request",
            model=normalized_model,
            provider=self.provider,
            response_model=response_model.__name__,
            adventure_id=adventure_id,
            game_id=game_id,
            operation=operation,
            phase=phase,
            metadata=metadata,
        )

        response = self._completion_with_openrouter_fallback(kwargs)
        
        content = response.choices[0].message.content
        if use_json_mode_fallback and (content is None or not str(content).strip()):
            response = self._retry_blank_json_content(kwargs, response)
            content = response.choices[0].message.content
        
        log_llm_interaction(
            model=model,
            provider=self.provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_content=content or "",
            raw_response=response.model_dump(),
            event_type="gm.turn.response",
            adventure_id=adventure_id,
            game_id=game_id,
            operation=operation,
            phase=phase,
            metadata={
                **(metadata or {}),
                "response_model": response_model.__name__,
            },
        )
        
        finish_reason = response.choices[0].finish_reason

        if not content:
            logger.error(f"LLM returned empty content. Raw response: {response.model_dump()}")
            if finish_reason == "length":
                raise ValueError("LLM hit token limit during reasoning. Increase 'Max Tokens' in Settings.")
            raise ValueError("No content returned from LLM for complex task.")
            
        try:
            content = self.clean_thinking_tags(content)
            content = self._clean_json_string(content)
            if not content:
                logger.error("LLM returned content that was empty after JSON cleanup. Raw response: %s", response.model_dump())
                if finish_reason == "length":
                    raise ValueError("LLM hit token limit during reasoning. Increase 'Max Tokens' in Settings.")
                raise ValueError("No content returned from LLM for complex task.")
            content = self._repair_json(content)
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                if finish_reason == "length" or self._is_truncated_json(content):
                    logger.error(
                        "LLM response appears truncated. Length: %d, finish_reason: %s. Full content: %s",
                        len(content), finish_reason, content,
                    )
                    raise ValueError(
                        "LLM response was truncated (token limit). "
                        "Please increase the token limit in Settings (Intelligence) and retry."
                    ) from exc
                repaired = self._attempt_repair_truncated_json(content)
                if repaired != content:
                    try:
                        data = json.loads(repaired)
                        logger.warning(
                            "LLM response was malformed but could be repaired. Original length: %d.",
                            len(content),
                        )
                    except json.JSONDecodeError:
                        data = None
                else:
                    data = None
                if data is None:
                    logger.error(
                        "LLM response was not valid JSON. Length: %d, finish_reason: %s. Full content: %s",
                        len(content), finish_reason, content,
                    )
                    preview = content[:280].replace("\n", " ").strip()
                    raise ValueError(
                        f"Failed to parse LLM response as JSON. Preview: {preview}"
                    ) from exc
            return response_model(**data)
        except json.JSONDecodeError as exc:
            if finish_reason == "length":
                raise ValueError(
                    "LLM response was truncated (token limit). "
                    "Please increase the token limit in Settings (Intelligence) and retry."
                ) from exc
            if self._is_truncated_json(content):
                raise ValueError(
                    "LLM response was truncated (token limit). "
                    "Please increase the token limit in Settings (Intelligence) and retry."
                ) from exc
            preview = content[:280].replace("\n", " ").strip()
            raise ValueError(f"Failed to parse LLM response as JSON. Preview: {preview}") from exc
        except ValidationError as exc:
            preview = content[:280].replace("\n", " ").strip()
            raise ValueError(
                f"LLM returned JSON that does not match expected schema {response_model.__name__}. "
                f"Preview: {preview}. Validation: {exc}"
            ) from exc
