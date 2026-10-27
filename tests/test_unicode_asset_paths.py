"""Unicode path components retain the same traversal and containment restrictions."""

import ipaddress
from pathlib import Path

import pytest

from backend.core.config import settings
from backend.utils import path_security
from backend.utils.text_utils import generate_session_id


@pytest.mark.parametrize(
    "title", ["Бегство из леса", "森からの脱出", "رحلة الغابة", "El bosque mágico"]
)
def test_generated_id_and_local_image_roundtrip(tmp_path, monkeypatch, title):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    session_id = generate_session_id(title)
    assert path_security.sanitize_path_component(session_id) == session_id
    folder = path_security.safe_data_path("adventures", "sessions", session_id, "visuals")
    Path(folder).mkdir(parents=True)
    image = Path(folder) / "портрет.png"
    image.write_bytes(b"fixture")
    url = path_security.local_path_to_data_url(str(image))
    assert path_security.data_url_to_local_path(url) == str(image)


@pytest.mark.parametrize(
    "component",
    [
        "../лес",
        "лес/../other",
        "лес\\..\\other",
        "/лес",
        "C:\\лес",
        "C:лес",
        "лес%2f..%2fother",
        "лес\x00",
        "ле\nс",
        "..",
        ".",
        "лес∕other",
        "лес／other",
        "лес\u202eevil",
        "лес\u200bother",
        "а" * 129,
    ],
)
def test_unsafe_unicode_components_are_rejected(tmp_path, monkeypatch, component):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    assert path_security.sanitize_path_component(component) != component
    with pytest.raises(ValueError):
        path_security.safe_data_path("adventures", "sessions", component)


def test_unicode_symlink_cannot_escape_data_directory(tmp_path, monkeypatch):
    data = tmp_path / "data"
    outside = tmp_path / "outside"
    data.mkdir()
    outside.mkdir()
    try:
        (data / "лес").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Symlink privileges not available on this Windows host")
        raise
    monkeypatch.setattr(settings, "DATA_DIR", str(data))
    with pytest.raises(ValueError, match="escapes"):
        path_security.safe_data_path("лес", "visuals")
    with pytest.raises(ValueError, match="escapes"):
        path_security.data_url_to_local_path("/data/лес/portrait.png")


@pytest.mark.parametrize("addresses", [[], ["127.0.0.1"], ["1.1.1.1", "192.168.1.1"]])
def test_provider_url_still_rejects_unresolved_or_private_hosts(monkeypatch, addresses):
    monkeypatch.setattr(
        path_security, "_resolve_host_ips", lambda _: [ipaddress.ip_address(ip) for ip in addresses]
    )
    with pytest.raises(ValueError):
        path_security.validate_provider_url("https://example.invalid", allow_private=False)


def test_provider_url_accepts_public_or_explicit_local_hosts(monkeypatch):
    monkeypatch.setattr(
        path_security, "_resolve_host_ips", lambda _: [ipaddress.ip_address("1.1.1.1")]
    )
    assert (
        path_security.validate_provider_url("https://example.invalid", allow_private=False)
        == "https://example.invalid"
    )
    assert (
        path_security.validate_provider_url("http://127.0.0.1:8188", allow_private=True)
        == "http://127.0.0.1:8188"
    )
