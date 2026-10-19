"""Async filters applied to LiteLLM streaming chunks (thinking tags, voice tag normalization)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

logger = logging.getLogger(__name__)

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"
# Flush the buffered stream start once enough text arrived to normalize a leading voice tag.
_VOICE_PREFIX_MAX_CHARS = 60
_VOICE_PREFIX_TAG_MIN_CHARS = 15
_VOICE_PREFIX_PLAIN_MIN_CHARS = 30


def chunk_delta(chunk: Any) -> str | None:
    """Returns the text delta of a streaming chunk, or None when it carries no text."""
    try:
        delta = chunk.choices[0].delta.content
    except (AttributeError, IndexError, TypeError):
        return None
    return delta if isinstance(delta, str) and delta else None


def set_chunk_delta(chunk: Any, content: str) -> None:
    """Replaces the text delta of a chunk (immutable pydantic deltas are copied)."""
    try:
        chunk.choices[0].delta.content = content
        return
    except Exception:  # frozen delta objects raise various errors
        logger.debug("Delta is immutable; replacing it with a copy.")
    try:
        delta_obj = chunk.choices[0].delta
        copy_fn = getattr(delta_obj, "model_copy", None) or delta_obj.copy
        chunk.choices[0].delta = copy_fn(update={"content": content})
    except Exception as e:  # never break the narration stream
        logger.warning("Failed to modify streaming chunk content: %s", e)


def _partial_tag_suffix_len(buffer: str, tag: str) -> int:
    """Length of the shortest proper prefix of `tag` that `buffer` ends with (0 if none)."""
    return next((i for i in range(1, len(tag)) if buffer.endswith(tag[:i])), 0)


class ThinkTagStripper:
    """Incrementally removes <think>...</think> blocks from streamed text."""

    def __init__(self) -> None:
        self.in_think = False
        self.buffer = ""

    def feed(self, delta: str) -> str:
        self.buffer += delta
        cleaned = ""
        while self.buffer:
            if self.in_think:
                done = self._consume_inside_think()
            else:
                emitted, done = self._consume_outside_think()
                cleaned += emitted
            if done:
                break
        return cleaned

    def _consume_outside_think(self) -> tuple[str, bool]:
        """Returns (visible text, whether to wait for more input)."""
        open_idx = self.buffer.find(_THINK_OPEN)
        if open_idx != -1:
            emitted = self.buffer[:open_idx]
            self.buffer = self.buffer[open_idx + len(_THINK_OPEN) :]
            self.in_think = True
            return emitted, False
        partial = _partial_tag_suffix_len(self.buffer, _THINK_OPEN)
        keep_from = len(self.buffer) - partial
        emitted, self.buffer = self.buffer[:keep_from], self.buffer[keep_from:]
        # Hold a partial opening tag until the next chunk arrives.
        return emitted, True

    def _consume_inside_think(self) -> bool:
        """Drops thinking text; returns whether to wait for more input."""
        close_idx = self.buffer.find(_THINK_CLOSE)
        if close_idx != -1:
            self.buffer = self.buffer[close_idx + len(_THINK_CLOSE) :]
            self.in_think = False
            return False
        partial = _partial_tag_suffix_len(self.buffer, _THINK_CLOSE)
        # Hold a partial closing tag until the next chunk arrives.
        self.buffer = self.buffer[-partial:] if partial else ""
        return True


async def clean_stream_thinking(stream: AsyncIterator[Any]) -> AsyncIterator[Any]:
    """Strips <think>...</think> blocks from stream chunks on-the-fly."""
    stripper = ThinkTagStripper()
    async for chunk in stream:
        delta = chunk_delta(chunk)
        if delta is not None:
            set_chunk_delta(chunk, stripper.feed(delta))
        yield chunk


def _voice_prefix_ready(buffer: str) -> bool:
    return (
        len(buffer) >= _VOICE_PREFIX_MAX_CHARS
        or "\n" in buffer
        or ("]" in buffer and len(buffer) >= _VOICE_PREFIX_TAG_MIN_CHARS)
        or (len(buffer) >= _VOICE_PREFIX_PLAIN_MIN_CHARS and "[" not in buffer)
    )


async def clean_stream_voice_tags(
    stream: AsyncIterator[Any], normalize: Callable[[str], str]
) -> AsyncIterator[Any]:
    """Buffers the start of the stream and normalizes a leading voice tag once."""
    buffer = ""
    prefix_processed = False
    last_chunk = None

    async for chunk in stream:
        delta = chunk_delta(chunk)
        if delta is None or prefix_processed:
            yield chunk
            continue

        buffer += delta
        last_chunk = chunk
        if _voice_prefix_ready(buffer):
            set_chunk_delta(chunk, normalize(buffer))
            prefix_processed = True
            yield chunk

    if not prefix_processed and last_chunk is not None:
        set_chunk_delta(last_chunk, normalize(buffer))
        yield last_chunk
