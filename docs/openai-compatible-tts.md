# OpenAI-Compatible Speech (TTS)

The **OpenAI-Compatible** speech provider reads the story aloud with any server that implements the OpenAI speech API, `POST {base}/audio/speech`. That covers local, offline servers as well as hosted services:

| Server | Base URL | Model | Voices | Key |
|---|---|---|---|---|
| [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) (Kokoro-82M, local) | `http://127.0.0.1:8880/v1` | `kokoro` | listed by the server (`af_heart`, `bm_george`, ...) | none |
| [Speaches](https://github.com/speaches-ai/speaches), [LocalAI](https://localai.io), openedai-speech (local) | the server's `/v1` URL | per server | per server | usually none |
| [OpenAI](https://platform.openai.com/docs/guides/text-to-speech) | `https://api.openai.com/v1` | `gpt-4o-mini-tts`, `tts-1`, `tts-1-hd` | `alloy`, `coral`, `nova`, ... | required |
| [OpenRouter](https://openrouter.ai/docs/guides/overview/multimodal/tts) | `https://openrouter.ai/api/v1` | e.g. `openai/gpt-4o-mini-tts-2025-12-15`, `fish-audio/drama-3` | per model; often empty = default voice | required |

Any other server with the same request format works too.

## Configure

1. Open **Admin → Speech Generation (TTS)** (or the speech step of the setup wizard) and choose **OpenAI-Compatible (local or hosted)**.
2. Enter the **Base URL**. It must end in `/v1`, exactly like the [OpenAI-compatible LLM endpoint](custom-openai-compatible.md).
3. Click **Load models & voices**, then pick or type the **Model** and, optionally, the **Narrator Voice**. An empty voice is not sent, so the model speaks with its default voice.
4. Optional: **Audio Format** (`mp3` default, `wav`, or `pcm` for models that only return raw audio; PCM is stored as WAV with the sample rate from the server's `Content-Type`, e.g. `audio/pcm;rate=44100`, else 24 kHz) and **Instructions** (delivery guidance such as "calm storyteller"; sent only when filled, supported e.g. by `gpt-4o-mini-tts`).
5. Save and use **Test Speech**.

The settings are stored server-wide in `tts_settings`: `provider: "custom_openai"`, `custom_openai_url`, `selected_model`, `custom_openai_voice`, `custom_openai_format`, `custom_openai_instructions`.

## API key

The key is optional, so local servers need nothing. TaleWeaver uses the same rule as the OpenAI-compatible LLM provider:

1. the **OpenAI-Compatible API Key** from **Provider Keys**, if stored (or required by the key policy);
2. otherwise, for `openrouter.ai` URLs, the **OpenRouter** key;
3. otherwise no `Authorization` header.

The key is sent as `Authorization: Bearer <key>`. Because the same vault entry is used for the LLM and the speech endpoint, point both at the same service when they need different keys, or keep speech on a keyless local server.

## Model and voice discovery

* **Models** come from `GET {base}/models`. TaleWeaver adds `output_modalities=speech`, which makes OpenRouter list speech models only; other servers ignore it. Entries that declare their output modalities are filtered to speech models.
* **Voices** come from `GET {base}/audio/voices` (Kokoro-FastAPI and similar servers), else from the model entry's `supported_voices` (OpenRouter), else, for OpenAI models only (`api.openai.com`, `openai/...`, `tts-1`, `gpt-4o-mini-tts`), TaleWeaver suggests OpenAI's voice names. Other models get no suggestions: their providers use their own voice ids and reject OpenAI names (Fish Audio answers `Provider returned 400` for `cedar`).
* Both lists are suggestions: any model or voice id can be typed in.

## Local servers and Docker

The Base URL goes through the same endpoint policy as the OpenAI-compatible LLM provider: loopback and LAN addresses need an **explicit** `ALLOW_PRIVATE_NETWORK_MODELS=true` in `.env` (the built-in default does not count as opt-in). Metadata, link-local and multicast addresses, credentials in the URL and redirects are always rejected.

The bundled `docker-compose.yml` has an optional Kokoro service:

```bash
docker compose --profile kokoro up -d
```

Then use the Base URL `http://kokoro:8880/v1` and the model `kokoro`. Without Compose:

```bash
docker run -d -p 8880:8880 --name kokoro ghcr.io/remsky/kokoro-fastapi-cpu:latest
```

In Docker, `127.0.0.1` is the TaleWeaver container itself; a server on the host is reached via `http://host.docker.internal:<port>/v1`. For an NVIDIA GPU use `KOKORO_IMAGE=ghcr.io/remsky/kokoro-fastapi-gpu:latest` plus a GPU reservation.

Kokoro-82M speaks English (US/UK), Spanish, French, Italian, Portuguese (BR), Hindi, Japanese and Chinese, **not German**. The voice decides the language (first letter of the id: `a`/`b` English, `e` Spanish, `f` French, `i` Italian, `p` Portuguese, `h` Hindi, `j` Japanese, `z` Chinese; second letter `f`/`m` = female/male).

## Behavior and limits

* **Character voices via mapping.** The narrator uses the **Narrator Voice** above. NPCs and the protagonist speak with the voice an admin assigned to their list voice under **Admin → Character Voices** (column *OpenAI-compatible*, e.g. `am_michael`); list voices without an entry use the narrator voice. See [Character Voices](../README.md#️-character-voices-voice-list).
* **No vocal tags.** Tags like `[whispering]` are removed before synthesis; use **Instructions** for the general delivery instead.
* **Whole clips, no streaming playback.** Each line is generated as one file and played when ready.
* Timeouts follow the regular TTS settings (`TTS_TIMEOUT_SECONDS`, `TTS_TIMEOUT_PER_1K_CHARS`, `TTS_TIMEOUT_MAX_SECONDS`).

## Troubleshooting

* **"Speech server URL rejected"**: the URL does not end in `/v1`, or it is a local/LAN address without the explicit `ALLOW_PRIVATE_NETWORK_MODELS=true`.
* **"Speech server not reachable"**: the server is not running, or the host is wrong (see the Docker note above).
* **401/403 from the server**: store or fix the OpenAI-Compatible API Key (or the OpenRouter key for OpenRouter).
* **"Voice ... not found" / "Provider returned 400"**: the voice id is unknown to the model. Clear the voice to use the model's default voice, or enter a voice id from the provider's own catalog.
* **Unsupported format**: switch the Audio Format (some models only return PCM, others only MP3).
