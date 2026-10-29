"""Default version and license metadata for newly generated adventures."""

from datetime import datetime, timezone
from typing import Optional

DEFAULT_VERSION = "1.0.0"
DEFAULT_LICENSE = "CC BY-NC 4.0"
DEFAULT_LICENSE_URL = "https://creativecommons.org/licenses/by-nc/4.0/"


def default_license_fields(
    username: str,
    version: Optional[str] = None,
    creator: Optional[str] = None,
    copyright: Optional[str] = None,
    license: Optional[str] = None,
    license_url: Optional[str] = None,
) -> dict[str, str]:
    """Returns template metadata, filling every missing value with the generation default."""
    year = datetime.now(timezone.utc).year
    return {
        "version": version or DEFAULT_VERSION,
        "creator": creator or username,
        "copyright": copyright or f"Copyright (c) {year} by {username}",
        "license": license or DEFAULT_LICENSE,
        "license_url": license_url or DEFAULT_LICENSE_URL,
    }
