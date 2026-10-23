"""Tests for the streamed, verified bundle download (spec sections 7 and 9).

All HTTP traffic goes through ``httpx.MockTransport``; no test touches the network.
"""

import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from backend.core.config import settings
from backend.services.adventure_library.downloader import (
    AdventureDownloader,
    DownloadCancelledError,
    DownloadError,
    HashMismatchError,
    UnsafeDownloadTargetError,
)
from backend.services.adventure_library.models import CatalogEntry, DownloadJob, JobState

BUNDLE = b"PK\x03\x04 fake adventure bundle" * 64
DOWNLOAD_URL = (
    "https://github.com/jschm42/taleweaver-adventures/releases/download/"
    "dark-forest-1.0.0/dark-forest-1.0.0.adz"
)
CDN_URL = "https://objects.githubusercontent.com/release-assets/dark-forest-1.0.0.adz"
CHUNK = 64 * 1024


def _entry(content: bytes = BUNDLE, **overrides) -> CatalogEntry:
    fields = {
        "id": "origin-dark-forest",
        "slug": "dark-forest",
        "title": "Dark Forest",
        "version": "1.0.0",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "download_url": DOWNLOAD_URL,
    }
    fields.update(overrides)
    return CatalogEntry(**fields)


def _job(entry: CatalogEntry) -> DownloadJob:
    now = datetime.now(timezone.utc)
    return DownloadJob(
        job_id="job-1",
        adventure_id=entry.id,
        slug=entry.slug,
        title=entry.title,
        version=entry.version,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def download_dir(monkeypatch, tmp_path) -> Path:
    target = tmp_path / "downloads"
    monkeypatch.setattr(settings, "ADVENTURE_DOWNLOAD_DIR", str(target))
    return target


def _recording_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    """Return a client over ``handler`` plus the list of requests it received."""
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    return httpx.AsyncClient(transport=httpx.MockTransport(record)), requests


def _files(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


async def test_happy_path_publishes_verified_bundle(download_dir):
    # Arrange
    entry = _entry()
    client, _ = _recording_client(lambda request: httpx.Response(200, content=BUNDLE))

    # Act
    async with client:
        path = await AdventureDownloader(http_client=client).download(entry)

    # Assert
    assert path == (download_dir / "dark-forest-1.0.0.adz").resolve()
    assert path.read_bytes() == BUNDLE
    assert _files(download_dir) == ["dark-forest-1.0.0.adz"]


async def test_hash_mismatch_raises_and_leaves_no_file(download_dir):
    # Arrange
    entry = _entry(sha256="0" * 64)
    job = _job(entry)
    client, _ = _recording_client(lambda request: httpx.Response(200, content=BUNDLE))

    # Act
    async with client:
        with pytest.raises(HashMismatchError):
            await AdventureDownloader(http_client=client).download(entry, job=job)

    # Assert
    assert _files(download_dir) == []
    assert job.state == JobState.ERROR


async def test_oversized_stream_is_aborted_at_cap(monkeypatch, download_dir):
    # Arrange
    cap = CHUNK + CHUNK // 2
    monkeypatch.setattr(settings, "ADVENTURE_DOWNLOAD_MAX_BYTES", cap)
    entry = _entry(content=b"x" * cap)
    job = _job(entry)

    async def endless_body() -> AsyncIterator[bytes]:
        # No Content-Length: the cap must be enforced while streaming.
        for _ in range(10):
            yield b"x" * CHUNK

    client, _ = _recording_client(lambda request: httpx.Response(200, content=endless_body()))

    # Act
    async with client:
        with pytest.raises(HashMismatchError, match="exceeded"):
            await AdventureDownloader(http_client=client).download(entry, job=job)

    # Assert
    assert job.bytes_downloaded <= cap
    assert _files(download_dir) == []


async def test_cancel_event_aborts_and_removes_part_file(download_dir):
    # Arrange
    entry = _entry(content=b"y" * (CHUNK * 2))
    job = _job(entry)
    cancel_event = asyncio.Event()
    part_seen: list[bool] = []

    async def body_cancelled_midway() -> AsyncIterator[bytes]:
        yield b"y" * CHUNK
        part_seen.append((download_dir / "dark-forest-1.0.0.adz.part").exists())
        cancel_event.set()
        yield b"y" * CHUNK

    client, _ = _recording_client(
        lambda request: httpx.Response(200, content=body_cancelled_midway())
    )

    # Act
    async with client:
        with pytest.raises(DownloadCancelledError):
            await AdventureDownloader(http_client=client).download(
                entry, job=job, cancel_event=cancel_event
            )

    # Assert
    assert part_seen == [True]
    assert _files(download_dir) == []
    assert job.state == JobState.CANCELLED


async def test_traversal_slug_is_rejected_before_any_request(download_dir):
    # Arrange
    entry = _entry().model_copy(update={"slug": "../evil"})
    client, requests = _recording_client(lambda request: httpx.Response(200, content=BUNDLE))

    # Act
    async with client:
        with pytest.raises(UnsafeDownloadTargetError):
            await AdventureDownloader(http_client=client).download(entry)

    # Assert
    assert requests == []
    assert not (download_dir.parent / "evil-1.0.0.adz").exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/jschm42/taleweaver-adventures/dark-forest.adz",
        "https://evil.example/dark-forest.adz",
    ],
    ids=["non-https", "non-allowlisted-host"],
)
async def test_disallowed_url_is_refused_before_any_request(download_dir, url):
    # Arrange
    entry = _entry().model_copy(update={"download_url": url})
    client, requests = _recording_client(lambda request: httpx.Response(200, content=BUNDLE))

    # Act
    async with client:
        with pytest.raises(DownloadError, match="refusing to download"):
            await AdventureDownloader(http_client=client).download(entry)

    # Assert
    assert requests == []
    assert _files(download_dir) == []


async def test_redirect_to_allowlisted_host_is_followed(download_dir):
    # Arrange
    entry = _entry()

    def github_release(request: httpx.Request) -> httpx.Response:
        if request.url.host == "github.com":
            return httpx.Response(302, headers={"location": CDN_URL})
        return httpx.Response(200, content=BUNDLE)

    client, requests = _recording_client(github_release)

    # Act
    async with client:
        path = await AdventureDownloader(http_client=client).download(entry)

    # Assert
    assert [r.url.host for r in requests] == ["github.com", "objects.githubusercontent.com"]
    assert path.read_bytes() == BUNDLE


async def test_redirect_to_non_allowlisted_host_is_refused(download_dir):
    # Arrange
    entry = _entry()
    client, requests = _recording_client(
        lambda request: httpx.Response(302, headers={"location": "https://169.254.169.254/x"})
    )

    # Act
    async with client:
        with pytest.raises(DownloadError, match="not in the adventure library allowlist"):
            await AdventureDownloader(http_client=client).download(entry)

    # Assert
    assert [r.url.host for r in requests] == ["github.com"]
    assert _files(download_dir) == []
