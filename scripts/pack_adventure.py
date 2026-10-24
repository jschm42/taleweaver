#!/usr/bin/env python3
"""Deterministic pack tool for TaleWeaver adventures (.adz).

A source directory holds the adventure manifest ``adventure.adv`` in its root
plus an ``assets/`` folder. This tool turns it into a reproducible ``.adz``
bundle (a ZIP archive) that is bit-identical across runs on equal toolchains.

Determinism guarantees:

* entries are written in strict lexicographical order of their POSIX paths
* every entry carries the fixed DOS timestamp ``1980-01-01 00:00:00``
* every entry carries the fixed mode ``0o644`` (regular file, no exec bit)
* Deflate with a pinned compression level (``9``)
* no extra fields, no comments, no directory entries

Byte-identity still depends on the underlying zlib build, so CI must pin the
runner image rather than float on ``ubuntu-latest``.

Usage::

    python3 scripts/pack_adventure.py src/<slug> dist/<slug>.adz --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

FIXED_DATETIME: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)
# (st_mode << 16) | (st_mode >> 16) is only needed for symlinks/devices; for plain
# regular files the high word alone carries the permission bits.
REGULAR_FILE_ATTR: int = 0o100644 << 16
COMPRESSION_LEVEL: int = 9
COPY_CHUNK_SIZE: int = 1 << 16
MANIFEST_NAME: str = "adventure.adv"

IGNORED_NAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
IGNORED_SUFFIXES: frozenset[str] = frozenset({".pyc", ".pyo", ".tmp", ".part", ".swp"})
IGNORED_DIR_NAMES: frozenset[str] = frozenset({".git", "__pycache__", ".idea", ".vscode"})


class PackError(Exception):
    """Raised when the source layout cannot be packed."""


def compute_sha256(file_path: Path, chunk_size: int = COPY_CHUNK_SIZE) -> str:
    """Return the hex SHA-256 digest of ``file_path`` using streaming reads."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def collect_entries(source_dir: Path) -> list[tuple[str, Path]]:
    """Collect packable files as sorted ``(posix_relpath, absolute_path)`` pairs."""
    entries: list[tuple[str, Path]] = []
    for path in source_dir.rglob("*"):
        relative = path.relative_to(source_dir)
        if any(part in IGNORED_DIR_NAMES for part in relative.parts[:-1]):
            continue
        if not path.is_file():
            continue
        if path.name in IGNORED_NAMES or path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        entries.append((relative.as_posix(), path))
    entries.sort(key=lambda entry: entry[0])
    return entries


def pack_adventure(
    source_dir: Path,
    output_path: Path,
    *,
    force: bool = False,
) -> dict[str, object]:
    """Pack ``source_dir`` into ``output_path`` and return build metadata."""
    source_dir = source_dir.resolve()
    if not source_dir.is_dir():
        raise PackError(f"source directory does not exist: {source_dir}")

    manifest_path = source_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise PackError(
            f"invalid adventure layout: missing root manifest '{MANIFEST_NAME}' in {source_dir}"
        )

    if output_path.exists():
        if not force:
            raise PackError(
                f"output file already exists: {output_path} (pass --force to overwrite)"
            )
        output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries = collect_entries(source_dir)
    if not entries:
        raise PackError(f"no packable files found in {source_dir}")

    try:
        with zipfile.ZipFile(
            output_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=COMPRESSION_LEVEL,
        ) as archive:
            for rel_posix, abs_path in entries:
                info = zipfile.ZipInfo(filename=rel_posix, date_time=FIXED_DATETIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = REGULAR_FILE_ATTR
                info.create_system = 3  # POSIX, so external_attr is meaningful
                with archive.open(info, mode="w") as destination, abs_path.open("rb") as source:
                    shutil.copyfileobj(source, destination, COPY_CHUNK_SIZE)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    return {
        "slug": source_dir.name,
        "archive": str(output_path.resolve()),
        "file_count": len(entries),
        "size_bytes": output_path.stat().st_size,
        "sha256": compute_sha256(output_path),
        "manifest_sha256": compute_sha256(manifest_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pack_adventure.py",
        description="Pack a TaleWeaver adventure source directory into a deterministic .adz.",
    )
    parser.add_argument("source_dir", type=Path, help="directory holding adventure.adv and assets/")
    parser.add_argument(
        "output_adz",
        type=Path,
        nargs="?",
        default=None,
        help="target .adz path (default: <source_dir_name>.adz in the current directory)",
    )
    parser.add_argument("-f", "--force", action="store_true", help="overwrite an existing output file")
    parser.add_argument("--json", action="store_true", help="emit build metadata as JSON for CI")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output = args.output_adz
    if output is None:
        output = Path.cwd() / f"{args.source_dir.resolve().name}.adz"

    try:
        metadata = pack_adventure(args.source_dir, output, force=args.force)
    except PackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(metadata, indent=2, sort_keys=True))
    else:
        print(f"packed {metadata['slug']} -> {metadata['archive']}")
        print(f"  files:    {metadata['file_count']}")
        print(f"  size:     {metadata['size_bytes']:,} bytes")
        print(f"  sha256:   {metadata['sha256']}")
        print(f"  manifest: {metadata['manifest_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
