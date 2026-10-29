"""
Model-specific request payload builders for the Black Forest Labs (BFL) direct API.

FLUX 3 endpoints reject unknown keys (`additionalProperties: false`), so each model
family gets an explicit allow-list of fields instead of a generic pass-through.
"""

import math
from typing import Any

FLUX_3_IMAGE = "flux-3-image"
FLUX_3_IMAGE_KLEIN = "flux-3-image-klein"

BFL_MODEL_ALIASES = {
    "flux-3": FLUX_3_IMAGE,
    "flux3": FLUX_3_IMAGE,
    "flux-3-image": FLUX_3_IMAGE,
    "flux-3-klein": FLUX_3_IMAGE_KLEIN,
    "flux3-klein": FLUX_3_IMAGE_KLEIN,
    "flux-3-image-klein": FLUX_3_IMAGE_KLEIN,
}

FLUX_3_ASPECT_RATIOS = (
    "21:9",
    "2:1",
    "16:9",
    "3:2",
    "7:5",
    "4:3",
    "5:4",
    "1:1",
    "4:5",
    "3:4",
    "5:7",
    "2:3",
    "9:16",
    "1:2",
    "9:21",
)

PROMPT_MAX_LENGTH = 1500

_LEGACY_FIELDS = (
    "input_image",
    "input_image_2",
    "input_image_3",
    "input_image_4",
    "seed",
    "width",
    "height",
    "safety_tolerance",
    "output_format",
    "webhook_url",
    "webhook_secret",
    "transparent_bg",
)

_FLUX_3_IMAGE_FIELDS = (
    "images",
    "aspect_ratio",
    "resolution",
    "safety_tolerance",
    "grounding",
    "version",
)

_FLUX_3_KLEIN_FIELDS = (
    "images",
    "aspect_ratio",
    "resolution",
    "width",
    "height",
    "seed",
    "safety_tolerance",
    "output_format",
    "steps",
)

_LEGACY_IMAGE_FIELDS = ("input_image", "input_image_2", "input_image_3", "input_image_4")


def resolve_bfl_model_alias(model_slug: str) -> str:
    """Map shorthand FLUX 3 names (e.g. `flux-3-klein`) to official endpoint slugs."""
    return BFL_MODEL_ALIASES.get(model_slug.lower(), model_slug)


def _ratio_value(aspect_ratio: str) -> float:
    width, height = aspect_ratio.split(":")
    return int(width) / int(height)


def nearest_flux_3_aspect_ratio(width: Any, height: Any) -> str | None:
    """Return the allowed FLUX 3 aspect ratio closest to `width:height`, or None if invalid."""
    try:
        target = float(width) / float(height)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if target <= 0:
        return None

    # Compare in log space so 2:1 and 1:2 are equally far from 1:1.
    log_target = math.log(target)
    return min(
        FLUX_3_ASPECT_RATIOS,
        key=lambda ratio: abs(math.log(_ratio_value(ratio)) - log_target),
    )


def _copy_fields(provider_options: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        field: provider_options[field]
        for field in fields
        if provider_options.get(field) is not None
    }


def _collect_legacy_images(provider_options: dict[str, Any]) -> list[Any]:
    return [
        provider_options[field]
        for field in _LEGACY_IMAGE_FIELDS
        if provider_options.get(field) is not None
    ]


def _build_flux_3_payload(
    provider_options: dict[str, Any], fields: tuple[str, ...]
) -> dict[str, Any]:
    payload = _copy_fields(provider_options, fields)
    if "images" in payload:
        return payload

    legacy_images = _collect_legacy_images(provider_options)
    if legacy_images:
        payload["images"] = legacy_images
    return payload


def _build_flux_3_image_payload(provider_options: dict[str, Any]) -> dict[str, Any]:
    payload = _build_flux_3_payload(provider_options, _FLUX_3_IMAGE_FIELDS)
    if "aspect_ratio" in payload:
        return payload

    aspect_ratio = nearest_flux_3_aspect_ratio(
        provider_options.get("width"), provider_options.get("height")
    )
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    return payload


def _build_flux_3_klein_payload(provider_options: dict[str, Any]) -> dict[str, Any]:
    return _build_flux_3_payload(provider_options, _FLUX_3_KLEIN_FIELDS)


def _build_legacy_payload(provider_options: dict[str, Any]) -> dict[str, Any]:
    return _copy_fields(provider_options, _LEGACY_FIELDS)


_PAYLOAD_BUILDERS = {
    FLUX_3_IMAGE: _build_flux_3_image_payload,
    FLUX_3_IMAGE_KLEIN: _build_flux_3_klein_payload,
}


def build_bfl_payload(
    model_slug: str, prompt: str, provider_options: dict[str, Any]
) -> dict[str, Any]:
    """Build the JSON body for `POST /v1/<model_slug>` containing only accepted keys."""
    builder = _PAYLOAD_BUILDERS.get(model_slug, _build_legacy_payload)
    return {"prompt": prompt[:PROMPT_MAX_LENGTH], **builder(provider_options)}
