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
    {"id": "black_forest_labs", "name": "Black Forest Labs (FLUX)"},
    {"id": "google", "name": "Google Gemini (Imagen)"},
    {"id": "ollama", "name": "Ollama (Local)"},
]

PREDEFINED_LLM_MODELS = {
    "openai": ["gpt-4o-mini", "gpt-4o", "o1-mini", "o3-mini"],
    "google": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
    "openrouter": ["openai/gpt-5-nano","openai/gpt-5-mini", "openai/gpt-5-chat",
                   "openai/gpt-4o"],
    "anthropic": ["claude-3-5-sonnvvet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"],
    "ollama": ["llama3.2", "qwen2.5", "mistral", "phi3"],
}

PREDEFINED_IMAGE_MODELS = {
    "openai": ["gpt-image-1-mini","gpt-image-1.5", "gpt-image-2"],
    "openrouter": ["black-forest-labs/flux.2-klein-4b", "sourceful/riverflow-v2-fast",
     "openai/gpt-5.4-image-2", "google/gemini-3.1-flash-image-preview" ,"openai/gpt-5-image-mini"],
    "black_forest_labs": ["flux-2-klein-4b", "flux-2-klein-9b", "flux-dev", "flux-pro", "flux-pro-1.1", "flux-2-flex", "flux-2-pro", "flux-2-max"],
    "google": ["gemini-3.1-flash-image-preview", "gemini-2.5-flash-image", "imagen-4.0-fast-generate-001", "imagen-4.0-generate-001"],
    "ollama": ["x/flux2-klein", "stable-diffusion-v1-5"],
}
