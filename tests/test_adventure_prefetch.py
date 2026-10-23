"""Tests for the opt-in first-boot adventure library prefetch (spec section 8.5)."""

import logging
from datetime import datetime, timedelta, timezone

import pytest

from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.services.adventure_library.catalog import CatalogService
from backend.services.adventure_library.jobs import JobError
from backend.services.adventure_library.models import AdventureCatalog, CatalogEntry
from backend.services.adventure_library.prefetch import prefetch_adventures

RELEASES = "https://github.com/jschm42/taleweaver-adventures/releases/download"


def _entry(slug: str, **overrides) -> CatalogEntry:
    fields = {
        "id": f"origin-{slug}",
        "slug": slug,
        "title": slug.title(),
        "version": "1.0.0",
        "size_bytes": 1024,
        "sha256": "a" * 64,
        "download_url": f"{RELEASES}/{slug}-1.0.0/{slug}-1.0.0.adz",
    }
    fields.update(overrides)
    return CatalogEntry(**fields)


class StubCatalogService(CatalogService):
    def __init__(self, entries: list[CatalogEntry], error: Exception | None = None) -> None:
        super().__init__()
        self._catalog = AdventureCatalog(schema=1, adventures=entries)
        self._error = error
        self.calls = 0

    async def get_catalog(self, *, force_refresh: bool = False) -> AdventureCatalog:
        self.calls += 1
        if self._error:
            raise self._error
        return self._catalog


class RecordingManager:
    """Stands in for JobManager; records ``(slug, owner_id)`` per started job."""

    def __init__(self, failing_slugs: frozenset[str] = frozenset()) -> None:
        self.started: list[tuple[str, str]] = []
        self._failing = failing_slugs

    async def start(self, entry: CatalogEntry, owner_id: str):
        if entry.slug in self._failing:
            raise JobError(f"{entry.slug} already running")
        self.started.append((entry.slug, owner_id))
        return type("Job", (), {"job_id": f"job-{entry.slug}"})()


@pytest.fixture
def prefetch_enabled(monkeypatch):
    monkeypatch.setattr(settings, "TALEWEAVER_PREFETCH_ADVENTURES", True)
    monkeypatch.setattr(settings, "APP_VERSION", "0.8.0")


def _user(username: str, role: str, age_days: int) -> User:
    created = datetime.now(timezone.utc) - timedelta(days=age_days)
    return User(username=username, hashed_password="x", role=role, created_at=created)


async def test_disabled_flag_does_nothing(monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "TALEWEAVER_PREFETCH_ADVENTURES", False)
    catalog = StubCatalogService([_entry("dark-forest")])
    manager = RecordingManager()

    # Act
    started = await prefetch_adventures(catalog, manager)

    # Assert
    assert started == 0
    assert catalog.calls == 0


async def test_existing_template_skips_prefetch(prefetch_enabled, db_session):
    # Arrange
    admin = _user("root", "admin", age_days=1)
    db_session.add(admin)
    await db_session.flush()
    db_session.add(AdventureTemplate(title="Already Here", owner_id=admin.id))
    await db_session.commit()
    catalog = StubCatalogService([_entry("dark-forest")])
    manager = RecordingManager()

    # Act
    started = await prefetch_adventures(catalog, manager)

    # Assert
    assert started == 0
    assert manager.started == []


async def test_missing_admin_skips_with_warning(prefetch_enabled, db_session, caplog):
    # Arrange
    db_session.add(_user("player", "user", age_days=1))
    await db_session.commit()
    manager = RecordingManager()

    # Act
    with caplog.at_level(logging.WARNING):
        started = await prefetch_adventures(StubCatalogService([_entry("a")]), manager)

    # Assert
    assert started == 0
    assert "no admin user" in caplog.text


async def test_starts_compatible_entries_for_first_admin(prefetch_enabled, db_session):
    # Arrange
    first_admin = _user("first", "admin", age_days=10)
    db_session.add_all([_user("second", "admin", age_days=1), first_admin])
    await db_session.commit()
    catalog = StubCatalogService(
        [
            _entry("dark-forest"),
            _entry("future", min_app_version="99.0.0"),
            _entry("busy"),
            _entry("sunken-city"),
        ]
    )
    manager = RecordingManager(failing_slugs=frozenset({"busy"}))

    # Act
    started = await prefetch_adventures(catalog, manager)

    # Assert
    assert started == 2
    assert manager.started == [
        ("dark-forest", first_admin.id),
        ("sunken-city", first_admin.id),
    ]


async def test_unexpected_failure_is_logged_not_raised(prefetch_enabled, db_session, caplog):
    # Arrange
    db_session.add(_user("root", "admin", age_days=1))
    await db_session.commit()
    catalog = StubCatalogService([], error=RuntimeError("boom"))

    # Act
    with caplog.at_level(logging.ERROR):
        started = await prefetch_adventures(catalog, RecordingManager())

    # Assert
    assert started == 0
    assert "Adventure prefetch failed" in caplog.text
