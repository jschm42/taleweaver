"""LLM-facing output schemas for the turn pipeline (Pass 1).

The engine-side models (`GameEvent`, `AdventureGeneratorToolIntent`) also carry
backend-filled result fields and adventure-generator tools. Sending those to the
model inflates the structured-output schema (and the prompt-injected schema in
JSON mode) without ever being useful, so the passes request these trimmed intents
and convert them back into engine models afterwards.
"""

from copy import copy
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model

from backend.engine.rule_engine import AdventureGeneratorToolIntent, ExitUpdate, GameEvent

# Filled by the backend after dice rolls / tool execution; the LLM must never set them.
_BACKEND_RESULT_FIELDS = {"skill_check_results", "attack_results", "tool_results"}
# Adventure-generator tools are only valid in generator chat mode.
_GENERATOR_TOOL_FIELDS = {
    "request_available_image_styles",
    "request_available_tones",
    "requested_adventure_generation",
}
# Scene labels/images are resolved from the database, never from the LLM.
_DB_RESOLVED_FIELDS = {"scene_label", "image_prompt"}


def _derive_model(
    name: str,
    base: type[BaseModel],
    exclude: set[str],
    extra_fields: dict[str, Any] | None = None,
) -> type[BaseModel]:
    fields: dict[str, Any] = {
        field_name: (field.annotation, copy(field))
        for field_name, field in base.model_fields.items()
        if field_name not in exclude
    }
    fields.update(extra_fields or {})
    return create_model(name, __config__=ConfigDict(extra="ignore"), **fields)


MechanicsIntent = _derive_model(
    "MechanicsIntent",
    GameEvent,
    _BACKEND_RESULT_FIELDS | _GENERATOR_TOOL_FIELDS | _DB_RESOLVED_FIELDS,
)
"""Pass 1 schema for strict/story adventures."""

ChatProgressionIntent = _derive_model(
    "ChatProgressionIntent",
    AdventureGeneratorToolIntent,
    _BACKEND_RESULT_FIELDS | _GENERATOR_TOOL_FIELDS,
    extra_fields={"updated_exits": (list[ExitUpdate] | None, None)},
)
"""Pass 1 schema for the chat-mode progression rule pass."""


def to_game_event(intent: BaseModel) -> GameEvent:
    """Converts a Pass 1 intent (or an already complete GameEvent) into a GameEvent."""
    if isinstance(intent, GameEvent):
        return intent
    return GameEvent.model_validate(intent.model_dump(exclude_none=True))
