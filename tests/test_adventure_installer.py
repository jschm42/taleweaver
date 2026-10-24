"""Tests for fetching library files, assembling the .adz and handing it to the importer.

HTTP goes through ``httpx.MockTransport``; the importer and the update scanner are
replaced by stubs, so no test touches the network or a real template.
"""

import io
import json
import zipfile
from types import SimpleNamespace

import httpx
import pytest

from backend.core.config import settings
from backend.engine import adventure_updates
from backend.services.adventure_library import installer as installer_module
from backend.services.adventure_library.catalog import LibraryError
from backend.services.adventure_library.installer import (
    AdventureInstallError,
    build_bundle,
    bundle_path,
    fetch_files,
    install_entry,
)
from backend.services.adventure_library.models import LibraryEntry

BASE = "https://raw.githubusercontent.com/jschm42/taleweaver-adventures/main"
BLUEPRINT = json.dumps({"adventure": {"title": "Dark Forest", "origin_id": "origin-df"}}).encode()
FILES = {
    "adventure.adv": BLUEPRINT,
    "assets/cover.jpg": b"\xff\xd8 cover",
    "assets/npc hero.jpg": b"\xff\xd8 hero",
}


def _entry(**overrides) -> LibraryEntry:
    fields = {
        "id": "origin-df",
        "slug": "dark-forest",
        "title": "Dark Forest",
        "version": "1.0.0",
        "files": list(FILES),
    }
    fields.update(overrides)
    return LibraryEntry(**fields)


def _repository(files: dict[str, bytes], requested: list[str] | None = None):
    """MockTransport handler serving ``files`` below ``BASE/dark-forest/``."""
    prefix = "/jschm42/taleweaver-adventures/main/dark-forest/"

    def serve(request: httpx.Request) -> httpx.Response:
        if requested is not None:
            requested.append(str(request.url))
        name = request.url.path.removeprefix(prefix)
        if request.url.host != "raw.githubusercontent.com" or name not in files:
            return httpx.Response(404)
        return httpx.Response(200, content=files[name])

    return serve


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def library_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ADVENTURE_LIBRARY_URL", BASE)
    monkeypatch.setattr(settings, "ADVENTURE_DOWNLOAD_DIR", str(tmp_path / "adventures"))


async def test_fetch_files_downloads_every_listed_file():
    # Arrange
    requested: list[str] = []

    # Act
    async with _client(_repository(FILES, requested)) as client:
        files = await fetch_files(_entry(), client)

    # Assert
    assert files == FILES
    assert f"{BASE}/dark-forest/assets/npc%20hero.jpg" in requested


async def test_missing_file_fails_the_download():
    # Arrange
    partial = {name: data for name, data in FILES.items() if name != "assets/cover.jpg"}

    # Act / Assert
    async with _client(_repository(partial)) as client:
        with pytest.raises(LibraryError, match="assets/cover.jpg: HTTP 404"):
            await fetch_files(_entry(), client)


async def test_download_limit_covers_all_files_together(monkeypatch):
    # Arrange
    total = sum(len(data) for data in FILES.values())
    monkeypatch.setattr(settings, "ADVENTURE_DOWNLOAD_MAX_BYTES", total - 1)

    # Act / Assert
    async with _client(_repository(FILES)) as client:
        with pytest.raises(LibraryError, match="download limit"):
            await fetch_files(_entry(), client)


async def test_network_error_is_reported_as_library_error():
    # Arrange
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    # Act / Assert
    async with _client(offline) as client:
        with pytest.raises(LibraryError, match="ConnectError"):
            await fetch_files(_entry(), client)


def test_build_bundle_puts_the_blueprint_first():
    # Act
    data = build_bundle({"assets/b.jpg": b"b", "adventure.adv": b"{}", "assets/a.jpg": b"a"})

    # Assert
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist() == ["adventure.adv", "assets/a.jpg", "assets/b.jpg"]
        assert archive.read("assets/a.jpg") == b"a"


def test_bundle_path_stays_inside_the_download_dir(tmp_path):
    # Act
    path = bundle_path("dark-forest")

    # Assert
    assert path == (tmp_path / "adventures" / "dark-forest.adz").resolve()


async def test_install_imports_stores_and_resolves_the_template(monkeypatch):
    # Arrange
    imported: list[bytes] = []
    rescans: list[bool] = []

    async def fake_import(db, data, *, owner_id, overwrite):
        imported.append(data)
        return True

    async def fake_find(db, owner_id, title, origin_id):
        return SimpleNamespace(id=f"tpl:{title}:{origin_id}")

    monkeypatch.setattr(installer_module.AdventureTemplateImporter, "import_adz", fake_import)
    monkeypatch.setattr(installer_module, "find_existing_template", fake_find)
    monkeypatch.setattr(adventure_updates, "scan_available_adventure_files", rescans.append)

    # Act
    async with _client(_repository(FILES)) as client:
        template_id = await install_entry(None, _entry(), owner_id="user-1", http_client=client)

    # Assert
    assert template_id == "tpl:Dark Forest:origin-df"
    assert bundle_path("dark-forest").read_bytes() == imported[0]
    assert rescans == [True]


async def test_rejected_bundle_is_not_stored(monkeypatch):
    # Arrange
    async def reject(db, data, *, owner_id, overwrite):
        return False

    monkeypatch.setattr(installer_module.AdventureTemplateImporter, "import_adz", reject)

    # Act / Assert
    async with _client(_repository(FILES)) as client:
        with pytest.raises(AdventureInstallError, match="rejected"):
            await install_entry(None, _entry(), owner_id="user-1", http_client=client)
    assert not bundle_path("dark-forest").exists()
