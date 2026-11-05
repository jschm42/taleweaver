"""Tests for scripts/bundle_skill.py and the committed adventure-concept-creator bundle."""

import importlib.util
import json
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "taleweaver-adventure-concept-creator"

_spec = importlib.util.spec_from_file_location(
    "bundle_skill", REPO_ROOT / "scripts" / "bundle_skill.py"
)
bundle_skill = importlib.util.module_from_spec(_spec)
sys.modules["bundle_skill"] = bundle_skill
_spec.loader.exec_module(bundle_skill)


@pytest.fixture
def repo_skill():
    return bundle_skill.resolve_skill(SKILL_NAME)


@pytest.fixture
def tmp_skill(tmp_path):
    """Isolated repo copy with the skill entry and its doc sources, not yet bundled."""
    skill_dir = tmp_path / ".agents" / "skills" / SKILL_NAME
    skill_dir.mkdir(parents=True)
    shutil.copyfile(
        REPO_ROOT / ".agents" / "skills" / SKILL_NAME / "SKILL.md", skill_dir / "SKILL.md"
    )
    for doc in bundle_skill.BUNDLES[SKILL_NAME]:
        source = tmp_path / doc.source
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / doc.source, source)
    shutil.copyfile(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    return bundle_skill.resolve_skill(SKILL_NAME, repo_root=tmp_path)


# --- Committed bundle ---------------------------------------------------------------


def test_committed_bundle_files_exist(repo_skill):
    # Arrange
    expected = bundle_skill.bundled_files(repo_skill) + [bundle_skill.MANIFEST_FILE]

    # Act
    missing = [path for path in expected if not (repo_skill.root / path).is_file()]

    # Assert
    assert missing == []
    assert "docs/scripting-enginge.md" in expected
    assert "docs/specs/adventure_format.md" in expected


def test_committed_bundle_passes_check(repo_skill):
    # Act
    report = bundle_skill.verify(repo_skill)

    # Assert
    assert report.errors == [], "Run `python scripts/bundle_skill.py` to rebuild the bundle"


def test_committed_manifest_checksums_match(repo_skill):
    # Arrange
    manifest = json.loads((repo_skill.root / "manifest.json").read_text(encoding="utf-8"))

    # Act / Assert
    for entry in manifest["files"]:
        path = repo_skill.root / entry["path"]
        assert bundle_skill.sha256_file(path) == entry["sha256"], entry["path"]
        assert path.stat().st_size == entry["size"], entry["path"]


def test_committed_package_json(repo_skill):
    # Arrange
    package = json.loads((repo_skill.root / "package.json").read_text(encoding="utf-8"))

    # Act
    doc_paths = [doc["path"] for doc in package["taleweaver"]["docs"]]

    # Assert
    assert package["name"] == SKILL_NAME
    assert package["main"] == "SKILL.md"
    assert "manifest.json" in package["files"]
    assert all((repo_skill.root / path).is_file() for path in package["files"])
    assert "docs/world-builder-syntax.md" in doc_paths


def test_skill_md_references_resolve(repo_skill):
    # Arrange
    text = (repo_skill.root / "SKILL.md").read_text(encoding="utf-8")

    # Act
    references = set(bundle_skill.SKILL_DOC_REF.findall(text))

    # Assert
    assert "## References" in text
    assert {
        "docs/world-builder-syntax.md",
        "docs/world-builder-blueprint-manual.md",
        "docs/scripting_engine.md",
        "docs/specs/adventure_format.md",
    } <= references
    assert all((repo_skill.root / ref).is_file() for ref in references)


def test_alias_is_identical_copy(repo_skill):
    # Act
    alias = bundle_skill.sha256_file(repo_skill.root / "docs" / "scripting-enginge.md")
    original = bundle_skill.sha256_file(repo_skill.root / "docs" / "scripting_engine.md")

    # Assert
    assert alias == original


def test_check_cli_passes():
    # Act
    exit_code = bundle_skill.main(["--check"])

    # Assert
    assert exit_code == 0


# --- Bundling in an isolated repo ---------------------------------------------------


def test_bundle_then_check_passes(tmp_skill):
    # Act
    manifest = bundle_skill.bundle(tmp_skill)
    report = bundle_skill.verify(tmp_skill)

    # Assert
    assert report.ok, report.errors
    assert manifest["entry"] == "SKILL.md"
    assert manifest["compatibility"]["taleweaver"].startswith(">=")
    assert [entry["path"] for entry in manifest["files"]] == bundle_skill.bundled_files(tmp_skill)


def test_check_detects_tampered_file(tmp_skill):
    # Arrange
    bundle_skill.bundle(tmp_skill)
    tampered = tmp_skill.root / "docs" / "world-builder-syntax.md"
    tampered.write_text(tampered.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")

    # Act
    report = bundle_skill.verify(tmp_skill)

    # Assert
    assert not report.ok
    assert any(
        "Checksum or size mismatch: docs/world-builder-syntax.md" in e for e in report.errors
    )
    assert any("Stale bundled doc: docs/world-builder-syntax.md" in e for e in report.errors)


def test_check_detects_missing_bundle(tmp_skill):
    # Act
    report = bundle_skill.verify(tmp_skill)

    # Assert
    assert any("Missing manifest.json" in e for e in report.errors)
    assert any("Missing bundled doc" in e for e in report.errors)


def test_bundle_keeps_bumped_version(tmp_skill):
    # Arrange
    bundle_skill.bundle(tmp_skill)
    package_path = tmp_skill.root / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = "2.1.0"
    package_path.write_text(json.dumps(package), encoding="utf-8")

    # Act
    manifest = bundle_skill.bundle(tmp_skill)

    # Assert
    assert manifest["version"] == "2.1.0"


def test_resolve_skill_rejects_path_traversal(tmp_skill):
    # Act / Assert
    with pytest.raises(ValueError):
        bundle_skill.resolve_skill("../../docs", repo_root=tmp_skill.repo_root)


# --- Archive export -----------------------------------------------------------------


@pytest.mark.parametrize("archive_format", ["tar.gz", "zip"])
def test_export_archive(tmp_skill, tmp_path, archive_format):
    # Arrange
    bundle_skill.bundle(tmp_skill)
    expected = {f"{SKILL_NAME}/{p}" for p in bundle_skill.bundled_files(tmp_skill)}
    expected.add(f"{SKILL_NAME}/manifest.json")

    # Act
    archive = bundle_skill.export_archive(tmp_skill, archive_format, tmp_path / "dist")

    # Assert
    assert archive.name == f"{SKILL_NAME}-1.0.0.{archive_format}"
    if archive_format == "zip":
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
    else:
        with tarfile.open(archive, "r:gz") as tf:
            names = set(tf.getnames())
    assert names == expected


def test_export_archive_refuses_unverified_bundle(tmp_skill, tmp_path):
    # Act / Assert
    with pytest.raises(RuntimeError):
        bundle_skill.export_archive(tmp_skill, "zip", tmp_path / "dist")
    assert not (tmp_path / "dist").exists()
