"""Reads each library adventure's manifest format version from the start of its file.

``library.json`` does not list the format version, so the catalog asks the repository for
only the first bytes of every ``adventure.adv`` (exports write ``"format"`` and ``"version"``
first). The response is streamed and cut off, so a server that ignores the ``Range`` header
cannot make us download a whole bundle. URLs are built by the catalog from validated index
values (see ``catalog.library_url``), never from API callers.
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

HEADER_BYTES = 512
MAX_PARALLEL = 6
_VERSION_RX = re.compile(rb'"version"\s*:\s*"(\d+(?:\.\d+){0,3})"')


def parse_format_version(head: bytes) -> str | None:
    """Top-level ``"version"`` of a manifest prefix, or None when it is not in ``head``."""
    # The nested "adventure" section carries the adventure's own version; ignore it.
    top_level = head.split(b'"adventure"', 1)[0]
    match = _VERSION_RX.search(top_level)
    return match.group(1).decode("ascii") if match else None


async def _read_head(client: httpx.AsyncClient, url: str) -> bytes:
    headers = {"Range": f"bytes=0-{HEADER_BYTES - 1}"}
    async with client.stream("GET", url, headers=headers, follow_redirects=False) as response:
        if response.status_code not in (httpx.codes.OK, httpx.codes.PARTIAL_CONTENT):
            return b""
        head = b""
        async for chunk in response.aiter_bytes():
            head += chunk
            if len(head) >= HEADER_BYTES:
                break
        return head[:HEADER_BYTES]


async def probe_format_versions(
    client: httpx.AsyncClient, targets: list[tuple[str, str]]
) -> dict[str, str]:
    """Maps adventure id -> format version for ``(id, adventure.adv URL)`` pairs.

    Failures are logged and skipped: an unknown version just leaves the entry unmarked.
    """
    semaphore = asyncio.Semaphore(MAX_PARALLEL)

    async def probe(adventure_id: str, url: str) -> tuple[str, str | None]:
        async with semaphore:
            try:
                return adventure_id, parse_format_version(await _read_head(client, url))
            except httpx.HTTPError as exc:
                logger.debug("Format probe failed for %s: %s", url, exc.__class__.__name__)
                return adventure_id, None

    results = await asyncio.gather(*(probe(aid, url) for aid, url in targets))
    return {aid: version for aid, version in results if version}
