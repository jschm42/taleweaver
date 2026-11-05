#!/usr/bin/env python3
"""
TaleWeaver Skill Bundler (CLI)

Bundles an agent skill from `.agents/skills/<name>/` for distribution: copies the companion
docs from the repo `docs/` folder into `<skill>/docs/`, writes `package.json` (npm package
config) and `manifest.json` (sha256 + sizes), verifies docs, checksums and relative
references (--check) and exports a verified bundle as a .tar.gz or .zip archive.

Complexity: d = companion docs per skill, f = bundled files, n = bytes of one file.

Usage:
  python scripts/bundle_skill.py                                  # rebuild the default skill
  python scripts/bundle_skill.py --skill taleweaver-adventure-concept-creator
  python scripts/bundle_skill.py --check                          # verify only, exit 1 on errors
  python scripts/bundle_skill.py --export-archive zip --output dist/
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tarfile
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SUBDIR = Path(".agents") / "skills"
ENTRY_FILE = "SKILL.md"
PACKAGE_FILE = "package.json"
MANIFEST_FILE = "manifest.json"
DEFAULT_SKILL = "taleweaver-adventure-concept-creator"
DEFAULT_VERSION = "1.0.0"
MANIFEST_SCHEMA = 1
ARCHIVE_SUFFIXES = {"tar.gz": ".tar.gz", "zip": ".zip"}
AGENT_TAGS = ["claude-code", "claude-skills", "antigravity", "github-copilot"]

SKILL_DOC_REF = re.compile(r"`(docs/[\w./-]+\.md)`")
MARKDOWN_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
FRONTMATTER_DESCRIPTION = re.compile(r"^description:\s*(.+)$", re.MULTILINE)


# --- Model -------------------------------------------------------------------------
@dataclass(frozen=True)
class CompanionDoc:
    """A repo doc that ships with a skill. `source` is relative to the repo root and is
    also the path inside the skill directory, unless `alias` names a second copy that
    exists only so a misspelled reference still resolves."""

    source: str
    description: str
    alias: str = ""

    @property
    def target(self) -> str:
        """Path inside the skill directory. O(1)."""
        return self.alias or self.source


BUNDLES: dict[str, tuple[CompanionDoc, ...]] = {
    "taleweaver-adventure-concept-creator": (
        CompanionDoc(
            "docs/world-builder-blueprint-manual.md",
            "Story Idea blueprint manual: workflow, tag overview and design advice.",
        ),
        CompanionDoc(
            "docs/world-builder-syntax.md",
            "Full key reference for the World-Builder blueprint syntax.",
        ),
        CompanionDoc(
            "docs/scripting_engine.md",
            "Scripting engine (`tw.*` API) used by on_start, guard, Rule and Script blocks.",
        ),
        CompanionDoc(
            "docs/scripting_engine.md",
            "Alias of docs/scripting_engine.md for references using the misspelled name.",
            alias="docs/scripting-enginge.md",
        ),
        CompanionDoc(
            "docs/specs/adventure_format.md",
            "Adventure file format specification (adventure.adv / .adz).",
        ),
    ),
}


@dataclass(frozen=True)
class Skill:
    """A resolved skill directory and its companion docs."""

    name: str
    root: Path
    repo_root: Path
    docs: tuple[CompanionDoc, ...]


@dataclass
class CheckReport:
    """Errors fail a check; warnings are informational."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no errors were recorded. O(1)."""
        return not self.errors


def safe_join(base: Path, relative: str) -> Path:
    """Join `relative` onto `base` and refuse paths that escape `base` (CWE-22). O(1)."""
    candidate = (base / relative).resolve()
    if not candidate.is_relative_to(base.resolve()):
        raise ValueError(f"Path escapes {base}: {relative}")
    return candidate


def sha256_file(path: Path) -> str:
    """Stream the file in 64 KiB chunks. O(n) time in file size, O(1) memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_skill(skill_arg: str, repo_root: Path = REPO_ROOT) -> Skill:
    """Resolve a skill name or path inside `.agents/skills/`. O(1)."""
    skills_dir = (repo_root / SKILLS_SUBDIR).resolve()
    is_path = "/" in skill_arg or "\\" in skill_arg
    root = Path(skill_arg).resolve() if is_path else safe_join(skills_dir, skill_arg)
    if root.parent != skills_dir:
        raise ValueError(f"Skill must live directly in {skills_dir}: {skill_arg}")
    if root.name not in BUNDLES:
        raise ValueError(f"No bundle definition for skill '{root.name}'")
    if not (root / ENTRY_FILE).is_file():
        raise FileNotFoundError(f"Missing {ENTRY_FILE} in {root}")
    return Skill(root.name, root, repo_root.resolve(), BUNDLES[root.name])


def bundled_files(skill: Skill) -> list[str]:
    """Relative paths covered by the manifest (everything except manifest.json). O(d log d)."""
    return sorted({ENTRY_FILE, PACKAGE_FILE, *(doc.target for doc in skill.docs)})


# --- Metadata ----------------------------------------------------------------------
def read_version(skill: Skill) -> str:
    """Keep a manually bumped version from an existing package.json. O(size of package.json)."""
    package_path = skill.root / PACKAGE_FILE
    if not package_path.is_file():
        return DEFAULT_VERSION
    return json.loads(package_path.read_text(encoding="utf-8")).get("version", DEFAULT_VERSION)


def read_description(skill: Skill) -> str:
    """Description from the SKILL.md frontmatter. O(size of SKILL.md)."""
    match = FRONTMATTER_DESCRIPTION.search((skill.root / ENTRY_FILE).read_text(encoding="utf-8"))
    return match.group(1).strip() if match else skill.name


def read_taleweaver_version(repo_root: Path) -> str:
    """TaleWeaver version from pyproject.toml, used as the minimum compatible version. O(1)."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return "0.0.0"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    poetry_version = data.get("tool", {}).get("poetry", {}).get("version")
    return poetry_version or data.get("project", {}).get("version", "0.0.0")


def documentation_entries(skill: Skill) -> list[dict[str, str]]:
    """Doc list shared by package.json and manifest.json. O(d)."""
    return [
        {"path": doc.target, "source": doc.source, "description": doc.description}
        | ({"alias_of": doc.source} if doc.alias else {})
        for doc in skill.docs
    ]


def build_package(skill: Skill, version: str) -> dict[str, Any]:
    """npm package configuration. O(d)."""
    return {
        "name": skill.name,
        "version": version,
        "description": read_description(skill),
        "main": ENTRY_FILE,
        "files": [*bundled_files(skill), MANIFEST_FILE],
        "keywords": ["taleweaver", "agent-skill", "world-builder", "interactive-fiction"],
        "license": "UNLICENSED",
        "private": True,
        "taleweaver": {
            "type": "agent-skill",
            "entry": ENTRY_FILE,
            "manifest": MANIFEST_FILE,
            "docs": documentation_entries(skill),
        },
    }


def file_entry(root: Path, relative: str) -> dict[str, Any]:
    """Manifest entry for one bundled file. O(file size) for hashing."""
    path = root / relative
    return {"path": relative, "sha256": sha256_file(path), "size": path.stat().st_size}


def build_manifest(skill: Skill, version: str) -> dict[str, Any]:
    """Distribution manifest with sha256 and size per file. O(total bytes) for hashing."""
    return {
        "schema": MANIFEST_SCHEMA,
        "name": skill.name,
        "version": version,
        "entry": ENTRY_FILE,
        "files": [file_entry(skill.root, relative) for relative in bundled_files(skill)],
        "documentation": documentation_entries(skill),
        "compatibility": {
            "taleweaver": f">={read_taleweaver_version(skill.repo_root)}",
            "agents": AGENT_TAGS,
            "formats": ["world-builder-blueprint", "adventure.adv", "adventure.adz"],
        },
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write pretty-printed UTF-8 JSON. O(size of data)."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --- Bundle ------------------------------------------------------------------------
def sync_docs(skill: Skill) -> None:
    """Copy every companion doc into the skill. O(total bytes)."""
    for doc in skill.docs:
        source = safe_join(skill.repo_root, doc.source)
        if not source.is_file():
            raise FileNotFoundError(f"Companion doc not found: {doc.source}")
        target = safe_join(skill.root, doc.target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def bundle(skill: Skill) -> dict[str, Any]:
    """Sync docs, then write package.json before manifest.json so the manifest can
    checksum package.json. O(total bytes). Returns the manifest."""
    version = read_version(skill)
    sync_docs(skill)
    write_json(skill.root / PACKAGE_FILE, build_package(skill, version))
    manifest = build_manifest(skill, version)
    write_json(skill.root / MANIFEST_FILE, manifest)
    return manifest


# --- Verification ------------------------------------------------------------------
def _load_json(path: Path, report: CheckReport) -> dict[str, Any] | None:
    """Parse a JSON file or record why it cannot be read. O(file size)."""
    if not path.is_file():
        report.errors.append(f"Missing {path.name}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.errors.append(f"Invalid JSON in {path.name}: {exc}")
        return None


def check_sources(skill: Skill, report: CheckReport) -> None:
    """Bundled docs must be exact copies of their repo source. O(total bytes)."""
    for doc in skill.docs:
        source = safe_join(skill.repo_root, doc.source)
        target = safe_join(skill.root, doc.target)
        if not target.is_file():
            report.errors.append(f"Missing bundled doc: {doc.target}")
            continue
        if source.is_file() and sha256_file(source) != sha256_file(target):
            report.errors.append(f"Stale bundled doc: {doc.target} differs from {doc.source}")


def check_manifest(skill: Skill, report: CheckReport) -> None:
    """Every manifest entry exists with matching sha256 and size. O(total bytes)."""
    manifest = _load_json(skill.root / MANIFEST_FILE, report)
    if manifest is None:
        return
    listed = [entry.get("path", "") for entry in manifest.get("files", [])]
    if sorted(listed) != bundled_files(skill):
        report.errors.append(f"manifest.json file list differs from {bundled_files(skill)}")
    for entry in manifest.get("files", []):
        path = safe_join(skill.root, entry["path"])
        if not path.is_file():
            report.errors.append(f"Manifest file missing: {entry['path']}")
            continue
        if sha256_file(path) != entry.get("sha256") or path.stat().st_size != entry.get("size"):
            report.errors.append(f"Checksum or size mismatch: {entry['path']}")


def check_package(skill: Skill, report: CheckReport) -> None:
    """package.json `main` and `files` must resolve inside the skill. O(f)."""
    package = _load_json(skill.root / PACKAGE_FILE, report)
    if package is None:
        return
    if package.get("name") != skill.name:
        report.errors.append(f"package.json name is not '{skill.name}'")
    report.errors.extend(
        f"package.json references missing file: {relative}"
        for relative in [package.get("main", ""), *package.get("files", [])]
        if not safe_join(skill.root, relative).is_file()
    )


def check_skill_references(skill: Skill, report: CheckReport) -> None:
    """Every `docs/...md` reference in SKILL.md resolves, and every primary doc is
    referenced. O(size of SKILL.md + d)."""
    referenced = set(SKILL_DOC_REF.findall((skill.root / ENTRY_FILE).read_text(encoding="utf-8")))
    report.errors.extend(
        f"SKILL.md references missing doc: {relative}"
        for relative in sorted(referenced)
        if not safe_join(skill.root, relative).is_file()
    )
    report.errors.extend(
        f"SKILL.md does not reference {doc.target}"
        for doc in skill.docs
        if not doc.alias and doc.target not in referenced
    )


def check_doc_links(skill: Skill, report: CheckReport) -> None:
    """Relative Markdown links between bundled docs. Broken links are warnings because
    bundled docs are exact copies of the repo docs. O(total bytes)."""
    for doc in skill.docs:
        target = skill.root / doc.target
        if doc.alias or not target.is_file():
            continue
        links = MARKDOWN_LINK.findall(target.read_text(encoding="utf-8"))
        local = [link for link in links if not re.match(r"^[a-z]+:", link)]
        missing = [link for link in local if not (target.parent / link).resolve().is_file()]
        report.warnings.extend(f"{doc.target}: link not bundled: {link}" for link in missing)


CHECKS = (check_sources, check_manifest, check_package, check_skill_references, check_doc_links)


def verify(skill: Skill) -> CheckReport:
    """Run every check. O(total bytes)."""
    report = CheckReport()
    for check in CHECKS:
        check(skill, report)
    return report


# --- Export ------------------------------------------------------------------------
def _reset_tar_owner(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Drop local owner data so archives are reproducible. O(1)."""
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def _write_zip(archive: Path, root: Path, prefix: str, members: list[str]) -> None:
    """Deflated zip of `members` under `prefix/`. O(total bytes)."""
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for relative in members:
            zf.write(root / relative, f"{prefix}/{relative}")


def _write_tar(archive: Path, root: Path, prefix: str, members: list[str]) -> None:
    """Gzipped tar of `members` under `prefix/`. O(total bytes)."""
    with tarfile.open(archive, "w:gz") as tf:
        for relative in members:
            tf.add(root / relative, f"{prefix}/{relative}", filter=_reset_tar_owner)


ARCHIVE_WRITERS = {"zip": _write_zip, "tar.gz": _write_tar}


def export_archive(skill: Skill, archive_format: str, output_dir: Path) -> Path:
    """Write `<name>-<version>.<ext>` with every bundled file under a `<name>/` prefix.
    Refuses to export a bundle that fails verification. O(total bytes)."""
    if archive_format not in ARCHIVE_SUFFIXES:
        raise ValueError(f"Unsupported archive format: {archive_format}")
    report = verify(skill)
    if not report.ok:
        raise RuntimeError("Bundle verification failed:\n  " + "\n  ".join(report.errors))
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{skill.name}-{read_version(skill)}{ARCHIVE_SUFFIXES[archive_format]}"
    members = [*bundled_files(skill), MANIFEST_FILE]
    ARCHIVE_WRITERS[archive_format](archive, skill.root, skill.name, members)
    return archive


# --- CLI ---------------------------------------------------------------------------
def print_report(report: CheckReport) -> None:
    """Print warnings, errors and a summary line. O(warnings + errors)."""
    status = "Check passed." if report.ok else f"Check failed with {len(report.errors)} error(s)."
    warnings = [f"WARNING: {w}" for w in report.warnings]
    print("\n".join([*warnings, *(f"ERROR: {e}" for e in report.errors), status]))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. O(len(argv))."""
    parser = argparse.ArgumentParser(description="Bundle a TaleWeaver agent skill.")
    parser.add_argument("--skill", default=DEFAULT_SKILL, help="Skill name or path")
    parser.add_argument("--check", action="store_true", help="Verify only, write nothing")
    parser.add_argument(
        "--export-archive",
        choices=sorted(ARCHIVE_SUFFIXES),
        help="Export a verified bundle as a distribution archive",
    )
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "dist", help="Archive output directory"
    )
    return parser.parse_args(argv)


def run_export(skill: Skill, archive_format: str, output_dir: Path) -> int:
    """Export an archive and return the exit code. O(total bytes)."""
    try:
        archive = export_archive(skill, archive_format, output_dir)
    except RuntimeError as exc:
        print(f"ERROR: {exc}\nRun `python scripts/bundle_skill.py` to rebuild the bundle.")
        return 1
    print(f"Exported {archive}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: bundle (default), --check or --export-archive. O(total bytes)."""
    args = parse_args(argv)
    try:
        skill = resolve_skill(args.skill)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}")
        return 2
    if args.check:
        report = verify(skill)
        print_report(report)
        return 0 if report.ok else 1
    if args.export_archive:
        return run_export(skill, args.export_archive, args.output)
    manifest = bundle(skill)
    print(f"Bundled {skill.name} {manifest['version']} ({len(manifest['files'])} files)")
    print_report(verify(skill))
    return 0


if __name__ == "__main__":
    sys.exit(main())
