import json
import importlib
from pydantic import BaseModel
from typing import TypeVar, Type, Any

from backend.models.user import User
from backend.core.security import encryption_util
from backend.core.llm_logger import log_llm_interaction, log_structured_event

T = TypeVar("T", bound=BaseModel)

class GameMasterLLM:
    _litellm_module: Any = None

    @classmethod
    def _get_litellm(cls) -> Any:
        if cls._litellm_module is None:
            cls._litellm_module = importlib.import_module("litellm")
            cls._litellm_module.drop_params = True
            # Prevents litellm from passing 'usage' to OpenAI-compatible endpoints that don't support it
            cls._litellm_module.add_usage = False
        return cls._litellm_module

    def __init__(self, user: User, provider: str = "openai"):
        """
        Initialize the router for a specific user and their preferred provider.
        The `provider` prefix is used to locate the specific key in the user's config.
        """
        self.user = user
        self.provider = (provider or "openai").lower()
        self.api_key = None
        self.api_base = None
        if self.provider == "ollama":
            llm_settings = self.user.llm_settings or {}
            self.api_base = (llm_settings.get("ollama_url") or "http://localhost:11434").rstrip("/")
        else:
            self.api_key = self._get_decrypted_key(self.provider)

    def _normalize_model(self, model: str) -> str:
        """Return a LiteLLM-friendly model slug for the configured provider."""
        normalized = (model or "").strip()
        if not normalized:
            raise ValueError(f"No model configured for provider '{self.provider}'.")

        if self.provider == "ollama":
            return normalized

        if "/" in normalized:
            return normalized.split("/", 1)[1].strip()

        return normalized

    def _get_decrypted_key(self, provider: str) -> str:
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
        adventure_id: str | None = None,
        game_id: str | None = None,
        operation: str | None = None,
        phase: str | None = None,
        metadata: dict[str, Any] | None = None,
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
        }

        if self.provider == "ollama":
            self._validate_ollama_model(model)
            kwargs["api_base"] = self.api_base
            kwargs["custom_llm_provider"] = "ollama"
        else:
            kwargs["api_key"] = self.api_key
        
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

        response = self._get_litellm().completion(**kwargs)
        
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

    def execute_complex_task(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        model: str,
        *,
        adventure_id: str | None = None,
        game_id: str | None = None,
        operation: str | None = None,
        phase: str | None = None,
        metadata: dict[str, Any] | None = None,
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
            "response_format": response_model
        }

        if self.provider == "ollama":
            self._validate_ollama_model(model)
            kwargs["api_base"] = self.api_base
            kwargs["custom_llm_provider"] = "ollama"
        else:
            kwargs["api_key"] = self.api_key

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

        response = self._get_litellm().completion(**kwargs)
        
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
        
        if not content:
            raise ValueError("No content returned from LLM for complex task.")
            
        try:
            data = json.loads(content)
            return response_model(**data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse LLM response as JSON: {content}") from exc
