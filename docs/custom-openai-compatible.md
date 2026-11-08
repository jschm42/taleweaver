# Custom OpenAI-Compatible Endpoints

Use any hosted OpenAI-compatible provider (e.g. OpenRouter, Groq, Together, DeepInfra) or self-hosted inference server (vLLM, Ollama, llama.cpp, LM Studio, TGI) with an OpenAI-compatible Chat Completions API.

Configure OpenAI-compatible endpoints directly within the Intelligence settings cards for Pass 1 (Mechanics), Pass 2 (Narration), Worldbuilder Generator, Autonomous Play Agent, or History Compression. Each pass can either inherit the global base URL or specify its own dedicated endpoint (e.g. `http://localhost:8001/v1` for mechanics and `https://openrouter.ai/api/v1` for narration). Detection is optional: you can detect models from the endpoint's `/models` route or enter any custom model ID manually.

For speech, see [OpenAI-Compatible Speech (TTS)](openai-compatible-tts.md); it uses the same Base URL rules and vault key.

## Authentication and headers

Store optional API keys in the Provider Vault under **OpenAI-Compatible API Key**. When pointing an OpenAI-compatible endpoint to OpenRouter (`https://openrouter.ai/api/v1`) without a custom OpenAI key, TaleWeaver automatically falls back to your saved OpenRouter vault key. TaleWeaver sends the key as `Authorization: Bearer <key>`. Endpoints that do not require authentication can leave the vault key empty. TaleWeaver sets standard headers for hosted gateways.

## Local networking

For loopback or LAN endpoints, explicitly set `ALLOW_PRIVATE_NETWORK_MODELS=true` in the server environment or `.env`, then restart TaleWeaver. Custom endpoints require this explicit opt-in even though legacy local providers may allow private networks by default. A public hosted endpoint does not require the private-network opt-in. Metadata/link-local destinations and redirects are rejected even when private networking is enabled.

In Docker, `127.0.0.1` refers to the TaleWeaver container. Use `host.docker.internal` where supported, or your configured host gateway/container network address. The inference server must listen on an interface reachable from TaleWeaver.

## Structured output and limits

Structured passes that return engine state changes (Pass 1 Mechanics, Worldbuilder Generator, and Autonomous Play Agent) include the JSON schema in the prompt. **Structured output support** defaults to **Prompt only** for widest compatibility. If the endpoint and selected model support it, choose **JSON object** to request JSON syntax or **JSON schema** to send the complete schema through `response_format`. No tool-calling support is required. TaleWeaver still parses and repairs (`json_repair`) the response against the requested Pydantic schema.

**Pass 2 (Narrative & Dialogue Storyteller)** and **History Compression** generate streaming creative prose or text summaries. Because they do not output JSON payloads, structured output compatibility modes do not apply to them. Dedicated storytelling or roleplay models (such as MythoMax, Cydonia, or Llama-3-Storywriter) run without JSON schema constraints, and their **Test Model** action validates creative prose generation directly.

The model list does not establish structured-output support. An unsupported selected mode can produce a server error; use **Prompt only** when unsure. Models also need streaming Chat Completions for narrative output. Compatibility depends on the endpoint's API implementation and the model's ability to follow the task schema.

The request timeout defaults to 300 seconds and is editable up to 3600 seconds per pass. It also controls the initial and idle streaming timeouts. Existing per-pass output-token settings remain in effect; the server determines the actual context limit.
