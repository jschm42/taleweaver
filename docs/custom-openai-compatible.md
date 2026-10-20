# Custom OpenAI-compatible APIs

Use **OpenAI-Compatible API** to connect a hosted gateway or a self-hosted inference server that implements the OpenAI Chat Completions API. It is a separate `custom_openai` provider with its own endpoint and optional encrypted API key. The official OpenAI provider keeps its existing configuration.

## Configure an endpoint

1. Open **Admin → Intelligence → Local Endpoints & Memory → Local & Custom API Endpoints**.
2. Under **OpenAI-Compatible API**, enter the API's Base URL, including its `/v1` path. Use the URL documented by your provider, not its website or the full `/chat/completions` URL. Examples:
   - Hosted gateway: `https://your-provider.example/v1`.
   - A provider with a path prefix: `https://your-provider.example/openai/v1`.
   - KoboldCpp's usual local address: `http://127.0.0.1:5001/v1`.
   - llama.cpp's usual local address: `http://127.0.0.1:8080/v1`.
   - vLLM or LM Studio: the host and port reported by the server, followed by `/v1`.
3. If the endpoint requires authentication, select **Add optional API key in Provider Vault**, save its key under **OpenAI-Compatible API**, and return to Intelligence. The key is encrypted at rest and sent to the configured endpoint using bearer authentication. Leave it unset for an unauthenticated server; do not put credentials in the URL.
4. Choose **Detect Models**, or enter the exact **Custom Model ID** in each pass. Detection uses `<base>/models` and is optional. Servers without this endpoint can use manual selection. Preserve the provider's model ID exactly, including vendor prefixes such as `openai/`.
5. Select **OpenAI-Compatible API** for mechanics, narrative, worldbuilder, play agent, and/or compression. Each role can use a different model ID. The Base URL, API key, timeout and structured-output mode are shared by these roles.
6. Save the settings before clicking **Test Model**. The test sends a small real structured completion to the saved endpoint using the selected output mode, then validates a JSON object containing a message. A successful test confirms that request, not every model capability or adventure task.

These addresses illustrate the required URL shape; they are not a record of live-provider verification.

## Local networking

For loopback or LAN endpoints, explicitly set `ALLOW_PRIVATE_NETWORK_MODELS=true` in the server environment or `.env`, then restart TaleWeaver. Custom endpoints require this explicit opt-in even though legacy local providers may allow private networks by default. A public hosted endpoint does not require the private-network opt-in. Metadata/link-local destinations and redirects are rejected even when private networking is enabled.

In Docker, `127.0.0.1` refers to the TaleWeaver container. Use `host.docker.internal` where supported, or your configured host gateway/container network address. The inference server must listen on an interface reachable from TaleWeaver.

## Structured output and limits

Custom structured requests include the JSON schema in the prompt. **Structured output support** defaults to **Prompt only** for compatibility. If the endpoint and selected model support it, choose **JSON object** to request JSON syntax or **JSON schema** to send the complete schema through `response_format`. No tool-calling support is required. TaleWeaver still parses and validates the response against the requested Pydantic schema.

The model list does not establish structured-output support. An unsupported selected mode can produce a server error; use **Prompt only** when unsure. Models also need streaming Chat Completions for narrative output. Compatibility depends on the endpoint's API implementation and the model's ability to follow the task schema.

The request timeout defaults to 300 seconds and is editable up to 3600 seconds. It also controls the initial and idle streaming timeouts. Existing per-pass output-token settings remain in effect; the server determines the actual context limit.

Detection errors distinguish authentication failure, missing `/models`, timeout and invalid/unreachable endpoints. Check the Base URL, server log, vault key and network connectivity before retrying. Detection failure does not disable manual IDs. Custom-provider requests do not fall back to official OpenAI or OpenRouter.
