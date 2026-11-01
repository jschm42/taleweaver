"""Base class for world-generation schemas: tolerates the null/empty keys LLMs emit."""

from typing import Any

from pydantic import BaseModel, model_validator

_EMPTY_VALUES: tuple[Any, ...] = (None, "", [], {})


def _drop_empty_unknown_keys(model: type[BaseModel], data: dict[str, Any]) -> dict[str, Any]:
    """Remove keys the model does not declare when their value carries no content.

    LLMs pattern-complete field names (e.g. ``on_success_script_text`` next to the
    ``on_*_script`` / ``on_*_text`` pairs) and emit them as null. Under
    ``extra="forbid"`` one such empty key would fail the whole manifest, so it is
    dropped here; unknown keys that carry content still fail validation.
    """
    known = set(model.model_fields)
    known.update(f.alias for f in model.model_fields.values() if f.alias)
    return {k: v for k, v in data.items() if k in known or v not in _EMPTY_VALUES}


class WorldBaseSchema(BaseModel):
    """Base schema for world generation models that normalizes null LLM outputs."""

    @model_validator(mode="before")
    @classmethod
    def normalize_null_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if cls.model_config.get("extra") == "forbid":
            data = _drop_empty_unknown_keys(cls, data)
        for field_name, field_info in cls.model_fields.items():
            key = field_info.alias if field_info.alias and field_info.alias in data else field_name
            if key not in data or data[key] is not None:
                continue
            if field_info.default == "":
                data[key] = ""
                continue
            if field_info.default_factory is list or field_info.default == []:
                data[key] = []
        return data
