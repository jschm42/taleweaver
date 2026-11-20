"""The .twe bundle version is the adventure manifest spec version and is checked on import."""

import io
import json
import zipfile

import pytest

from backend.core.adventure_format import CURRENT_VERSION
from backend.engine.adventures.entity_bundle import (
    MANIFEST_NAME,
    EntityBundle,
    EntityBundleError,
    pack_entity_bundle,
    unpack_entity_bundle,
)


def _bundle_with_version(version) -> bytes:
    manifest = {
        "format": "TaleWeaverEntity",
        "version": version,
        "kind": "npc",
        "entity": {"id": "X"},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(manifest))
    return buffer.getvalue()


def test_export_writes_the_manifest_spec_version():
    # Act
    data = pack_entity_bundle(EntityBundle("npc", {"id": "WOLF", "name": "Wolf"}))
    manifest = json.loads(zipfile.ZipFile(io.BytesIO(data)).read(MANIFEST_NAME))

    # Assert
    assert manifest["version"] == CURRENT_VERSION
    assert unpack_entity_bundle(data).version == CURRENT_VERSION


def test_legacy_integer_bundles_still_import():
    # Act
    bundle = unpack_entity_bundle(_bundle_with_version(1))

    # Assert
    assert bundle.version == "1.4.0"


@pytest.mark.parametrize(
    "version,message",
    [
        ("99.0.0", "newer TaleWeaver"),
        ("0.9", "too old"),
        ("abc", "Invalid entity bundle version"),
        (None, "Unsupported entity bundle version"),
        (2, "Unsupported entity bundle version"),
    ],
)
def test_unusable_versions_are_rejected(version, message):
    # Act / Assert
    with pytest.raises(EntityBundleError, match=message):
        unpack_entity_bundle(_bundle_with_version(version))
