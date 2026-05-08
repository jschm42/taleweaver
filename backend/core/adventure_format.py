from __future__ import annotations

from typing import Any

FORMAT_NAME = "TaleWeaver"
LEGACY_FORMAT_NAME = "taleweaver.adz"
CURRENT_VERSION = "1.2"
MIN_SUPPORTED_VERSION = "1.0"


def _parse_version(value: str) -> tuple[int, ...]:
    parts = [part.strip() for part in (value or "").split(".")]
    numbers: list[int] = []
    for part in parts:
        if part == "":
            continue
        if not part.isdigit():
            raise ValueError(f"Invalid format version '{value}'.")
        numbers.append(int(part))
    if not numbers:
        raise ValueError("Missing format version.")
    return tuple(numbers)


def is_supported_version(version: str, *, minimum: str = MIN_SUPPORTED_VERSION) -> bool:
    return _parse_version(version) >= _parse_version(minimum)


def validate_manifest_version(payload: dict[str, Any], *, require_format: bool = True) -> str:
    if not isinstance(payload, dict):
        raise ValueError("Invalid import file: expected JSON object.")

    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Invalid import file: missing version.")

    if require_format:
        fmt = payload.get("format")
        if fmt not in [FORMAT_NAME, LEGACY_FORMAT_NAME]:
            raise ValueError(
                f"Unsupported import format '{fmt}'. Expected '{FORMAT_NAME}'."
            )

    if not is_supported_version(version):
        raise ValueError(
            f"Import version {version} is too old. Minimum supported version is {MIN_SUPPORTED_VERSION}."
        )

    return version
