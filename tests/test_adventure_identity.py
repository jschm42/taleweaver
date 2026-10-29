"""
Tests for the stable adventure identity (origin_id) used to detect updates across title changes.
"""

import os

import pytest

from backend.core.adventure_identity import manifest_origin_id
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.adventures.adventure_import_support import find_existing_template
from backend.engine.adventures.adventure_updates import find_matching_file_for_template
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User


def _file(title: str, stem: str, origin_id: str | None) -> dict:
    return {
        "file_path": f"/fake/{stem}.adz",
        "stem": stem,
        "title": title,
        "origin_id": origin_id,
        "version": "3.0.0",
        "format_version": "1.3",
        "has_sequences": True,
    }


def test_manifest_origin_id_reads_only_adventure_section():
    """Top-level origin_id (legacy LLM start scene) is ignored; blanks are None."""
    assert manifest_origin_id({"adventure": {"origin_id": " abc "}}) == "abc"
    assert manifest_origin_id({"origin_id": "ENTRANCE_HALL", "adventure": {}}) is None
    assert manifest_origin_id({"adventure": {"origin_id": ""}}) is None
    assert manifest_origin_id(None) is None


def test_origin_id_match_wins_over_title():
    """A renamed adventure is still matched by its origin_id."""
    template = AdventureTemplate(title="Old Name", origin_id="id-1")
    files = [_file("Old Name", "Old_Name", "id-other"), _file("New Name", "New_Name", "id-1")]

    assert find_matching_file_for_template(template, files)["origin_id"] == "id-1"


def test_different_origin_ids_never_match_by_title():
    """Same title but different identities are different adventures (e.g. a user's own one)."""
    template = AdventureTemplate(title="Kitchen Crisis", origin_id="mine")
    files = [_file("Kitchen Crisis", "Kitchen_Crisis", "sample")]

    assert find_matching_file_for_template(template, files) is None


def test_legacy_template_falls_back_to_filename_stem():
    """Templates without origin_id still find their sample via title/filename stem."""
    template = AdventureTemplate(title="Crazy Job Interview", origin_id=None)
    files = [_file("Crazy Job Interview (Copy)", "Crazy_Job_Interview", "sample")]

    assert find_matching_file_for_template(template, files)["origin_id"] == "sample"


@pytest.mark.asyncio
async def test_find_existing_template_prefers_origin_and_skips_foreign_titles(db_session):
    """Import conflicts match by origin_id; title only matches legacy templates without one."""
    user = User(id="identity-user", username="identity_user", hashed_password="pw")
    renamed = AdventureTemplate(id="tpl-renamed", title="Renamed", owner_id=user.id, origin_id="o1")
    foreign = AdventureTemplate(id="tpl-foreign", title="Shared", owner_id=user.id, origin_id="o2")
    db_session.add_all([user, renamed, foreign])
    await db_session.commit()

    by_origin = await find_existing_template(db_session, user.id, "Original", "o1")
    foreign_title = await find_existing_template(db_session, user.id, "Shared", "o3")

    assert by_origin.id == "tpl-renamed"
    assert foreign_title is None


@pytest.mark.asyncio
async def test_export_assigns_and_keeps_origin_id(db_session):
    """Exporting a legacy template assigns a stable origin_id that later exports reuse."""
    template = AdventureTemplate(id="tpl-export-identity", title="Exported", origin_id=None)
    db_session.add(template)
    await db_session.commit()

    first = await AdventureExporter.build_full_manifest(db_session, template.id)
    second = await AdventureExporter.build_full_manifest(db_session, template.id)

    assert first["adventure"]["origin_id"]
    assert first["adventure"]["origin_id"] == second["adventure"]["origin_id"]


def test_bundled_adventures_have_unique_identity_and_clean_titles():
    """Shipped samples need an origin_id for updates and must not carry export suffixes."""
    from backend.engine.adventures.adventure_updates import scan_available_adventure_files

    repo_adventures = os.path.abspath(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "adventures")
    )
    bundled = [
        f
        for f in scan_available_adventure_files(force_refresh=True)
        if os.path.abspath(f["file_path"]).startswith(repo_adventures)
        and f["file_path"].endswith(".adz")
    ]
    origin_ids = [f["origin_id"] for f in bundled]

    assert bundled
    assert all(origin_ids)
    assert len(set(origin_ids)) == len(origin_ids)
    assert not [f["title"] for f in bundled if "(Copy)" in f["title"] or "(Argon)" in f["title"]]
