# ComfyUI image provider (Experimental)

TaleWeaver can send text-to-image jobs to a ComfyUI server through its HTTP API,
alongside the existing AUTOMATIC1111/Forge and Ollama providers. **This integration
is experimental**: checkpoint compatibility and generation time depend on the
selected model and your ComfyUI installation.

## Setup

1. Start ComfyUI separately and install a compatible checkpoint in its
   `models/checkpoints` directory. This adapter does not install ComfyUI or models.
2. Open **Admin → Visual Generation (T2I)** and select
   **ComfyUI (Local, Experimental)** for the Standard (Simple) and/or High-Fidelity
   (Advanced) model.
3. Enter your **ComfyUI server URL**. The default is `http://127.0.0.1:8188`.
   This address is reached by the TaleWeaver **backend**, not the player's browser.
   For another machine, enter that server's reachable hostname/IP and port. For
   containers, use the appropriate container/service hostname. A reverse proxy
   path prefix is supported, for example `http://gpu-host:8188/comfy`.
4. Choose the workflow family independently for each ComfyUI profile:
   - **SD 1.5**: standard text-to-image graph, recommended starting edge 512 px.
   - **SDXL**: standard text-to-image graph, recommended starting edge 1024 px.
5. Choose an installed checkpoint from each profile's model picker. The list is
   fetched from the **configured server** using
   `/object_info/CheckpointLoaderSimple`. A checkpoint name can also be entered
   manually, including a relative subfolder such as `portraits/model.safetensors`.
6. Set the generation timeout (1–3,600 seconds; default 600). Configure steps, CFG,
   sampler, scheduler and image size under **Local Diffusion Parameters** as needed.
   Use ComfyUI sampler/scheduler IDs such as `euler`, `euler_ancestral`,
   `dpmpp_2m`, `normal` or `karras`. A checkpoint's recommended parameters may differ.
7. Save settings, then use the profile's image test. Existing quality routing
   selects which profile renders scenes, character portraits, items and covers.

The setup wizard also offers ComfyUI with the same URL, workflow and checkpoint
choices.

No API key is required for a standard ComfyUI server. Private/LAN/loopback URLs
follow the existing `ALLOW_PRIVATE_NETWORK_MODELS` policy; set it to `true` when
using such endpoints. The setting is already enabled by default for local setups.
Use a trusted ComfyUI instance reachable from the backend; the adapter does not
expose or start a ComfyUI server itself.

## Workflows and profiles

Both built-in workflows use core ComfyUI nodes: `CheckpointLoaderSimple`,
`CLIPTextEncode`, `EmptyLatentImage`, `KSampler`, `VAEDecode`, and `SaveImage`.
ComfyUI loads the checkpoint's model/CLIP/VAE; the selected workflow supplies its
family's default resolution. A workflow does not convert an incompatible
checkpoint into that family.

Each generated request is a fresh graph. TaleWeaver passes its existing prepared
image prompt and negative prompt into the text-encoding nodes. Existing style
instructions, output format, thumbnail generation and asset paths are retained.
The Simple and Advanced profiles can use different checkpoints and workflow
families on the same configured server. Explicit resolution settings override the
family default, with the existing scene/portrait aspect ratios retained.

This version supports standard SD 1.5 and SDXL checkpoint workflows. Custom-node
workflows, arbitrary workflow JSON import, FLUX/SD3/other architectures, img2img,
ControlNet, LoRA selection and authenticated ComfyUI gateways are not included.

## Queue behavior and failures

- Submit once to `/prompt`, poll `/history/{prompt_id}`, and download that job's
  saved output through `/view`. Other jobs' outputs are never used as substitutes.
- The configured timeout bounds submission, execution waiting and download.
  Individual HTTP requests have a 30-second transport timeout. The admin image
  test's browser deadline includes the configured generation timeout plus a
  small response margin.
- On timeout/cancellation, attempt to remove **only this job** if it is still
  queued. A job already running remotely may finish later. The adapter never
  calls the global `/interrupt` endpoint and never resubmits a timed-out job.
- Rejected workflows, failed execution and missing output are reported as errors.
  Downloads are capped at 32 MiB and pass through the existing image decoder and
  safe local file writer.
- The existing direct catalog/account image screens still have their upstream
  180-second browser deadline. For slower configurations, use the admin profile
  test and reduce generation settings on those screens. Adventure asset generation
  uses the backend job flow.

## Verification

```sh
poetry run pytest tests/test_comfyui.py tests/test_media_engine.py tests/test_model_discovery.py tests/test_config_api.py tests/test_security_hardening.py -q
cd frontend
npm run test:comfyui
npm run build
```

Automated tests use fake HTTP responses and real local image persistence; they do
not require a GPU or contact an external ComfyUI server. A live checkpoint smoke
test on the target ComfyUI installation remains recommended before relying on the
experimental provider for a full adventure.
