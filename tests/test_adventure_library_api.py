"""API tests for ``/adventures/library/*`` and the retired example endpoints.

The library service and the installer are replaced by in-process stubs on the router
module, so no test reaches the network or imports a real bundle.
"""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import select

from backend.api.routes.adventures import imports as imports_routes
from backend.api.routes.adventures import library as library_routes
from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.services.adventure_library.catalog import LibraryError, LibraryService
from backend.services.adventure_library.installer import AdventureInstallError
from backend.services.adventure_library.models import AdventureLibrary, LibraryEntry

LIBRARY = "/api/adventures/library"
BASE = "https://raw.githubusercontent.com/jschm42/taleweaver-adventures/main"


def _entry(slug: str, title: str, version: str = "1.0.0", **overrides: Any) -> LibraryEntry:
    fields = {
        "id": f"origin-{slug}",
        "slug": slug,
        "title": title,
        "version": version,
        "cover": "assets/cover.jpg",
        "files": ["adventure.adv", "assets/cover.jpg"],
    }
    fields.update(overrides)
    return LibraryEntry(**fields)


class StubLibraryService(LibraryService):
    """Serves a fixed index (or raises) and counts forced refreshes."""

    def __init__(self, entries: list[LibraryEntry], error: LibraryError | None = None) -> None:
        super().__init__()
        self.library = AdventureLibrary(schema=1, adventures=entries)
        self.error = error
        self.refresh_calls = 0

    async def get_library(self, *, force_refresh: bool = False) -> AdventureLibrary:
        if self.error is not None:
            raise self.error
        self.refresh_calls += int(force_refresh)
        return self.library

    def is_stale(self) -> bool:
        return False


@pytest.fixture(autouse=True)
def library_base(monkeypatch):
    monkeypatch.setattr(settings, "ADVENTURE_LIBRARY_URL", BASE)


@pytest.fixture
def library(monkeypatch) -> Callable[..., StubLibraryService]:
    """Install a stub library service on the router module."""

    def install(*entries: LibraryEntry, error: LibraryError | None = None) -> StubLibraryService:
        service = StubLibraryService(list(entries), error)
        monkeypatch.setattr(library_routes, "_library_service", service)
        return service

    return install


@pytest.fixture
def installs(monkeypatch) -> list[tuple[str, str]]:
    """Replace the installer; records ``(slug, owner_id)`` per call."""
    calls: list[tuple[str, str]] = []

    async def fake_install(db, entry, *, owner_id):
        calls.append((entry.slug, owner_id))
        return f"template-{entry.slug}"

    monkeypatch.setattr(library_routes, "install_entry", fake_install)
    return calls


async def _current_user_id(db_session) -> str:
    return await db_session.scalar(select(User.id).where(User.username == "test_user"))


async def test_catalog_merges_local_install_state(auth_client, db_session, library):
    # Arrange
    library(
        _entry("dark-forest", "Dark Forest", version="1.2.0"),
        _entry("sunken-city", "Sunken City"),
    )
    db_session.add(
        AdventureTemplate(
            title="Dark Forest",
            owner_id=await _current_user_id(db_session),
            origin_id="origin-dark-forest",
            version="1.0.0",
        )
    )
    await db_session.commit()

    # Act
    response = await auth_client.get(f"{LIBRARY}/catalog")

    # Assert
    assert response.status_code == 200
    items = {item["entry"]["slug"]: item for item in response.json()["items"]}
    assert items["dark-forest"]["installed_version"] == "1.0.0"
    assert items["dark-forest"]["update_available"] is True
    assert items["sunken-city"]["installed_version"] is None
    assert items["sunken-city"]["update_available"] is False


async def test_catalog_builds_cover_urls_and_sorts_by_title(auth_client, library):
    # Arrange
    library(
        _entry("zebra", "Zebra Run"),
        _entry("apple", "Apple Hunt", cover=None),
    )

    # Act
    response = await auth_client.get(f"{LIBRARY}/catalog")

    # Assert
    items = response.json()["items"]
    assert [item["entry"]["title"] for item in items] == ["Apple Hunt", "Zebra Run"]
    assert items[0]["cover_url"] is None
    assert items[1]["cover_url"] == f"{BASE}/zebra/assets/cover.jpg"
    assert response.json()["stale"] is False


async def test_catalog_unavailable_returns_502(auth_client, library):
    # Arrange
    library(error=LibraryError("unexpected HTTP status 404"))

    # Act
    response = await auth_client.get(f"{LIBRARY}/catalog")

    # Assert
    assert response.status_code == 502


async def test_refresh_forces_a_fetch(auth_client, library):
    # Arrange
    service = library(_entry("dark-forest", "Dark Forest"))

    # Act
    response = await auth_client.post(f"{LIBRARY}/refresh")

    # Assert
    assert response.status_code == 200
    assert service.refresh_calls == 1


async def test_install_runs_the_installer_for_the_caller(
    auth_client, db_session, library, installs
):
    # Arrange
    library(_entry("dark-forest", "Dark Forest", version="1.2.0"))

    # Act
    response = await auth_client.post(f"{LIBRARY}/install", json={"id": "origin-dark-forest"})

    # Assert
    assert response.status_code == 200
    assert response.json() == {"template_id": "template-dark-forest", "version": "1.2.0"}
    assert installs == [("dark-forest", await _current_user_id(db_session))]


async def test_install_unknown_id_returns_404(auth_client, library, installs):
    # Arrange
    library(_entry("dark-forest", "Dark Forest"))

    # Act
    response = await auth_client.post(f"{LIBRARY}/install", json={"id": "no-such-id"})

    # Assert
    assert response.status_code == 404
    assert installs == []


async def test_install_while_running_returns_409(auth_client, monkeypatch, library, installs):
    # Arrange
    library(_entry("dark-forest", "Dark Forest"))
    monkeypatch.setattr(library_routes, "_installing", {"origin-dark-forest"})

    # Act
    response = await auth_client.post(f"{LIBRARY}/install", json={"id": "origin-dark-forest"})

    # Assert
    assert response.status_code == 409
    assert installs == []


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (LibraryError("dark-forest/assets/cover.jpg: HTTP 404"), 502),
        (AdventureInstallError("the importer rejected dark-forest 1.0.0"), 422),
    ],
)
async def test_install_failures_map_to_http_errors(
    auth_client, monkeypatch, library, error, expected_status
):
    # Arrange
    library(_entry("dark-forest", "Dark Forest"))

    async def failing_install(db, entry, *, owner_id):
        raise error

    monkeypatch.setattr(library_routes, "install_entry", failing_install)

    # Act
    response = await auth_client.post(f"{LIBRARY}/install", json={"id": "origin-dark-forest"})

    # Assert
    assert response.status_code == expected_status
    assert library_routes._installing == set()


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/adventures/check-examples"), ("post", "/api/adventures/import-examples")],
)
async def test_retired_example_endpoints_return_410(auth_client, method, path):
    # Act
    response = await getattr(auth_client, method)(path)

    # Assert
    assert response.status_code == 410
    assert response.json() == {
        "detail": "Example adventures are now provided by the adventure library."
    }


async def test_legacy_flag_restores_example_import(auth_client, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "ADVENTURE_LEGACY_EXAMPLES_ENABLED", True)
    imported_dirs: list[str] = []

    async def fake_import(db, directory, **kwargs) -> None:
        imported_dirs.append(directory)

    monkeypatch.setattr(
        imports_routes.AdventureTemplateImporter, "import_from_directory", fake_import
    )

    # Act
    response = await auth_client.post("/api/adventures/import-examples")

    # Assert
    assert response.status_code == 200
    assert imported_dirs[0].replace("\\", "/") == "adventures/samples"
