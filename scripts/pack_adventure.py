#!/usr/bin/env python3
"""Deterministic pack tool for TaleWeaver adventures (.adz).

A source directory holds the adventure manifest ``adventure.adv`` in its root
plus an ``assets/`` folder. This tool turns it into a reproducible ``.adz``
bundle (a ZIP archive) that is bit-identical across runs on equal toolchains.

Determinism guarantees:

* entries are written in strict lexicographical order of their POSIX paths
* every entry carries the fixed DOS timestamp ``1980-01-01 00:00:00``
* every entry carries the fixed mode ``0o644`` (regular file, no exec bit)
* Deflate with a pinned compression level (``9``) for text, STORED for
  already-compressed media (PNG/JPEG/WebP/OGG/MP3/...), so the packer never
  re-encodes or re-compresses payload bytes
* no extra fields, no comments, no directory entries

Before packing, every ``assets/...`` path referenced by the manifest is
resolved case-sensitively against the files actually present. A missing or
case-mismatched reference aborts the build instead of shipping a bundle that
fails silently on the player's machine.

Byte-identity still depends on the underlying zlib build, so CI must pin the
runner image rather than float on ``ubuntu-latest``.

Usage::

    python3 scripts/pack_adventure.py src/<slug> dist/<slug>.adz --json
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
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

# Media formats are already entropy-coded; running them through Deflate changes
# no bytes worth changing and only burns CPU. They are stored verbatim.
STORE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif",
        ".ogg", ".opus", ".mp3", ".m4a", ".aac", ".flac",
        ".mp4", ".webm", ".zip", ".gz", ".bz2", ".xz", ".zst",
    }
)

# ``assets/`` paths that the runtime resolves from the app's frozen catalogs
# (see scripts/freeze_catalogs.py) instead of from the bundle. Pass
# ``strict_assets=True`` to demand them inside the bundle as well.
EXTERNAL_ASSET_PATTERNS: tuple[str, ...] = ("assets/catalog/*",)

ASSET_REF_PATTERN = re.compile(r"assets/[A-Za-z0-9_.\-/]+")


class PackError(Exception):
    """Raised when the source layout cannot be packed."""


def compute_sha256(file_path: Path, chunk_size: int = COPY_CHUNK_SIZE) -> str:
    """Return the hex SHA-256 digest of ``file_path`` using streaming reads."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def check_asset_references(
    manifest_path: Path,
    packed_paths: set[str],
    *,
    allow_missing: tuple[str, ...] = (),
    strict_assets: bool = False,
) -> dict[str, object]:
    """Resolve every asset path referenced by the manifest against ``packed_paths``.

    Comparison is exact and case-sensitive: ``assets/Foo.jpg`` does not satisfy
    ``assets/foo.jpg``. Returns a report; raises :class:`PackError` listing every
    problem at once when a reference cannot be resolved.
    """
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    referenced = sorted(set(ASSET_REF_PATTERN.findall(text)))
    allowlist = () if strict_assets else EXTERNAL_ASSET_PATTERNS
    allowlist = tuple(allowlist) + tuple(allow_missing)

    by_lower = {packed.lower(): packed for packed in packed_paths}
    missing: list[str] = []
    mismatched: list[str] = []
    external: list[str] = []
    for reference in referenced:
        if reference in packed_paths:
            continue
        if any(fnmatch.fnmatchcase(reference, pattern) for pattern in allowlist):
            external.append(reference)
            continue
        twin = by_lower.get(reference.lower())
        if twin is not None:
            mismatched.append(f"{reference} (bundle has {twin!r} - case mismatch)")
        else:
            missing.append(reference)

    if missing or mismatched:
        problems = [f"missing asset: {item}" for item in missing]
        problems += [f"case-mismatched asset: {item}" for item in mismatched]
        raise PackError(
            f"unresolved asset references in {manifest_path.name} "
            f"({len(missing)} missing, {len(mismatched)} case-mismatched): "
            + "; ".join(problems)
        )

    return {
        "referenced": len(referenced),
        "bundled": len(referenced) - len(external),
        "external": len(external),
    }


def collect_entries(
    source_dir: Path, exclude_patterns: tuple[str, ...] = ()
) -> list[tuple[str, Path]]:
    """Collect packable files as sorted ``(posix_relpath, absolute_path)`` pairs.

    ``exclude_patterns`` are shell-style globs matched against the POSIX relative
    path (``fnmatch`` semantics), e.g. ``"*.md"`` or ``"meta/*"``.
    """
    entries: list[tuple[str, Path]] = []
    for path in source_dir.rglob("*"):
        relative = path.relative_to(source_dir)
        if any(part in IGNORED_DIR_NAMES for part in relative.parts[:-1]):
            continue
        if not path.is_file():
            continue
        if path.name in IGNORED_NAMES or path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        rel_posix = relative.as_posix()
        if any(fnmatch.fnmatchcase(rel_posix, pattern) for pattern in exclude_patterns):
            continue
        entries.append((rel_posix, path))
    entries.sort(key=lambda entry: entry[0])
    return entries


def _read_manifest_version(manifest_path: Path) -> str | None:
    """Return ``adventure.version`` from the manifest, or ``None`` if absent."""
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackError(f"manifest is not valid JSON: {manifest_path}: {exc}") from exc
    adventure = payload.get("adventure")
    version = adventure.get("version") if isinstance(adventure, dict) else None
    return version if isinstance(version, str) and version.strip() else None


def pack_adventure(
    source_dir: Path,
    output_path: Path,
    *,
    force: bool = False,
    exclude: tuple[str, ...] = (),
    allow_missing: tuple[str, ...] = (),
    strict_assets: bool = False,
    expect_version: str | None = None,
    slug: str | None = None,
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

    entries = collect_entries(source_dir, exclude)
    if not entries:
        raise PackError(f"no packable files found in {source_dir}")

    manifest_version = _read_manifest_version(manifest_path)
    if expect_version is not None and manifest_version != expect_version:
        raise PackError(
            f"manifest version mismatch: adventure.adv declares "
            f"{manifest_version!r}, expected {expect_version!r}"
        )

    assets = check_asset_references(
        manifest_path,
        {rel_posix for rel_posix, _ in entries},
        allow_missing=allow_missing,
        strict_assets=strict_assets,
    )

    try:
        with zipfile.ZipFile(
            output_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=COMPRESSION_LEVEL,
        ) as archive:
            for rel_posix, abs_path in entries:
                info = zipfile.ZipInfo(filename=rel_posix, date_time=FIXED_DATETIME)
                info.compress_type = (
                    zipfile.ZIP_STORED
                    if abs_path.suffix.lower() in STORE_SUFFIXES
                    else zipfile.ZIP_DEFLATED
                )
                info.external_attr = REGULAR_FILE_ATTR
                info.create_system = 3  # POSIX, so external_attr is meaningful
                with archive.open(info, mode="w") as destination, abs_path.open("rb") as source:
                    shutil.copyfileobj(source, destination, COPY_CHUNK_SIZE)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    return {
        "slug": slug or source_dir.name,
        "archive": str(output_path.resolve()),
        "file_count": len(entries),
        "entries": [rel_posix for rel_posix, _ in entries],
        "size_bytes": output_path.stat().st_size,
        "sha256": compute_sha256(output_path),
        "manifest_sha256": compute_sha256(manifest_path),
        "manifest_version": manifest_version,
        "asset_references": assets,
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
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "skip files whose POSIX relative path matches this shell-style glob; "
            "repeatable (e.g. --exclude '$SLUG.md' keeps release notes out of the bundle)"
        ),
    )
    parser.add_argument(
        "--allow-missing",
        action="append",
        default=[],
        metavar="GLOB",
        help="treat manifest asset references matching this glob as externally resolved",
    )
    parser.add_argument(
        "--expect-version",
        metavar="VERSION",
        default=None,
        help="fail unless adventure.adv declares exactly this adventure.version (e.g. from the release tag)",
    )
    parser.add_argument(
        "--slug",
        metavar="SLUG",
        default=None,
        help="report this slug instead of the source directory name (must match the release tag slug)",
    )
    parser.add_argument(
        "--strict-assets",
        action="store_true",
        help="also require assets/catalog/* references to exist inside the bundle",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output = args.output_adz
    if output is None:
        output = Path.cwd() / f"{args.source_dir.resolve().name}.adz"

    try:
        metadata = pack_adventure(
            args.source_dir,
            output,
            force=args.force,
            exclude=tuple(args.exclude),
            allow_missing=tuple(args.allow_missing),
            strict_assets=args.strict_assets,
            expect_version=args.expect_version,
            slug=args.slug,
        )
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
        assets = metadata["asset_references"]
        print(
            f"  assets:   {assets['referenced']} referenced "
            f"({assets['bundled']} bundled, {assets['external']} external)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
