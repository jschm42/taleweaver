"""Built-in ComfyUI text-to-image profiles using core nodes only."""

import secrets
from typing import Any, Literal

from pydantic import BaseModel, Field

Workflow = Literal["sd15", "sdxl"]


class ComfySettings(BaseModel):
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_timeout: int = Field(default=600, ge=1, le=3600)
    simple_comfyui_workflow: Workflow = "sdxl"
    advanced_comfyui_workflow: Workflow = "sdxl"


class ComfyTestOptions(BaseModel):
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_timeout: int = Field(default=600, ge=1, le=3600)
    comfyui_workflow: Workflow = "sdxl"


class RenderOptions(BaseModel):
    width: int = Field(ge=256, le=2048, multiple_of=8)
    height: int = Field(ge=256, le=2048, multiple_of=8)
    steps: int = Field(default=25, ge=1, le=150)
    cfg_scale: float = Field(default=7, ge=0, le=30, allow_inf_nan=False)
    seed: int = Field(default_factory=lambda: secrets.randbelow(2**53), ge=0, lt=2**64)


def default_edge(options: dict[str, Any]) -> int:
    profile = options.get("comfyui_profile", "simple")
    family = options.get("comfyui_workflow") or options.get(f"{profile}_comfyui_workflow", "sdxl")
    if family not in {"sd15", "sdxl"}:
        raise ValueError("Choose the SD 1.5 or SDXL ComfyUI workflow.")
    return 512 if family == "sd15" else 1024


def build_workflow(prompt: str, checkpoint: str, options: dict[str, Any]) -> dict[str, Any]:
    """Build a fresh graph; prompts are opaque text, never a workflow template."""
    profile = options.get("comfyui_profile", "simple")
    if not checkpoint or checkpoint == "default":
        raise ValueError("Choose an installed ComfyUI checkpoint.")
    edge = default_edge(options)
    merged = dict(options)
    for key in (*RenderOptions.model_fields, "sampler_name", "scheduler"):
        if options.get(f"{profile}_{key}") is not None:
            merged[key] = options[f"{profile}_{key}"]
    values = {key: merged[key] for key in RenderOptions.model_fields if merged.get(key) is not None}
    if values.get("seed") == -1:
        values.pop("seed")
    render = RenderOptions.model_validate({"width": edge, "height": edge, **values})
    sampler = str(merged.get("sampler_name") or "euler").lower()
    scheduler = str(merged.get("scheduler") or "normal").lower()
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": options.get("negative_prompt") or "", "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": render.width, "height": render.height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": render.seed,
                "steps": render.steps,
                "cfg": render.cfg_scale,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": 1.0,
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": "TaleWeaver"},
        },
    }
