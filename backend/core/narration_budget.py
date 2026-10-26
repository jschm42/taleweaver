"""Measures how much of a narrated turn is narrator prose versus character dialogue.

The narration styles only *ask* the model for a certain length. This module checks the finished
turn against a per-style budget and logs the result, so prompt changes can be judged with numbers
(see the ``gm.turn.narration_budget`` telemetry event) instead of by reading transcripts.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Final, Optional

from backend.core.llm_logger import log_structured_event
from backend.core.narration_styles import DEFAULT_NARRATION_STYLE, is_narration_style

# Speaker: "Line" / **Speaker:** [tag] "Line" — mirrors the dialogue format of the narration prompt.
_DIALOGUE_LINE: Final = re.compile(
    r"^\s*(?:\[[^\]\n]+\]\s*)?\**[\w .'’\-()]{2,60}?\**\s*:\**\s*(?:\[[^\]\n]+\]\s*)?[\"“„»]"
)
_NARRATOR_LABEL: Final = re.compile(r"^\s*\**(?:narrator|narration|game master|gm)\**\s*:", re.I)
_TAG: Final = re.compile(r"\[[^\]\n]*\]|<[^>\n]*>")
_SENTENCE_END: Final = re.compile(r"[.!?…]+[\"”»]?(?=\s|$)")


@dataclass(frozen=True)
class NarrationBudget:
    """Upper limits for one turn; ``None`` means the style does not limit that value."""

    max_narration_ratio: float
    max_beat_sentences: Optional[int] = None
    max_beats: Optional[int] = None


_BUDGETS: Final[dict[str, NarrationBudget]] = {
    "terse": NarrationBudget(max_narration_ratio=0.6, max_beats=3),
    # The script style allows one extra two-sentence opening beat for new locations.
    "dialogue": NarrationBudget(max_narration_ratio=0.34, max_beat_sentences=2, max_beats=4),
    "balanced": NarrationBudget(max_narration_ratio=0.7),
    "rich": NarrationBudget(max_narration_ratio=0.8),
    "epic": NarrationBudget(max_narration_ratio=0.9),
}


@dataclass(frozen=True)
class NarrationMetrics:
    narration_words: int
    dialogue_words: int
    narration_beats: int
    dialogue_lines: int
    longest_beat_sentences: int
    leaked_narrator_labels: int

    @property
    def narration_ratio(self) -> float:
        total = self.narration_words + self.dialogue_words
        return round(self.narration_words / total, 3) if total else 0.0


def _word_count(text: str) -> int:
    return len(_TAG.sub(" ", text).split())


def _sentence_count(text: str) -> int:
    return max(1, len(_SENTENCE_END.findall(_TAG.sub(" ", text))))


def _classify(line: str) -> tuple[str, str]:
    """Returns (kind, text) with kind ``dialogue``, ``narration``, ``leak`` (labelled prose) or ``empty``."""
    if not _TAG.sub("", line).strip():
        return "empty", ""
    if _NARRATOR_LABEL.match(line):
        return "leak", _NARRATOR_LABEL.sub("", line, count=1).strip()
    if _DIALOGUE_LINE.match(line):
        return "dialogue", line
    return "narration", line


def measure_narration(text: str) -> NarrationMetrics:
    """Splits the turn into narrator beats (prose lines) and dialogue lines and counts both."""
    narration_words = dialogue_words = beats = lines = longest = leaks = 0
    for raw_line in (text or "").splitlines():
        kind, line = _classify(raw_line.strip())
        leaks += kind == "leak"
        if kind == "dialogue":
            lines += 1
            dialogue_words += _word_count(line)
        elif _TAG.sub("", line).strip():
            beats += 1
            narration_words += _word_count(line)
            longest = max(longest, _sentence_count(line))
    return NarrationMetrics(narration_words, dialogue_words, beats, lines, longest, leaks)


def budget_violations(metrics: NarrationMetrics, style: object) -> list[str]:
    """Names of the budget limits this turn exceeded (empty when it fits)."""
    budget = _BUDGETS[str(style) if is_narration_style(style) else DEFAULT_NARRATION_STYLE]
    checks = {
        # Turns without any dialogue are fine (nobody may be present).
        "narration_ratio": metrics.dialogue_lines > 0
        and metrics.narration_ratio > budget.max_narration_ratio,
        "beat_length": budget.max_beat_sentences is not None
        and metrics.longest_beat_sentences > budget.max_beat_sentences,
        "beat_count": budget.max_beats is not None and metrics.narration_beats > budget.max_beats,
        "narrator_label": metrics.leaked_narrator_labels > 0,
    }
    return [name for name, exceeded in checks.items() if exceeded]


def log_narration_budget(text: str, style: object, **fields: Any) -> list[str]:
    """Logs the turn's narration metrics and budget result; returns the violated limits."""
    metrics = measure_narration(text)
    violations = budget_violations(metrics, style)
    log_structured_event(
        "gm.turn.narration_budget",
        narration_style=style if is_narration_style(style) else DEFAULT_NARRATION_STYLE,
        narration_ratio=metrics.narration_ratio,
        within_budget=not violations,
        violations=violations,
        **asdict(metrics),
        **fields,
    )
    return violations
