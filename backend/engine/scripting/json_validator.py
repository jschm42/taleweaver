"""JSON parsing and lightweight schema validation for adventure scripts (``tw.llm.ask_json``)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any, Optional

from backend.core.llm_json_repair import attempt_repair_truncated_json, repair_json

_FENCE_JSON_RE = re.compile(r"^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$", re.IGNORECASE)
_THINK_BLOCK_RE = re.compile(r"<think>[\s\S]*?(?:</think>|$)", re.IGNORECASE)

_TYPE_CHECKERS: dict[str, Callable[[Any], bool]] = {
    "str": lambda v: isinstance(v, str),
    "string": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "list": lambda v: isinstance(v, list),
    "array": lambda v: isinstance(v, list),
    "dict": lambda v: isinstance(v, dict),
    "object": lambda v: isinstance(v, dict),
    "any": lambda _v: True,
}

_PYTHON_TYPE_MAP: dict[Any, str] = {
    str: "str",
    int: "int",
    float: "float",
    bool: "bool",
    list: "list",
    dict: "dict",
}


def extract_json_candidate(raw: str) -> str:
    """Strips thinking tags and markdown fences, returning the JSON slice."""
    cleaned = _THINK_BLOCK_RE.sub("", str(raw or "")).strip()
    fence = _FENCE_JSON_RE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()

    first_idx = next((i for i, ch in enumerate(cleaned) if ch in "{["), -1)
    last_idx = next(
        (len(cleaned) - 1 - i for i, ch in enumerate(reversed(cleaned)) if ch in "}]"),
        -1,
    )
    if 0 <= first_idx < last_idx:
        return cleaned[first_idx : last_idx + 1]
    return cleaned


def parse_llm_json(raw: str) -> tuple[Any, Optional[str]]:
    """Parses JSON from LLM text with best-effort repair. Returns ``(value, error)``."""
    candidate = extract_json_candidate(raw)
    if not candidate:
        return None, "empty JSON response"

    for attempt in (
        candidate,
        repair_json(candidate),
        attempt_repair_truncated_json(candidate),
    ):
        if not attempt:
            continue
        try:
            return json.loads(attempt), None
        except json.JSONDecodeError:
            continue
    return None, "invalid JSON syntax"


def _resolve_type_name(spec: Any) -> Optional[str]:
    if isinstance(spec, type) and spec in _PYTHON_TYPE_MAP:
        return _PYTHON_TYPE_MAP[spec]
    if isinstance(spec, str):
        lowered = spec.strip().lower()
        return lowered if lowered in _TYPE_CHECKERS else None
    return None


def _check_number_bounds(value: Any, spec: dict[str, Any], path: str) -> Optional[str]:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    min_val = spec.get("min")
    max_val = spec.get("max")
    if isinstance(min_val, (int, float)) and value < min_val:
        return f"{path}: {value} is less than min {min_val}"
    if isinstance(max_val, (int, float)) and value > max_val:
        return f"{path}: {value} is greater than max {max_val}"
    return None


def _check_length_bounds(value: Any, spec: dict[str, Any], path: str) -> Optional[str]:
    if not isinstance(value, (str, list, dict)):
        return None
    min_len = spec.get("min_len")
    max_len = spec.get("max_len")
    if isinstance(min_len, int) and len(value) < min_len:
        return f"{path}: length {len(value)} is less than min_len {min_len}"
    if isinstance(max_len, int) and len(value) > max_len:
        return f"{path}: length {len(value)} is greater than max_len {max_len}"
    return None


def _check_bounds(value: Any, spec: dict[str, Any], path: str) -> Optional[str]:
    err = _check_number_bounds(value, spec, path) or _check_length_bounds(value, spec, path)
    if err:
        return err
    enum_vals = spec.get("enum")
    if isinstance(enum_vals, (list, tuple)) and value not in enum_vals:
        return f"{path}: value {value!r} not in allowed enum {list(enum_vals)!r}"
    return None


def _validate_list_items(value: list[Any], item_spec: Any, path: str) -> Optional[str]:
    for idx, item in enumerate(value):
        err = validate_json_schema(item, item_spec, f"{path}[{idx}]")
        if err:
            return err
    return None


def _validate_typed_dict_spec(
    value: Any, type_key: Any, spec: dict[str, Any], path: str
) -> Optional[str]:
    tname = _resolve_type_name(type_key)
    if tname is None:
        return f"{path}: unknown schema type {type_key!r}"
    if not _TYPE_CHECKERS[tname](value):
        return f"{path}: expected {tname}, got {type(value).__name__}"
    err = _check_bounds(value, spec, path)
    if err:
        return err
    if "items" in spec and isinstance(value, list):
        return _validate_list_items(value, spec["items"], path)
    if "fields" in spec and isinstance(spec["fields"], dict):
        return _validate_object_fields(value, spec["fields"], path)
    return None


def _validate_dict_spec(value: Any, spec: dict[str, Any], path: str) -> Optional[str]:
    type_key = spec.get("type")
    if type_key is not None:
        return _validate_typed_dict_spec(value, type_key, spec, path)
    return _validate_object_fields(value, spec, path)


def _validate_object_fields(value: Any, fields: dict[str, Any], path: str) -> Optional[str]:
    if not isinstance(value, dict):
        return f"{path}: expected dict/object, got {type(value).__name__}"
    for key, field_spec in fields.items():
        key_str = str(key)
        optional = isinstance(field_spec, dict) and bool(field_spec.get("optional"))
        if key_str not in value:
            if optional:
                continue
            return f"{path}: missing required key '{key_str}'"
        if value[key_str] is None and optional:
            continue
        err = validate_json_schema(value[key_str], field_spec, f"{path}.{key_str}")
        if err:
            return err
    return None


def _validate_list_schema(value: Any, schema: list[Any], path: str) -> Optional[str]:
    if not isinstance(value, list):
        return f"{path}: expected list, got {type(value).__name__}"
    if len(schema) == 1:
        return _validate_list_items(value, schema[0], path)
    return None


def validate_json_schema(value: Any, schema: Any, path: str = "$") -> Optional[str]:
    """Validates ``value`` against a lightweight sandbox schema. Returns error string or None."""
    if schema is None:
        return None
    tname = _resolve_type_name(schema)
    if tname is not None:
        return (
            None
            if _TYPE_CHECKERS[tname](value)
            else f"{path}: expected {tname}, got {type(value).__name__}"
        )
    if isinstance(schema, list):
        return _validate_list_schema(value, schema, path)
    if isinstance(schema, dict):
        return _validate_dict_spec(value, schema, path)
    return f"{path}: unsupported schema specification"


def schema_prompt_hint(schema: Any) -> str:
    """Builds a compact human/LLM-readable JSON structure instruction from ``schema``."""
    if schema is None:
        return "Return ONLY valid JSON (an object or array), without markdown fences or prose."
    try:
        rendered = _describe_schema(schema)
        return (
            "Return ONLY valid JSON matching this schema (no markdown fences, no commentary): "
            f"{json.dumps(rendered, ensure_ascii=False)}"
        )
    except Exception:
        return "Return ONLY valid JSON matching the requested structure, without markdown fences."


def _describe_schema(schema: Any) -> Any:
    tname = _resolve_type_name(schema)
    if tname is not None:
        return tname
    if isinstance(schema, list):
        return [_describe_schema(schema[0])] if len(schema) == 1 else "list"
    if isinstance(schema, dict):
        if "type" in schema:
            desc = str(_resolve_type_name(schema.get("type")) or schema.get("type"))
            details = [
                f"{k}={schema[k]}"
                for k in ("min", "max", "min_len", "max_len", "enum")
                if k in schema
            ]
            if "items" in schema:
                details.append(f"items={_describe_schema(schema['items'])}")
            return f"{desc} ({', '.join(details)})" if details else desc
        return {str(k): _describe_schema(v) for k, v in schema.items()}
    return str(schema)
