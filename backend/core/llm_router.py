import json
import logging
import re
from pydantic import BaseModel
from typing import TypeVar, Type, Any, Optional
import litellm

from backend.models.user import User
from backend.core.security import encryption_util
from backend.core.llm_logger import log_llm_interaction, log_structured_event

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

class GameMasterLLM:
    DEFAULT_SMALL_MAX_TOKENS = 4096
    DEFAULT_COMPLEX_MAX_TOKENS = 8192


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
        from backend.core.config import settings
        try:
            return self._get_litellm().completion(**kwargs, request_timeout=settings.INTELLIGENCE_TIMEOUT)
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
            return self._get_litellm().completion(**retry_kwargs, request_timeout=settings.INTELLIGENCE_TIMEOUT)

    async def _acompletion_with_openrouter_fallback(self, kwargs: dict):
        """Async variant of completion retry for OpenRouter provider-order mismatches."""
        from backend.core.config import settings
        try:
            logger.info(
                "GameMasterLLM calling LLM for user %s with model %s", self.user.id, kwargs.get("model")
            )
            return await self._get_litellm().acompletion(**kwargs, request_timeout=settings.INTELLIGENCE_TIMEOUT)
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
            return await self._get_litellm().acompletion(**retry_kwargs, request_timeout=settings.INTELLIGENCE_TIMEOUT)

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
        prefix = "small_" if model_category == "small" else "complex_"
        
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
        default_max_tokens = (
            self.DEFAULT_SMALL_MAX_TOKENS
            if model_category == "small"
            else self.DEFAULT_COMPLEX_MAX_TOKENS
        )
        self.max_tokens = self._coerce_int(raw_max_tokens, default=default_max_tokens)

        if self.provider == "ollama":
            self.api_base = (llm_settings.get("ollama_url") or "http://localhost:11434").rstrip("/")
        else:
            self.api_key = self._get_decrypted_key(self.provider)
            
        self.model_category = model_category
        logger.info(f"Router initialized: category={model_category}, provider={self.provider}, thinking={self.enable_thinking}, max_tokens={self.max_tokens}")

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
        response_model: Type[T],
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

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "response_format": response_model,
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

    def execute_complex_task(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
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

        kwargs = {
            "model": normalized_model,
            "messages": messages,
            "response_format": response_model,
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
