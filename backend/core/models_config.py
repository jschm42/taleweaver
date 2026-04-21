"""
Centralized model and provider configurations for TaleWeaver.
"""

LLM_PROVIDERS = [
    {"id": "openai", "name": "OpenAI"},
    {"id": "google", "name": "Google Gemini"},
    {"id": "openrouter", "name": "OpenRouter"},
    {"id": "anthropic", "name": "Anthropic"},
    {"id": "ollama", "name": "Ollama (Local)"},
]

IMAGE_PROVIDERS = [
    {"id": "openai", "name": "OpenAI (DALL-E)"},
    {"id": "openrouter", "name": "OpenRouter (Various)"},
    {"id": "midjourney", "name": "Midjourney (via Proxy)"},
    {"id": "black_forest_labs", "name": "Black Forest Labs (FLUX)"},
    {"id": "ollama", "name": "Ollama (Local)"},
]

PREDEFINED_LLM_MODELS = {
    "openai": ["gpt-4o-mini", "gpt-4o", "o1-mini", "o3-mini"],
    "google": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
    "openrouter": ["openai/gpt-5-mini", "openai/gpt-5-chat"],
    "anthropic": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"],
    "ollama": ["llama3.2", "qwen2.5", "mistral", "phi3"],
}

PREDEFINED_IMAGE_MODELS = {
    "openai": ["dall-e-3", "dall-e-2"],
    "openrouter": ["black-forest-labs/flux.2-klein-4b", "openai/gpt-5-image-mini"],
    "midjourney": ["mj-v6", "mj-v6.1"],
    "black_forest_labs": ["flux-dev", "flux-pro-1.1", "flux-schnell"],
    "ollama": ["x/flux2-klein", "stable-diffusion-v1-5"],
}
