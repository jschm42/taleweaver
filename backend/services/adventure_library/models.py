"""Pydantic models for the adventure library: the remote ``library.json`` and its API view."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
BLUEPRINT_NAME = "adventure.adv"
ASSETS_DIR = "assets"

_LEADING_NUMBER = re.compile(r"^\d+")
# Characters that would change the meaning of a URL path segment or a zip member name.
_FORBIDDEN_PATH_CHARS = frozenset("\\:?#%")


def is_safe_member_path(path: str) -> bool:
    """True for ``adventure.adv`` and plain relative paths below ``assets/``.

    The index is remote data, so every listed path is checked before it is turned into
    a URL or a zip member name (CWE-22): no absolute paths, no ``..``, no backslashes,
    and nothing outside the two locations an ``.adz`` bundle may contain.
    """
    if not path or any(char in _FORBIDDEN_PATH_CHARS for char in path):
        return False
    # Split by hand: PurePosixPath would silently drop "." and empty segments.
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    return path == BLUEPRINT_NAME or (len(parts) > 1 and parts[0] == ASSETS_DIR)


class LibraryEntry(BaseModel):
    """One adventure as listed in ``library.json``: an unpacked directory in the repo."""

    # Unknown fields are ignored so newer indexes stay readable.
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, description="adventure.origin_id (UUID), primary key")
    slug: str = Field(pattern=SLUG_PATTERN, max_length=64)
    title: str = Field(min_length=1)
    teaser: str = ""
    version: str = Field(min_length=1)
    author: str = ""
    language: str = ""
    license: str = ""
    cover: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    files: list[str] = Field(min_length=1)

    @field_validator("files")
    @classmethod
    def _files_are_safe(cls, files: list[str]) -> list[str]:
        unsafe = [path for path in files if not is_safe_member_path(path)]
        if unsafe:
            raise ValueError(f"unsafe file path(s): {unsafe[:3]}")
        if BLUEPRINT_NAME not in files:
            raise ValueError(f"{BLUEPRINT_NAME} is not listed")
        return files

    @field_validator("cover")
    @classmethod
    def _cover_is_safe(cls, cover: str | None) -> str | None:
        return cover if cover and is_safe_member_path(cover) else None


class AdventureLibrary(BaseModel):
    """The whole ``library.json`` document."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # ``schema`` would shadow a BaseModel attribute.
    schema_: int = Field(alias="schema")
    adventures: list[LibraryEntry] = Field(default_factory=list)


class LibraryItemView(BaseModel):
    """A library entry merged with the caller's install state (API view)."""

    entry: LibraryEntry
    cover_url: str | None = None
    installed_version: str | None = None
    update_available: bool = False


def version_tuple(value: str) -> tuple[int, ...]:
    """Parse a dotted version into integers, ignoring non-numeric suffixes.

    ``"0.7.0-beta"`` -> ``(0, 7, 0)``; ``"1.2rc1"`` -> ``(1, 2)``; garbage -> ``(0,)``.
    """
    parts: list[int] = []
    for segment in (value or "").strip().split("."):
        match = _LEADING_NUMBER.match(segment)
        if not match:
            break
        parts.append(int(match.group()))
        if match.end() != len(segment):
            break
    return tuple(parts) if parts else (0,)


def _padded(parts: tuple[int, ...], length: int) -> tuple[int, ...]:
    return parts + (0,) * (length - len(parts))


def is_version_at_least(current: str, required: str) -> bool:
    """Return True when ``current`` >= ``required`` (missing components count as 0)."""
    current_parts = version_tuple(current)
    required_parts = version_tuple(required)
    length = max(len(current_parts), len(required_parts))
    return _padded(current_parts, length) >= _padded(required_parts, length)
