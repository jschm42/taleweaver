"""Shared LLM latency and telemetry analytics service."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from backend.core.config import PROJECT_ROOT, settings

_DEFAULT_LOG_NAMES = ("llm_debug.jsonl", "llm_telemetry.jsonl")


def _logs_root() -> Path:
    return (PROJECT_ROOT / settings.DATA_DIR / "logs").resolve()


def resolve_telemetry_log_path(log_name: Optional[str] = None) -> Optional[Path]:
    """Resolve a telemetry ``.jsonl`` file strictly inside ``DATA_DIR/logs`` (CWE-22 safe)."""
    logs_dir = _logs_root()
    if log_name:
        clean = log_name.strip()
        if "/" in clean or "\\" in clean or ".." in clean or not clean.endswith(".jsonl"):
            raise ValueError("log_name must be a plain .jsonl filename inside data/logs/.")
        candidate = (logs_dir / clean).resolve()
        if not candidate.is_relative_to(logs_dir):
            raise ValueError("Invalid telemetry log path.")
        if not candidate.is_file():
            raise LookupError(f"Telemetry log '{clean}' not found in data/logs/.")
        return candidate

    for default_name in _DEFAULT_LOG_NAMES:
        candidate = (logs_dir / default_name).resolve()
        if candidate.is_relative_to(logs_dir) and candidate.is_file():
            return candidate
    return None


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = int(round((p / 100.0) * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(idx, len(sorted_values) - 1))]


def _summarize(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min_ms": round(min(ordered), 2),
        "p50_ms": round(_percentile(ordered, 50), 2),
        "p90_ms": round(_percentile(ordered, 90), 2),
        "p95_ms": round(_percentile(ordered, 95), 2),
        "max_ms": round(max(ordered), 2),
        "avg_ms": round(sum(ordered) / len(ordered), 2),
    }


def _load_events(log_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                events.append(obj)
    return events


def _event_ts(event: dict[str, Any]) -> Optional[datetime]:
    raw = event.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _filter_since_minutes(events: list[dict[str, Any]], minutes: int) -> list[dict[str, Any]]:
    if minutes <= 0:
        return events
    timestamps = [ts for ts in (_event_ts(e) for e in events) if ts is not None]
    if not timestamps:
        return events
    cutoff = max(timestamps) - timedelta(minutes=minutes)
    return [e for e in events if (ts := _event_ts(e)) is not None and ts >= cutoff]


def _collect_pipeline(events: list[dict[str, Any]]) -> dict[tuple[str, ...], list[float]]:
    grouped: dict[tuple[str, ...], list[float]] = defaultdict(list)
    for event in events:
        event_type = str(event.get("event_type") or "")
        duration_ms = event.get("duration_ms")
        if event_type.startswith("gm.turn.pipeline") and isinstance(duration_ms, (int, float)):
            grouped[(event_type, str(event.get("phase") or "n/a"))].append(float(duration_ms))
    return grouped


def _collect_req_resp(events: list[dict[str, Any]]) -> dict[tuple[str, ...], list[float]]:
    pending: dict[tuple[Any, ...], datetime] = {}
    grouped: dict[tuple[str, ...], list[float]] = defaultdict(list)
    for event in events:
        event_type = event.get("event_type")
        if event_type not in {"gm.turn.request", "gm.turn.response"}:
            continue
        ts = _event_ts(event)
        if ts is None:
            continue
        key = (
            event.get("adventure_id"),
            event.get("game_id"),
            event.get("operation"),
            event.get("phase"),
            event.get("model"),
            event.get("provider"),
        )
        if event_type == "gm.turn.request":
            pending[key] = ts
            continue
        started = pending.pop(key, None)
        if started is None:
            continue
        group_key = (
            str(event.get("operation") or "n/a"),
            str(event.get("phase") or "n/a"),
            str(event.get("model") or "n/a"),
            str(event.get("provider") or "n/a"),
        )
        grouped[group_key].append((ts - started).total_seconds() * 1000.0)
    return grouped


def _format_groups(
    grouped: dict[tuple[str, ...], list[float]], fields: tuple[str, ...], limit: int
) -> list[dict[str, Any]]:
    rows = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    shown = rows[:limit] if limit > 0 else rows
    return [{**dict(zip(fields, key, strict=True)), **_summarize(values)} for key, values in shown]


def _delta_rows(
    before: dict[tuple[str, ...], list[float]],
    after: dict[tuple[str, ...], list[float]],
    fields: tuple[str, ...],
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(set(before) & set(after)):
        b = _summarize(before[key])
        a = _summarize(after[key])
        delta = round(float(a["p50_ms"]) - float(b["p50_ms"]), 2)
        rows.append(
            {
                **dict(zip(fields, key, strict=True)),
                "p50_before_ms": b["p50_ms"],
                "p50_after_ms": a["p50_ms"],
                "delta_ms": delta,
                "n_before": b["count"],
                "n_after": a["count"],
            }
        )
    rows.sort(key=lambda item: abs(float(item["delta_ms"])), reverse=True)
    return rows[:limit] if limit > 0 else rows


def analyze_llm_telemetry(
    *,
    log_name: Optional[str] = None,
    since_minutes: int = 0,
    split_ts: Optional[str] = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Compute latency percentiles and optional before/after deltas from LLM telemetry logs."""
    log_path = resolve_telemetry_log_path(log_name)
    if log_path is None:
        return {
            "log_file": None,
            "total_events": 0,
            "pipeline_events": [],
            "request_response_latencies": [],
        }

    events = _filter_since_minutes(_load_events(log_path), since_minutes)
    pipeline = _collect_pipeline(events)
    req_resp = _collect_req_resp(events)
    result: dict[str, Any] = {
        "log_file": log_path.name,
        "total_events": len(events),
        "pipeline_events": _format_groups(pipeline, ("event_type", "phase"), limit),
        "request_response_latencies": _format_groups(
            req_resp, ("operation", "phase", "model", "provider"), limit
        ),
    }
    if split_ts:
        try:
            cutoff = datetime.fromisoformat(split_ts)
        except ValueError as exc:
            raise ValueError(f"Invalid ISO timestamp '{split_ts}'.") from exc
        before = [e for e in events if (ts := _event_ts(e)) is not None and ts < cutoff]
        after = [e for e in events if (ts := _event_ts(e)) is not None and ts >= cutoff]
        result["delta"] = {
            "split_ts": split_ts,
            "before_events": len(before),
            "after_events": len(after),
            "pipeline_delta": _delta_rows(
                _collect_pipeline(before), _collect_pipeline(after), ("event_type", "phase"), limit
            ),
            "request_response_delta": _delta_rows(
                _collect_req_resp(before),
                _collect_req_resp(after),
                ("operation", "phase", "model", "provider"),
                limit,
            ),
        }
    return result
