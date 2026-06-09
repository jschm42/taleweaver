# HOWTO: Local Stable Diffusion (Automatic1111 / Forge) with TaleWeaver

This guide walks you through running a local image generation backend
(Automatic1111 WebUI or its [`stable-diffusion-webui-forge`](https://github.com/lllyasviel/stable-diffusion-webui-forge) fork)
and pointing TaleWeaver at it. It covers two model families:

- **Black Forest Labs FLUX** (`.nf4` / GGUF quantized checkpoints, e.g. `flux1-schnell-nf4`, `flux1-dev-nf4`)
- **Stable Diffusion 1.5 / SDXL** checkpoints (`.safetensors`)

TaleWeaver talks to the local daemon over the standard SD WebUI HTTP API
(`/sdapi/v1/...`, default `http://127.0.0.1:7860`).

---

## 1. Prerequisites

- A working Python 3.10+ TaleWeaver install (see the top-level `README.md`).
- An NVIDIA GPU with at least **8 GB VRAM** for SD 1.5 / SDXL,
  **12 GB+** strongly recommended for FLUX. FLUX NF4 (4-bit) checkpoints are
  designed to fit in 8-12 GB and are the recommended entry point.
- ~30 GB of free disk space for model checkpoints and Python environments.
- `git`, `wget` or `curl`, and (Windows only) **Visual Studio 2022 Build Tools**
  with the *Desktop development with C++* workload (Forge compiles native
  extensions on first run).

---

## 2. Install Automatic1111 / Forge

You only need **one** of the two; Forge is recommended for FLUX because it
ships with aggressive VRAM optimizations (FP8 / NF4 weight casting, block
swapping, sdp attention).

### Option A — `stable-diffusion-webui-forge` (recommended for FLUX)

```bash
git clone --recursive https://github.com/lllyasviel/stable-diffusion-webui-forge.git
cd stable-diffusion-webui-forge
```

### Option B — Original Automatic1111 WebUI

```bash
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui
```

Forge's `webui-user.bat` / `webui-user.sh` is preconfigured to listen on
`127.0.0.1:7860`, which is the URL TaleWeaver expects by default.

---

## 3. Enable the API

Both forks expose the HTTP API on the same port as the UI. The relevant
flags live in `webui-user.bat` (Windows) or `webui-user.sh` (Linux/macOS).

Edit the `COMMANDLINE_ARGS` line so it includes `--api`:

```bash
# webui-user.sh
export COMMANDLINE_ARGS="--api --listen"
```

```bat
:: webui-user.bat
set COMMANDLINE_ARGS=--api --listen
```

- `--api` enables the `/sdapi/v1/...` endpoints that TaleWeaver calls.
- `--listen` makes the daemon reachable from non-`localhost` clients
  (only needed if your TaleWeaver backend runs in a different container /
  WSL instance / VM).

Start the daemon with `webui.sh` or `webui-user.bat`. The first launch will
compile native extensions and download the Stable Diffusion WebUI base models
(several GB). Once you see a line similar to this in the console, the API is
ready:

```
INFO:     Uvicorn running on http://127.0.0.1:7860
```

Quick smoke test from another terminal:

```bash
curl http://127.0.0.1:7860/sdapi/v1/sd-models
```

You should get a JSON array listing every checkpoint Forge has discovered in
its `models/Stable-diffusion` directory.

---

## 4. Download Models

Place the checkpoints inside the `models/Stable-diffusion/` folder of the
Forge / A1111 install, then click the **🔄 refresh** button next to the
checkpoint dropdown in the UI (or restart the daemon). TaleWeaver
auto-discovers them via `/sdapi/v1/sd-models`; the file's `title` becomes
the model id.

### 4.1 Black Forest Labs FLUX (NF4 quantized)

The official FLUX checkpoints are ~24 GB at full precision. The community
provides **NF4** (4-bit) and **GGUF** quantizations that drop the footprint
to ~5-8 GB with only a small quality hit. Popular options:

| Checkpoint | Type | Size | License | Source |
|---|---|---|---|---|
| `flux1-schnell-nf4` | NF4 safetensors | ~5.5 GB | Apache-2.0 | https://huggingface.co/lllyasviel/flux1-dev-bnb-nf4 (also works for schnell) |
| `flux1-dev-bnb-nf4` | NF4 safetensors | ~5.5 GB | FLUX.1-dev Non-Commercial | https://huggingface.co/lllyasviel/flux1-dev-bnb-nf4 |
| `flux1-schnell-gguf` | GGUF (Q4_0/Q5_0) | ~6-8 GB | Apache-2.0 | https://huggingface.co/city96/FLUX.1-schnell-gguf |
| `flux1-dev-gguf` | GGUF (Q4_0/Q5_0) | ~6-8 GB | FLUX.1-dev Non-Commercial | https://huggingface.co/city96/FLUX.1-dev-gguf |

Download with `huggingface-cli` (recommended) or directly from the browser:

```bash
# Install the CLI once
pip install -U "huggingface_hub[cli]"

# Example: pull the Schnell NF4 checkpoint
huggingface-cli download lllyasviel/flux1-dev-bnb-nf4 \
  --local-dir stable-diffusion-webui-forge/models/Stable-diffusion/flux1-schnell-nf4 \
  --include "*.safetensors"
```

> **Note on NF4 checkpoints in Forge:** Forge automatically detects the
> `.nf4` and GGUF filenames and switches to its `ForgeNF4` / GGUF loader. No
> extra config is required — just place the file in `models/Stable-diffusion/`
> and select it from the checkpoint dropdown (or via TaleWeaver).

### 4.2 Stable Diffusion 1.5 / SDXL (safetensors)

Any `.safetensors` checkpoint works. Common sources:

- `https://huggingface.co/runwayml/stable-diffusion-v1-5`
- `https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0`
- `https://civitai.com/` (community models, read each model's license)

```bash
huggingface-cli download stabilityai/stable-diffusion-xl-base-1.0 \
  --local-dir stable-diffusion-webui-forge/models/Stable-diffusion/sdxl-base-1.0 \
  --include "*.safetensors" "*.json"
```

---

## 5. Verify the Daemon

After restarting Forge / A1111 with the new checkpoint on disk, the API
should list it:

```bash
curl -s http://127.0.0.1:7860/sdapi/v1/sd-models | python -m json.tool
```

You should see the new `title` (e.g. `flux1-schnell-nf4.safetensors` or
`sdxl-base-1.0.safetensors`) in the response.

If you want to confirm generation works end-to-end, run a quick
`txt2img` request:

```bash
curl -X POST http://127.0.0.1:7860/sdapi/v1/txt2img \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a cinematic red dragon, fantasy art, highly detailed",
    "steps": 4,
    "cfg_scale": 1.0,
    "width": 1024,
    "height": 1024,
    "sampler_name": "Euler",
    "scheduler": "Simple"
  }'
```

FLUX.1-schnell uses ~4 steps with `cfg_scale=1.0`; FLUX.1-dev wants
~20-30 steps and a higher CFG (3-4). SD 1.5 / SDXL uses 20-30 steps with
`cfg_scale=7.0`.

---

## 6. Configure TaleWeaver

TaleWeaver distinguishes between a **simple** (fast) and an **advanced**
(high quality) image model. Both can be routed to the same local daemon, or
you can use a hosted API for one and a local daemon for the other.

### 6.1 Open the Admin Visuals page

Sign in as an admin, go to **Admin → Visuals**, and scroll to the
*Simple Visuals* and *Advanced Visuals* cards.

### 6.2 Simple Visuals (covers, items, NPC portraits — fast)

Recommended local setup with FLUX.1-schnell NF4:

| Field | Value |
|---|---|
| **Provider** | `Stable Diffusion (Local)` |
| **Model Selection** | `flux1-schnell-nf4` (refresh the dropdown — see `Settings → Refresh models` button) |
| **API URL** | `http://127.0.0.1:7860` |
| **Steps** | `4` (Schnell is distilled; higher steps waste time) |
| **CFG Scale** | `1.0` |
| **Sampler** | `Euler` |
| **Scheduler** | `Simple` |
| **Min. Long Edge** | `768` (smaller → faster, still acceptable for portraits and items) |

For FLUX.1-dev (better quality, slower), raise **Steps** to `20-30` and
**CFG Scale** to `3.5-4.0`.

### 6.3 Advanced Visuals (scenes — high quality)

| Field | Value |
|---|---|
| **Provider** | `Stable Diffusion (Local)` |
| **Model Selection** | `flux1-dev-nf4` or `sdxl-base-1.0` |
| **API URL** | `http://127.0.0.1:7860` |
| **Steps** | `20` (FLUX-dev) or `25-30` (SDXL) |
| **CFG Scale** | `3.5` (FLUX-dev) or `7.0` (SDXL) |
| **Sampler** | `Euler` (FLUX) or `DPM++ 2M Karras` (SDXL) |
| **Scheduler** | `Normal` (FLUX) or `Karras` (SDXL) |
| **Min. Long Edge** | `1024` (FLUX-native) or `1024` (SDXL) |

### 6.4 Click **Test Connection**

The button calls `/sdapi/v1/txt2img` with a small prompt and renders a
thumbnail directly in the admin panel. A green badge with a sample image
means everything is wired up correctly. A red badge usually means:

- The daemon is not running (check the Forge console window).
- `API URL` is wrong (default `http://127.0.0.1:7860`).
- A firewall is blocking the loopback call.
- The selected `model` does not exist on disk (the dropdown would have
  shown only `default` in that case — click the refresh button).

### 6.5 Save

Click **Save Settings**. The values are persisted to the database and
applied to all subsequent image generation requests.

---

## 7. Generate a Test Adventure

The fastest way to verify the full pipeline is to create a new adventure
from the Portal:

1. Open `http://localhost:5173/portal` (or your frontend URL).
2. Click **+ Create Adventure**, fill in a short story idea, and submit.
3. Watch the *Generation Progress* modal: the avatar, scenes, NPCs, and
   items should populate with images within a minute or two on a modern
   GPU. If you see placeholder silhouettes, check the Forge console window
   for the underlying `/sdapi/v1/txt2img` request and its response.

For NF4 / GGUF checkpoints the first image of a session is *slow*
(several minutes while Forge loads the checkpoint into VRAM); subsequent
generations are typically 5-15 s for SD 1.5 / SDXL and 10-30 s for FLUX.

---

## 8. Performance Tips

- **Use Forge, not A1111**, for FLUX. Forge's block swapping and FP8
  quantization let FLUX.1-dev run comfortably on 12 GB cards.
- **Keep the checkpoint pinned in the daemon.** Switching checkpoints via
  `override_settings.sd_model_checkpoint` (which TaleWeaver does) reloads
  the model. Use the *simple* model for all `item / cover / NPC` jobs and
  the *advanced* model only for `scene` jobs to minimize reloads.
- **Set `image_format=jpeg` and `image_quality=85`** (TaleWeaver defaults)
  to keep the on-disk library small.
- **Enable `--xformers`** in `COMMANDLINE_ARGS` if your GPU supports it.
- **Bump `min_long_edge`** only if you actually need larger images —
  generation time scales roughly with pixel count.
- **Stable Diffusion 1.5 is still the fastest** model family if you need
  *many* images per second (e.g. long adventures with hundreds of items).

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Test Connection` returns red, no image | Daemon not running | Start `webui.sh` / `webui-user.bat` and look for `Uvicorn running on http://127.0.0.1:7860` |
| Dropdown only contains `default` | Forge has not picked up the new `.safetensors` | Click the **🔄 refresh** button next to the model dropdown in the UI, or restart the daemon |
| Generation returns HTTP 404 | `--api` flag missing | Add `--api` to `COMMANDLINE_ARGS` and restart |
| Generation returns HTTP 500, "out of memory" | Checkpoint larger than VRAM | Switch to an NF4 / GGUF quantization, lower `min_long_edge`, or enable `--xformers` / `--medvram` |
| Generation succeeds but image is black / all noise | `cfg_scale` set too low for the model | FLUX-dev needs `cfg_scale ≥ 3.0`; SDXL needs `7.0`; SD 1.5 needs `7.0` |
| `steps=4` produces very low detail on a non-Schnell model | Schnell is the only model that works with 4 steps | Raise `steps` to `20-30` for `flux1-dev` and `sdxl` |
| `Negative prompt` field present in API but ignored | SD WebUI / Forge supports it natively — leave the field empty if you don't want one | n/a |
| 401 / auth errors | You enabled `--api-auth user:pass` on the daemon | Append the credentials to the API URL: `http://user:pass@127.0.0.1:7860` |

---

## 10. License Reminders

- **FLUX.1-schnell** is released under the **Apache-2.0** license and is
  free for commercial and non-commercial use.
- **FLUX.1-dev** is released under the *FLUX.1-dev Non-Commercial License*
  by Black Forest Labs. You may use it locally for personal, research, or
  non-commercial purposes. If you intend to publish or monetize adventures
  generated with it, switch to `flux1-schnell-nf4` or a hosted BFL API key.
- **Stable Diffusion 1.5** is licensed under the *CreativeML Open RAIL-M*
  license. **SDXL** is under the *SDXL OpenRAIL++-M* license. Both allow
  commercial use with a few restrictions (no illegal content, no
  generating identifiable real people without consent, etc.).
- Community checkpoints on CivitAI / HuggingFace carry their own licenses
  — always read the model card before generating content you plan to
  publish.

---

## Related Documentation

- `README.md` — top-level TaleWeaver setup
- `docs/in_game_debugging.md` — in-game debug commands
- `backend/api/routes/config_api.py` — backend logic that talks to the
  `stable_diffusion` provider (`_fetch_stable_diffusion_models` and the
  `MediaEngine._generate_image_stable_diffusion_direct` helper)
