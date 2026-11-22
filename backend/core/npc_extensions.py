"""Runtime- and fork-specific data of a single NPC (namespaces inside ``metadata_json``).

Shared feature runtimes may store per-NPC seed data next to the engine's own NPC settings,
e.g. ``"metadata_json": {"agent_runtime": {"schema_version": 1, ...}}``. A metadata key is
such a namespace when its value is a JSON object with a ``schema_version`` (engine settings
never carry one). TaleWeaver never interprets it: the object is kept unchanged, nested
``null`` values included, on import, while editing and on export. Imports are untrusted, so
a namespace with an invalid key, past ``MAX_NAMESPACES`` or past the size budget is dropped.
"""

from __future__ import annotations

from typing import Any

from backend.core.manifest_extensions import MAX_NAMESPACES, encoded_size, is_valid_namespace

SCHEMA_VERSION_KEY = "schema_version"
MAX_NPC_EXTENSIONS_BYTES = 64 * 1024


def is_npc_extension(value: Any) -> bool:
    """True for a metadata value that is an extension namespace object."""
    return isinstance(value, dict) and SCHEMA_VERSION_KEY in value


def split_npc_extensions(metadata: Any) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Splits NPC metadata into (engine settings, valid extension namespaces).

    Extension namespaces that break the rules are dropped from both parts.
    """
    if not isinstance(metadata, dict):
        return {}, {}

    settings: dict[str, Any] = {}
    extensions: dict[str, dict[str, Any]] = {}
    budget = MAX_NPC_EXTENSIONS_BYTES
    for key, value in metadata.items():
        if not is_npc_extension(value):
            settings[key] = value
            continue
        size = encoded_size(value)
        if len(extensions) >= MAX_NAMESPACES or not is_valid_namespace(key) or size > budget:
            continue
        budget -= size
        extensions[key] = value
    return settings, extensions


def normalize_npc_metadata_extensions(metadata: Any) -> dict[str, Any]:
    """Returns the NPC metadata with invalid extension namespaces removed."""
    settings, extensions = split_npc_extensions(metadata)
    return {**settings, **extensions}
