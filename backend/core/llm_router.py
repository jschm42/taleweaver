import json
import logging
import re
from typing import Any, Optional, TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from backend.core.llm_logger import log_llm_interaction, log_structured_event
from backend.core.security import encryption_util
from backend.models.user import User

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

class GameMasterLLM:
    DEFAULT_SMALL_MAX_TOKENS = 4096
    DEFAULT_COMPLEX_MAX_TOKENS = 8192
    DEFAULT_GENERATOR_MAX_TOKENS = 16384


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
        """Call LiteLLM completion and retry once for OpenRouter provider-order mismatches."""
        try:
            return self._get_litellm().completion(**kwargs, request_timeout=self.request_timeout)
        except Exception as exc:
            if self.provider != "openrouter":
                raise

            available_providers = self._extract_openrouter_available_providers(exc)
            if not available_providers:
                raise

            logger.warning(
                "OpenRouter provider mismatch for model '%s'. Retrying with provider order: %s",
                kwargs.get("model"),
                ",".join(available_providers),
            )
            retry_kwargs = self._retry_kwargs_with_openrouter_provider_order(kwargs, available_providers)
            return self._get_litellm().completion(**retry_kwargs, request_timeout=self.request_timeout)

    async def _acompletion_with_openrouter_fallback(self, kwargs: dict):
        """Async variant of completion retry for OpenRouter provider-order mismatches."""
        try:
            logger.info(
                "GameMasterLLM calling LLM for user %s with model %s", self.user.id, kwargs.get("model")
            )
            return await self._get_litellm().acompletion(**kwargs, request_timeout=self.request_timeout)
        except Exception as exc:
            if self.provider != "openrouter":
                raise

            available_providers = self._extract_openrouter_available_providers(exc)
            if not available_providers:
                raise

            logger.warning(
                "OpenRouter provider mismatch for model '%s'. Retrying with provider order: %s",
                kwargs.get("model"),
                ",".join(available_providers),
            )
            retry_kwargs = self._retry_kwargs_with_openrouter_provider_order(kwargs, available_providers)

            logger.info(
                "GameMasterLLM calling LLM (Fallback) for user %s with model %s", self.user.id, kwargs.get("model")
            )
            return await self._get_litellm().acompletion(**retry_kwargs, request_timeout=self.request_timeout)

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

        if "/" in normalized:
            return normalized.split("/", 1)[1].strip()

        return normalized
    
    def _apply_thinking_settings(self, kwargs: dict) -> None:
        """Inject thinking parameters if enabled in user settings."""
        if not self.enable_thinking:
            return
            
        # LiteLLM maps 'thinking' to provider-specific params (budget_tokens for Anthropic, etc.)
        kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": self.max_thinking_tokens
        }

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
        
        # Auto-detect OpenRouter keys or provider
        if self.provider != "ollama" and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter"):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"
        
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
        
        if self.provider != "ollama" and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter"):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"
        
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
        
        if self.provider != "ollama" and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter"):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"
        
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

        return await self._acompletion_with_openrouter_fallback(kwargs)

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

        if is_gemini or is_anthropic:
            # Inject schema into prompt since we are bypassing strict tool enforcement
            schema_json = json.dumps(response_model.model_json_schema(), indent=2)
            system_prompt += (
                f"\n\nCRITICAL: You MUST respond with a single JSON object matching this schema exactly.\n"
                f"DO NOT wrap the response in a list (no square brackets at the top level).\n"
                f"DO NOT include any markdown formatting or text outside the JSON.\n"
                f"SCHEMA:\n{schema_json}"
            )
            messages[0]["content"] = system_prompt

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "response_format": {"type": "json_object"} if (is_gemini or is_anthropic) else response_model,
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

        if self.provider != "ollama" and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter"):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"

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
            content = self._clean_json_string(content)
            data = json.loads(content)
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

        if is_gemini:
            # Inject schema into prompt since we are bypassing strict enforcement
            schema_json = json.dumps(response_model.model_json_schema(), indent=2)
            system_prompt += (
                f"\n\nCRITICAL: You MUST respond with a single JSON object matching this schema exactly.\n"
                f"DO NOT wrap the response in a list (no square brackets at the top level).\n"
                f"DO NOT include any markdown formatting or text outside the JSON.\n"
                f"SCHEMA:\n{schema_json}"
            )
            messages[0]["content"] = system_prompt

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "response_format": {"type": "json_object"} if is_gemini else response_model,
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

        # Auto-detect OpenRouter keys or provider
        if self.provider != "ollama" and (self.api_key.startswith("sk-or-v1") or self.provider == "openrouter"):
            kwargs["api_base"] = "https://openrouter.ai/api/v1"

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
            content = self._clean_json_string(content)
            data = json.loads(content)
            return response_model(**data)
        except json.JSONDecodeError as exc:
            if finish_reason == "length":
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
