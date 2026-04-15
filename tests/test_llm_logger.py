"""Tests for the structured LLM debug logger."""

import json

from backend.core import llm_logger


def test_structured_logging_appends_jsonl_entries(tmp_path, monkeypatch):
    """Structured events and LLM turns are appended as parseable JSONL rows."""
    log_dir = tmp_path / "logs"
    log_file = log_dir / "llm_debug.jsonl"
    monkeypatch.setattr(llm_logger, "LOG_DIR", str(log_dir))
    monkeypatch.setattr(llm_logger, "LOG_FILE", str(log_file))

    llm_logger.log_structured_event(
        "adventure.generation.started",
        adventure_id="adv-123",
        title="Test Adventure",
        phase="analysis",
    )
    llm_logger.log_llm_interaction(
        model="gpt-4o-mini",
        provider="openai",
        system_prompt="system prompt",
        user_prompt="user prompt",
        response_content="response content",
        raw_response={"choices": []},
        event_type="gm.turn.response",
        adventure_id="adv-123",
        game_id="game-123",
        operation="generate_world",
        phase="analysis",
        metadata={"scene_count": 5},
    )

    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])

    assert first["event_type"] == "adventure.generation.started"
    assert first["adventure_id"] == "adv-123"
    assert second["event_type"] == "gm.turn.response"
    assert second["game_id"] == "game-123"
    assert second["metadata"]["scene_count"] == 5