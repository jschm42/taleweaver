---
name: taleweaver-telemetry
description: Analyze LLM telemetry, response latencies, pipeline performance, percentile benchmarks (p50/p90/p95), and token response pairs from TaleWeaver runtime logs.
---

# TaleWeaver LLM Telemetry & Latency Analyzer

Use this skill when you need to inspect LLM performance, monitor response times, investigate timeouts or slow turns, benchmark model providers, or evaluate turn pipeline latencies.

The telemetry analyzer CLI is located at: [scripts/analyze_llm_latency.py](file:///c:/Users/jean/DEV/repositories/taleweaver/scripts/analyze_llm_latency.py).

Telemetry logs are stored in: `data/logs/llm_debug.jsonl` (and `data/logs/llm_telemetry.jsonl`).

---

## Quick Reference Commands

### 1. Overall Telemetry Summary
Analyze all recorded LLM turns and pipeline steps:
```bash
poetry run python scripts/analyze_llm_latency.py
```
*Outputs:*
- **Pipeline Events**: `duration_ms` percentiles (`min`, `p50`, `p90`, `p95`, `max`, `avg`) for `total`, `cycle_total`, `narration`, and other turn pipeline stages.
- **Request/Response Pair Latencies**: Breakdown grouped by `(turn_type, action, model, provider)`.

### 2. Focus on Recent Activity (Last N Minutes)
Inspect only recent game turns (e.g. from the last 15 or 60 minutes) to evaluate immediate test runs:
```bash
# Analyze events from the last 15 minutes
poetry run python scripts/analyze_llm_latency.py --since-minutes 15

# Analyze events from the last hour
poetry run python scripts/analyze_llm_latency.py --since-minutes 60
```

### 3. Before/After Optimization Comparison
Compare latency distributions before and after a specific deployment, prompt change, or timestamp:
```bash
poetry run python scripts/analyze_llm_latency.py --split-ts "2026-05-28T21:00:00+00:00"
```

### 4. Custom Log Files or Extended Section Limits
```bash
# Analyze a specific archived telemetry log
poetry run python scripts/analyze_llm_latency.py --log data/logs/llm_debug.jsonl --limit 50

# Unlimited breakdown rows
poetry run python scripts/analyze_llm_latency.py --limit 0
```

---

## Diagnostic Scenarios & Workflows

### Scenario A: *"Turn generation feels sluggish or hangs"*
1. Run `poetry run python scripts/analyze_llm_latency.py --since-minutes 10`
2. Check `gm.turn.pipeline.total` `p95` and `max` to see if latency is spiking.
3. Check the Request/Response section:
   - If `p50` is normal (e.g. ~2-3s) but `max` is >30s, check if the LLM provider was rate-limiting or experiencing transient delays.
   - If `narration` pass is high, check prompt size and generation token limits in `.env` (`MAX_TOKENS`).

### Scenario B: *"Comparing performance across different models (e.g. DeepSeek vs. Gemini)"*
1. Run `poetry run python scripts/analyze_llm_latency.py --limit 0`
2. Look at the `Request/Response Pair Latencies` table:
   ```text
   chat_turn | mechanics | deepseek-v4-flash | deepseek -> p50=5032.6ms p90=8223.3ms
   chat_turn | mechanics | gemini-2.5-flash   | openai   -> p50=1200.0ms p90=1900.0ms
   ```
3. Evaluate whether switching the default model in `.env` (`PRIMARY_MODEL`) improves turn latency for local play.
