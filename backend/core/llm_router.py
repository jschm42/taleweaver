import json
import litellm
from pydantic import BaseModel
from typing import TypeVar, Type

from backend.models.user import User
from backend.core.security import encryption_util

T = TypeVar("T", bound=BaseModel)

class GameMasterLLM:
    def __init__(self, user: User, provider: str = "openai"):
        """
        Initialize the router for a specific user and their preferred provider.
        The `provider` prefix is used to locate the specific key in the user's config.
        """
        self.user = user
        self.provider = provider
        self.api_key = self._get_decrypted_key(provider)

    def _get_decrypted_key(self, provider: str) -> str:
        if not self.user.encrypted_api_keys or provider not in self.user.encrypted_api_keys:
            raise ValueError(f"No API key configured for provider: {provider}")
        
        encrypted_key = self.user.encrypted_api_keys[provider]
        return encryption_util.decrypt_key(encrypted_key)

    def execute_simple_task(self, system_prompt: str, user_prompt: str, model: str) -> str:
        """
        Free narrative task (Hallucination Mode).
        Provides a plain text output from the model.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = litellm.completion(
            model=model,
            messages=messages,
            api_key=self.api_key
        )
        
        return response.choices[0].message.content or ""

    def execute_complex_task(self, system_prompt: str, user_prompt: str, response_model: Type[T], model: str) -> T:
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
        response = litellm.completion(
            model=model,
            messages=messages,
            api_key=self.api_key,
            response_format=response_model
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("No content returned from LLM for complex task.")
            
        try:
            data = json.loads(content)
            return response_model(**data)
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse LLM response as JSON: {content}")
