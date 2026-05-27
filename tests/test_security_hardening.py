import os

import pytest

from backend.api.routes.adventures.assets import _build_uploaded_visual_path
from backend.api.routes.adventures.agent_logic import _resolve_session_issue_log_path
from backend.api.routes.config_api import _build_catalog_upload_path, _route_error_response
from backend.core.config import settings
from backend.engine.media_engine import _build_output_filepath
from backend.engine.session_importer import _ensure_within_base_dir
from backend.engine.tts_engine import _build_audio_output_path, _strip_vocal_tags


def test_strip_vocal_tags_removes_bracketed_segments():
    text = "[whispers] Hello there (softly) traveler."

    result = _strip_vocal_tags(text)

    assert result == "Hello there  traveler."


def test_build_audio_output_path_stays_inside_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    result = _build_audio_output_path("adv-1", "session-1", "mp3")

    assert result.startswith(str(tmp_path))
    assert result.endswith(".mp3")


def test_build_output_filepath_rejects_external_absolute_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    with pytest.raises(ValueError):
        _build_output_filepath(str(tmp_path.parent), "../evil.png", "png")


def test_build_catalog_upload_path_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    with pytest.raises(ValueError):
        _build_catalog_upload_path("../catalog", "tile", "image.png")


def test_build_uploaded_visual_path_sanitizes_target_and_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    result = _build_uploaded_visual_path("template_1", "protagonist", "Hero ../Name", "portrait.exe")

    assert result.startswith(str(tmp_path))
    assert "/protagonist/" in result.replace("\\", "/")
    assert result.endswith(".png")
    assert os.path.basename(result).startswith("hero-name_")


def test_route_error_response_hides_exception_details():
    response = _route_error_response("Catalog upload", "Upload failed.", RuntimeError("secret token leaked"))

    assert response == {"status": "error", "message": "Upload failed."}


def test_resolve_session_issue_log_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    with pytest.raises(ValueError):
        _resolve_session_issue_log_path("../outside")


def test_ensure_within_base_dir_rejects_escape(tmp_path):
    base_dir = tmp_path / "adventures" / "sessions" / "session-1"
    base_dir.mkdir(parents=True, exist_ok=True)

    escaped = base_dir / ".." / ".." / "users" / "owned.txt"
    with pytest.raises(ValueError):
        _ensure_within_base_dir(str(escaped), str(base_dir))
