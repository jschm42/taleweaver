"""Speed rating of the admin model tests: fast / ok / slow per pass.

The limits are seconds per request, measured on the short test prompts. Real turns carry a
larger state block, so they take somewhat longer; the rating is meant for comparing models.
Pass 2 streams in play, so the player sees text before the full passage is done.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

# (fast up to, ok up to) seconds per request.
_LIMITS: dict[str, tuple[float, float]] = {
    "small": (2.0, 5.0),
    "play_agent": (3.0, 7.0),
    "complex": (4.0, 9.0),
    "compression": (5.0, 12.0),
    "generator": (8.0, 20.0),
}
_NOTES = {
    "small": "Pass 1 runs before every narration, so it adds directly to every turn.",
    "complex": "Full passage; in play the text streams, so the first words appear earlier.",
    "play_agent": "Adds to every Play-Agent step.",
    "compression": "Runs in the background now and then.",
    "generator": "Runs rarely; speed matters little here.",
}


@dataclass
class SpeedRating:
    rating: str
    seconds: float
    fast_limit: float
    ok_limit: float
    note: str

    def label(self) -> str:
        return f"Speed: {self.rating} ({self.seconds:.1f} s per request)"


def rate_speed(pass_key: str, seconds: float) -> SpeedRating:
    """Rates the slowest request of a test against the limits of its pass."""
    fast_limit, ok_limit = _LIMITS.get(pass_key, _LIMITS["small"])
    rating = "slow"
    if seconds <= ok_limit:
        rating = "ok"
    if seconds <= fast_limit:
        rating = "fast"
    note = _NOTES.get(pass_key, _NOTES["small"])
    return SpeedRating(rating, round(seconds, 2), fast_limit, ok_limit, note)


def speed_payload(pass_key: str, seconds: float) -> dict:
    """The `speed` block of a test response."""
    rated = rate_speed(pass_key, seconds)
    return {**asdict(rated), "label": rated.label()}
