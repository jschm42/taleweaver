import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def parse_iso_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = int(round((p / 100.0) * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(idx, len(sorted_values) - 1))]


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "count": float(len(ordered)),
        "min_ms": min(ordered),
        "p50_ms": percentile(ordered, 50),
        "p90_ms": percentile(ordered, 90),
        "p95_ms": percentile(ordered, 95),
        "max_ms": max(ordered),
        "avg_ms": sum(ordered) / len(ordered),
    }


def load_events(log_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(obj)
    return events


def event_timestamp(event: dict[str, Any]) -> datetime | None:
    value = event.get("timestamp")
    if not isinstance(value, str):
        return None
    try:
        return parse_iso_timestamp(value)
    except Exception:
        return None


def filter_events_since_minutes(events: list[dict[str, Any]], minutes: int) -> list[dict[str, Any]]:
    if minutes <= 0:
        return events

    timestamps = [ts for ts in (event_timestamp(e) for e in events) if ts is not None]
    if not timestamps:
        return events

    latest = max(timestamps)
    cutoff = latest - timedelta(minutes=minutes)
    filtered: list[dict[str, Any]] = []
    for event in events:
        ts = event_timestamp(event)
        if ts is None:
            continue
        if ts >= cutoff:
            filtered.append(event)
    return filtered


def split_events_by_timestamp(
    events: list[dict[str, Any]], split_ts: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    before: list[dict[str, Any]] = []
    after: list[dict[str, Any]] = []
    for event in events:
        ts = event_timestamp(event)
        if ts is None:
            continue
        if ts < split_ts:
            before.append(event)
        else:
            after.append(event)
    return before, after


def derive_request_response_latencies(events: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], list[float]]:
    pending: dict[tuple[Any, ...], datetime] = {}
    grouped: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)

    for event in events:
        event_type = event.get("event_type")
        if event_type not in {"gm.turn.request", "gm.turn.response"}:
            continue

        try:
            ts = parse_iso_timestamp(str(event.get("timestamp")))
        except Exception:
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

        duration_ms = (ts - started).total_seconds() * 1000.0
        group_key = (
            str(event.get("operation") or "n/a"),
            str(event.get("phase") or "n/a"),
            str(event.get("model") or "n/a"),
            str(event.get("provider") or "n/a"),
        )
        grouped[group_key].append(duration_ms)

    return grouped


def collect_pipeline_events(events: list[dict[str, Any]]) -> dict[tuple[str, str], list[float]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)

    for event in events:
        event_type = str(event.get("event_type") or "")
        if not event_type.startswith("gm.turn.pipeline"):
            continue

        duration_ms = event.get("duration_ms")
        if not isinstance(duration_ms, (int, float)):
            continue

        phase = str(event.get("phase") or "n/a")
        grouped[(event_type, phase)].append(float(duration_ms))

    return grouped


def print_group_summary(title: str, grouped: dict[tuple[str, ...], list[float]], limit: int) -> None:
    print("=" * 88)
    print(title)
    print("=" * 88)

    if not grouped:
        print("No matching events found.")
        return

    rows = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    shown = rows[:limit] if limit > 0 else rows

    for key, values in shown:
        stats = summarize(values)
        key_str = " | ".join(key)
        print(
            f"{key_str} -> n={int(stats['count'])} "
            f"min={stats['min_ms']:.1f}ms p50={stats['p50_ms']:.1f}ms "
            f"p90={stats['p90_ms']:.1f}ms p95={stats['p95_ms']:.1f}ms "
            f"max={stats['max_ms']:.1f}ms avg={stats['avg_ms']:.1f}ms"
        )


def print_delta_summary(
    title: str,
    before: dict[tuple[str, ...], list[float]],
    after: dict[tuple[str, ...], list[float]],
    limit: int,
) -> None:
    print("=" * 88)
    print(title)
    print("=" * 88)

    shared_keys = sorted(set(before.keys()) & set(after.keys()))
    if not shared_keys:
        print("No overlapping keys found between BEFORE and AFTER windows.")
        return

    rows: list[tuple[float, str]] = []
    for key in shared_keys:
        b = summarize(before[key])
        a = summarize(after[key])
        delta = a["p50_ms"] - b["p50_ms"]
        key_str = " | ".join(key)
        sign = "+" if delta >= 0 else ""
        row = (
            abs(delta),
            f"{key_str} -> "
            f"p50_before={b['p50_ms']:.1f}ms p50_after={a['p50_ms']:.1f}ms "
            f"delta={sign}{delta:.1f}ms "
            f"n_before={int(b['count'])} n_after={int(a['count'])}",
        )
        rows.append(row)

    rows.sort(key=lambda item: item[0], reverse=True)
    shown = rows[:limit] if limit > 0 else rows
    for _, text in shown:
        print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze TaleWeaver LLM latency telemetry.")
    parser.add_argument(
        "--log",
        default="backend/logs/llm_debug.jsonl",
        help="Path to telemetry log file (default: backend/logs/llm_debug.jsonl)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum rows per section (0 = no limit)",
    )
    parser.add_argument(
        "--since-minutes",
        type=int,
        default=0,
        help="Only analyze events from the last N minutes based on latest log timestamp (0 = all)",
    )
    parser.add_argument(
        "--split-ts",
        default="",
        help="ISO timestamp to split BEFORE/AFTER windows (example: 2026-05-05T21:00:00+00:00)",
    )
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        raise SystemExit(f"Log file not found: {log_path}")

    events = load_events(log_path)
    print(f"Loaded events: {len(events)} from {log_path}")

    if args.since_minutes > 0:
        events = filter_events_since_minutes(events, args.since_minutes)
        print(f"Filtered to last {args.since_minutes} minutes: {len(events)} events")

    pipeline = collect_pipeline_events(events)
    req_resp = derive_request_response_latencies(events)

    print_group_summary("Pipeline Events (duration_ms from gm.turn.pipeline.*)", pipeline, args.limit)
    print()
    print_group_summary("Request/Response Pair Latencies (gm.turn.request -> gm.turn.response)", req_resp, args.limit)

    if args.split_ts:
        split_ts = parse_iso_timestamp(args.split_ts)
        before_events, after_events = split_events_by_timestamp(events, split_ts)

        before_pipeline = collect_pipeline_events(before_events)
        after_pipeline = collect_pipeline_events(after_events)
        before_req_resp = derive_request_response_latencies(before_events)
        after_req_resp = derive_request_response_latencies(after_events)

        print()
        print(f"Split timestamp: {args.split_ts}")
        print(f"BEFORE events: {len(before_events)} | AFTER events: {len(after_events)}")
        print()
        print_delta_summary(
            "Delta (Pipeline Events): AFTER p50 - BEFORE p50",
            before_pipeline,
            after_pipeline,
            args.limit,
        )
        print()
        print_delta_summary(
            "Delta (Request/Response Pair Latencies): AFTER p50 - BEFORE p50",
            before_req_resp,
            after_req_resp,
            args.limit,
        )


if __name__ == "__main__":
    main()
