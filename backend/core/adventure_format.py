from __future__ import annotations

from typing import Any

from packaging.version import InvalidVersion
from packaging.version import parse as parse_version

FORMAT_NAME = "TaleWeaver"
LEGACY_FORMAT_NAME = "taleweaver.adz"
CURRENT_VERSION = "1.3.1"
MIN_SUPPORTED_VERSION = "1.0"
# Manifests below this version are still playable but shown as deprecated.
DEPRECATED_BELOW_VERSION = "1.3.1"
# Manifests below this version must be migrated before they can be played.
PLAYABLE_MIN_VERSION = "1.3"


def is_version_below(version: Any, threshold: str) -> bool:
    """True when ``version`` parses and is lower than ``threshold`` (``1.3`` == ``1.3.0``).

    Missing or unparsable versions are never "below": callers decide separately what an
    unknown version means.
    """
    text = str(version or "").strip()
    if not text:
        return False
    try:
        return parse_version(text) < parse_version(threshold)
    except InvalidVersion:
        return False


def is_deprecated_version(version: Any) -> bool:
    return is_version_below(version, DEPRECATED_BELOW_VERSION)


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
            raise ValueError(f"Unsupported import format '{fmt}'. Expected '{FORMAT_NAME}'.")

    if not is_supported_version(version):
        raise ValueError(
            f"Import version {version} is too old. Minimum supported version is {MIN_SUPPORTED_VERSION}."
        )

    return version
