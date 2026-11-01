"""Adventure library: list and install adventures stored in the adventures repository."""

from backend.services.adventure_library.catalog import (
    SUPPORTED_SCHEMA,
    LibraryError,
    LibraryService,
    library_url,
    parse_library,
)
from backend.services.adventure_library.installer import (
    AdventureInstallError,
    build_bundle,
    bundle_path,
    download_bundle,
    fetch_files,
    install_entry,
)
from backend.services.adventure_library.models import (
    AdventureLibrary,
    LibraryEntry,
    LibraryItemView,
    is_newer_version,
    is_safe_member_path,
    is_version_at_least,
    version_tuple,
)
from backend.services.adventure_library.updates import (
    library_update_for,
    stage_library_updates,
)

__all__ = [
    "SUPPORTED_SCHEMA",
    "AdventureInstallError",
    "AdventureLibrary",
    "LibraryEntry",
    "LibraryError",
    "LibraryItemView",
    "LibraryService",
    "build_bundle",
    "bundle_path",
    "download_bundle",
    "fetch_files",
    "install_entry",
    "is_newer_version",
    "is_safe_member_path",
    "is_version_at_least",
    "library_update_for",
    "library_url",
    "parse_library",
    "stage_library_updates",
    "version_tuple",
]
