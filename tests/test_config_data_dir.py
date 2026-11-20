"""Unit tests for DATA_DIR fallback behavior in app settings."""

from backend.core.config import Settings


def test_data_dir_defaults_to_data_when_env_missing(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    cfg = Settings(_env_file=None)

    assert cfg.DATA_DIR == "data"
    assert cfg.DATABASE_URL == "sqlite+aiosqlite:///./data/taleweaver.db"


def test_data_dir_defaults_to_data_when_env_empty(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    cfg = Settings(_env_file=None)

    assert cfg.DATA_DIR == "data"
    assert cfg.DATABASE_URL == "sqlite+aiosqlite:///./data/taleweaver.db"


def test_data_dir_uses_explicit_env_value(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "custom_store")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    cfg = Settings(_env_file=None)

    assert cfg.DATA_DIR == "custom_store"
    assert cfg.DATABASE_URL == "sqlite+aiosqlite:///./custom_store/taleweaver.db"
