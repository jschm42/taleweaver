"""Tests for staging library updates of installed adventures into the download dir."""

from typing import Any

import pytest

from backend.models.adventure_template import AdventureTemplate
from backend.services.adventure_library import updates as updates_module
from backend.services.adventure_library.catalog import LibraryError, LibraryService
from backend.services.adventure_library.models import AdventureLibrary, LibraryEntry


def _entry(slug: str, version: str) -> LibraryEntry:
    return LibraryEntry(
        id=f"origin-{slug}", slug=slug, title=slug, version=version, files=["adventure.adv"]
    )


def _template(slug: str, version: str | None, origin: bool = True) -> AdventureTemplate:
    return AdventureTemplate(
        title=slug, origin_id=f"origin-{slug}" if origin else None, version=version
    )


class StubService(LibraryService):
    def __init__(self, *entries: LibraryEntry, error: LibraryError | None = None) -> None:
        super().__init__()
        self.library = AdventureLibrary(schema=1, adventures=list(entries))
        self.error = error

    async def get_library(self, *, force_refresh: bool = False) -> AdventureLibrary:
        if self.error is not None:
            raise self.error
        return self.library


@pytest.fixture
def downloads(monkeypatch) -> dict[str, Any]:
    """Replace the download and the disk check; records downloaded slugs."""
    state: dict[str, Any] = {"downloaded": [], "on_disk": set(), "fail": set()}

    async def fake_download(entry):
        if entry.slug in state["fail"]:
            raise LibraryError("HTTP 503")
        state["downloaded"].append(entry.slug)

    def fake_on_disk(template, version):
        return template.title in state["on_disk"]

    monkeypatch.setattr(updates_module, "download_bundle", fake_download)
    monkeypatch.setattr(updates_module, "_bundle_on_disk", fake_on_disk)
    return state


async def test_only_newer_library_versions_are_downloaded(downloads):
    # Arrange
    service = StubService(
        _entry("newer", "1.2.0"), _entry("same", "1.0.0"), _entry("older", "0.9.0")
    )
    templates = [
        _template("newer", "1.0.0"),
        _template("same", "1.0.0"),
        _template("older", "1.0.0"),
        _template("unlisted", "1.0.0"),
        _template("newer", "1.0.0", origin=False),
    ]

    # Act
    errors = await updates_module.stage_library_updates(templates, service)

    # Assert
    assert errors == []
    assert downloads["downloaded"] == ["newer"]


async def test_a_bundle_already_on_disk_is_not_downloaded_again(downloads):
    # Arrange
    downloads["on_disk"].add("newer")
    service = StubService(_entry("newer", "1.2.0"))

    # Act
    await updates_module.stage_library_updates([_template("newer", "1.0.0")], service)

    # Assert
    assert downloads["downloaded"] == []


async def test_download_failures_are_reported_and_do_not_stop_the_rest(downloads):
    # Arrange
    downloads["fail"].add("broken")
    service = StubService(_entry("broken", "2.0.0"), _entry("fine", "2.0.0"))
    templates = [_template("broken", "1.0.0"), _template("fine", "1.0.0")]

    # Act
    errors = await updates_module.stage_library_updates(templates, service)

    # Assert
    assert errors == ["broken: download failed (HTTP 503)"]
    assert downloads["downloaded"] == ["fine"]


async def test_no_catalog_stages_nothing(downloads):
    # Arrange
    service = StubService(error=LibraryError("offline"))

    # Act
    errors = await updates_module.stage_library_updates([_template("x", "1.0.0")], service)

    # Assert
    assert errors == []
    assert downloads["downloaded"] == []
