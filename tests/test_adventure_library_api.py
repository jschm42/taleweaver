"""API tests for ``/adventures/library/*`` and the retired example endpoints (spec 8.3, 9).

The catalog service and the job manager are replaced by in-process stubs on the router
module, so no test reaches the network or writes a real bundle.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from backend.api.routes.adventures import imports as imports_routes
from backend.api.routes.adventures import library as library_routes
from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.services.adventure_library.catalog import CatalogService
from backend.services.adventure_library.jobs import JobManager
from backend.services.adventure_library.models import (
    AdventureCatalog,
    CatalogEntry,
    DownloadJob,
    JobState,
)

LIBRARY = "/api/adventures/library"
RELEASES = "https://github.com/jschm42/taleweaver-adventures/releases/download"


def _entry(slug: str, title: str, version: str = "1.0.0", **overrides: Any) -> CatalogEntry:
    fields = {
        "id": f"origin-{slug}",
        "slug": slug,
        "title": title,
        "version": version,
        "size_bytes": 1024,
        "sha256": "a" * 64,
        "download_url": f"{RELEASES}/{slug}-{version}/{slug}-{version}.adz",
    }
    fields.update(overrides)
    return CatalogEntry(**fields)


class StubCatalogService(CatalogService):
    """Serves a fixed catalog and counts refreshes."""

    def __init__(self, entries: list[CatalogEntry]) -> None:
        super().__init__()
        self.catalog = AdventureCatalog(schema=1, generator="test", adventures=entries)
        self.refresh_calls = 0

    async def get_catalog(self, *, force_refresh: bool = False) -> AdventureCatalog:
        return self.catalog

    async def refresh(self) -> AdventureCatalog:
        self.refresh_calls += 1
        return self.catalog

    def is_stale(self) -> bool:
        return False


class GatedDownloader:
    """Fake downloader that pauses at each stage until the test opens the gate."""

    def __init__(self, tmp_path: Path) -> None:
        self.start_gate = asyncio.Event()
        self.finish_gate = asyncio.Event()
        self._tmp_path = tmp_path

    async def download(self, entry: CatalogEntry, *, job: DownloadJob, cancel_event) -> Path:
        await self.start_gate.wait()
        job.state = JobState.DOWNLOADING
        job.bytes_downloaded = entry.size_bytes // 2
        await self.finish_gate.wait()
        job.bytes_downloaded = entry.size_bytes
        return self._tmp_path / f"{entry.slug}-{entry.version}.adz"

    async def cleanup_partial(self, target: Path) -> None:
        return None


class StubInstaller:
    async def install(self, db, file_path: Path, *, owner_id: str) -> str:
        return "installed-template-id"


@pytest.fixture
def library_catalog(monkeypatch) -> Callable[..., StubCatalogService]:
    """Install a stub catalog on the router module; call it with the entries to serve."""

    def install(*entries: CatalogEntry) -> StubCatalogService:
        service = StubCatalogService(list(entries))
        monkeypatch.setattr(library_routes, "_catalog_service", service)
        return service

    return install


@pytest.fixture
async def downloader(monkeypatch, tmp_path) -> AsyncIterator[GatedDownloader]:
    """Replace the router's job manager with one driven by a gated fake downloader."""
    monkeypatch.setattr(settings, "ADVENTURE_DOWNLOAD_DIR", str(tmp_path))
    fake = GatedDownloader(tmp_path)
    manager = JobManager(downloader=fake, installer=StubInstaller())
    monkeypatch.setattr(library_routes, "job_manager", manager)
    yield fake
    # Unwind jobs still waiting at a gate so no task outlives the test loop.
    await manager.shutdown()


async def _current_user_id(db_session) -> str:
    return await db_session.scalar(select(User.id).where(User.username == "test_user"))


async def _wait_for_state(auth_client, state: str) -> dict[str, Any]:
    """Poll the jobs endpoint until the first job reaches ``state`` (bounded)."""
    for _ in range(200):
        jobs = (await auth_client.get(f"{LIBRARY}/jobs")).json()["jobs"]
        if jobs and jobs[0]["state"] == state:
            return jobs[0]
        await asyncio.sleep(0.01)
    raise AssertionError(f"job never reached state {state!r}")


async def test_catalog_merges_local_install_state(auth_client, db_session, library_catalog):
    # Arrange
    library_catalog(
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


async def test_catalog_route_is_not_swallowed_by_template_route(auth_client, library_catalog):
    # Arrange
    library_catalog(_entry("dark-forest", "Dark Forest"))

    # Act
    response = await auth_client.get(f"{LIBRARY}/catalog")

    # Assert
    assert response.status_code == 200
    assert set(response.json()) == {"items", "catalog_generated_at", "stale"}


async def test_catalog_items_are_sorted_by_title(auth_client, library_catalog):
    # Arrange
    library_catalog(
        _entry("zeta", "zeta Station"),
        _entry("alpha", "Alpha Ruins"),
        _entry("middle", "middle Earthworks"),
    )

    # Act
    response = await auth_client.get(f"{LIBRARY}/catalog")

    # Assert
    titles = [item["entry"]["title"] for item in response.json()["items"]]
    assert titles == ["Alpha Ruins", "middle Earthworks", "zeta Station"]


async def test_download_unknown_id_returns_404(auth_client, library_catalog, downloader):
    # Arrange
    library_catalog(_entry("dark-forest", "Dark Forest"))

    # Act
    response = await auth_client.post(f"{LIBRARY}/download", json={"ids": ["no-such-id"]})

    # Assert
    assert response.status_code == 404
    assert "no-such-id" in response.json()["detail"]


async def test_download_incompatible_entry_returns_409(
    auth_client, monkeypatch, library_catalog, downloader
):
    # Arrange
    monkeypatch.setattr(settings, "APP_VERSION", "0.8.0")
    library_catalog(_entry("future", "Future Saga", min_app_version="99.0.0"))

    # Act
    response = await auth_client.post(f"{LIBRARY}/download", json={"ids": ["origin-future"]})

    # Assert
    assert response.status_code == 409
    assert "99.0.0" in response.json()["detail"]


async def test_jobs_report_state_machine_and_progress(auth_client, library_catalog, downloader):
    # Arrange
    library_catalog(_entry("dark-forest", "Dark Forest", size_bytes=2048))
    started = await auth_client.post(f"{LIBRARY}/download", json={"ids": ["origin-dark-forest"]})

    # Act
    queued = await _wait_for_state(auth_client, "queued")
    downloader.start_gate.set()
    downloading = await _wait_for_state(auth_client, "downloading")
    downloader.finish_gate.set()
    done = await _wait_for_state(auth_client, "done")

    # Assert
    assert started.status_code == 200
    assert queued["bytes_downloaded"] == 0
    assert downloading["bytes_downloaded"] == 1024
    assert done["bytes_downloaded"] == 2048
    assert done["template_id"] == "installed-template-id"


async def test_cancel_unknown_job_returns_404(auth_client, downloader):
    # Act
    response = await auth_client.post(f"{LIBRARY}/jobs/unknown-job/cancel")

    # Assert
    assert response.status_code == 404


async def test_refresh_returns_catalog_shape(auth_client, library_catalog):
    # Arrange
    service = library_catalog(_entry("dark-forest", "Dark Forest"))
    catalog_body = (await auth_client.get(f"{LIBRARY}/catalog")).json()

    # Act
    response = await auth_client.post(f"{LIBRARY}/refresh")

    # Assert
    assert response.status_code == 200
    assert response.json() == catalog_body
    assert service.refresh_calls == 1


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
