"""User-facing reasons for failed image generations.

Provider errors (safety filters, rejected keywords, quota, bad model names) are useful to the
author, so they are passed on instead of a generic message. Secrets that providers sometimes
echo back (API keys, bearer tokens, signed URL parameters) are redacted, and the text is clipped.
"""

from __future__ import annotations

import re

MAX_REASON_LENGTH = 400
_REDACTED = "[redacted]"

_SECRET_PATTERNS = (
    re.compile(r"\b(sk|pk|rk|bfl|hf|or)[-_][A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)\b(api[_-]?key|token|key|signature|sig)=[^&\s\"']+"),
    re.compile(r"\b[A-Za-z0-9_\-]{40,}\b"),
)


def _redact(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


def image_error_reason(exc: BaseException, fallback: str = "Visual generation failed.") -> str:
    """Returns the provider's failure reason, redacted and clipped, or the fallback."""
    reason = _redact(" ".join(str(exc).split()))
    if not reason:
        return fallback
    if len(reason) > MAX_REASON_LENGTH:
        reason = reason[: MAX_REASON_LENGTH - 3].rstrip() + "..."
    return f"{fallback.rstrip('.')}: {reason}"
