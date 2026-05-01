import os
import json
import datetime
import logging
from typing import Any, Optional, Dict

from backend.core.config import settings

LOG_DIR = os.path.join(settings.DATA_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "llm_debug.jsonl")

logger = logging.getLogger(__name__)

MAX_LOG_TEXT_LENGTH = 12000


def _truncate_text(value: Any, max_length: int = MAX_LOG_TEXT_LENGTH) -> Any:
    if isinstance(value, str) and len(value) > max_length:
        return value[:max_length] + "...[truncated]"
    return value


def _prepare_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _prepare_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_prepare_value(item) for item in value]
    if isinstance(value, tuple):
        return [_prepare_value(item) for item in value]
    return _truncate_text(value)


def _write_entry(entry: Dict[str, Any]) -> None:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(_prepare_value(entry), ensure_ascii=False, default=str) + "\n")
    except OSError as exc:
        logger.error("Failed to write to LLM debug log: %s", exc)


def log_structured_event(event_type: str, **fields: Any) -> None:
    """Appends a structured lifecycle event to the JSONL debug log."""
    _write_entry(
        {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event_type": event_type,
            **fields,
        }
    )

def log_llm_interaction(
    model: str,
    provider: str,
    system_prompt: str,
    user_prompt: str,
    response_content: str,
    raw_response: Optional[dict] = None,
    *,
    event_type: str = "llm_interaction",
    adventure_id: Optional[str] = None,
    game_id: Optional[str] = None,
    operation: Optional[str] = None,
    phase: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Logs an LLM interaction to a local JSONL file for debugging.
    """
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event_type": event_type,
        "model": model,
        "provider": provider,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response": response_content,
        "raw_response": raw_response,
        "adventure_id": adventure_id,
        "game_id": game_id,
        "operation": operation,
        "phase": phase,
        "metadata": metadata,
    }

    _write_entry(entry)
