"""
Centralized model and provider configurations for TaleWeaver.
"""

LLM_PROVIDERS = [
    {"id": "openai", "name": "OpenAI"},
    {"id": "google", "name": "Google Gemini"},
    {"id": "deepseek", "name": "DeepSeek"},
    {"id": "openrouter", "name": "OpenRouter"},
    {"id": "anthropic", "name": "Anthropic"},
    {"id": "ollama", "name": "Ollama (Local, EXPERIMENTAL)"},
]

IMAGE_PROVIDERS = [
    {"id": "openai", "name": "OpenA"},
    {"id": "openrouter", "name": "OpenRouter (Various)"},
    {"id": "black_forest_labs", "name": "Black Forest Labs"},
    {"id": "google", "name": "Google Gemini"},
    {"id": "ollama", "name": "Ollama (Local, EXPERIMENTAL)"},
]

TTS_PROVIDERS = [
    {"id": "google", "name": "Google Cloud TTS"},
    {"id": "elevenlabs", "name": "ElevenLabs"},
]

PREDEFINED_LLM_MODELS = {
    "openai": ["gpt-5.4-mini", "gpt-5.3", "gpt-5.4", "gpt-5.5"],
    "google": ["gemini-3.1-pro-preview", "gemini-2.5-flash"],
    "deepseek": ["deepseek-v4-flash", "deepseek-v4-pro"],
    "openrouter": ["openai/gpt-5-mini", "openai/gpt-5-chat"],
    "anthropic": ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"],
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

PREDEFINED_TTS_MODELS = {
    "google": [
        {"id": "gemini-3.1-flash-tts-preview", "name": "Gemini 3.1 Flash TTS (Preview)"},
        {"id": "gemini-2.5-flash-preview-tts", "name": "Gemini 2.5 Flash TTS (Preview)"},
    ],
    "elevenlabs": [
        {"id": "eleven_v3", "name": "Eleven v3"},
        {"id": "eleven_multilingual_v2", "name": "Multilingual v2"},
        {"id": "eleven_flash_v2_5", "name": "Flash v2.5"},
        {"id": "eleven_flash_v2", "name": "Flash v2"},
    ]
}
