"""Chooses which chat messages the history compression summarizes.

Compressing as soon as a single turn leaves the memory window costs one extra LLM call
per player message. Instead, compression waits until more than ``max_turns`` turns are
uncompressed and then summarizes all but the newest ``max_turns - max_turns // 2`` turns
at once. The prompt still shows the last ``max_turns`` turns, so the summary and the
window overlap and no turn is lost in between.

Dialog choices (``[Choice] ...`` user messages) belong to the turn they answer and do not
start a turn of their own, here and in the prompt's memory window.
"""

from collections.abc import Sequence
from typing import Any, Optional

CHOICE_MESSAGE_PREFIX = "[Choice]"


def is_turn_start(message: Any) -> bool:
    """A turn starts with a player message; dialog choices do not count."""
    if message.role != "user":
        return False
    return not str(message.content or "").startswith(CHOICE_MESSAGE_PREFIX)


def _first_uncompressed_index(messages: Sequence[Any], last_compressed_id: Optional[str]) -> int:
    if not last_compressed_id:
        return 0
    for index, message in enumerate(messages):
        if message.id == last_compressed_id:
            return index + 1
    return 0


def messages_to_compress(
    messages: Sequence[Any], last_compressed_id: Optional[str], max_turns: int
) -> list[Any]:
    """Returns the messages to fold into the summary now (empty when it is not due yet)."""
    start = _first_uncompressed_index(messages, last_compressed_id)
    turn_starts = [i for i, m in enumerate(messages) if i >= start and is_turn_start(m)]
    if len(turn_starts) <= max_turns:
        return []
    keep_turns = max(1, max_turns - max_turns // 2)
    cutoff = turn_starts[len(turn_starts) - keep_turns]
    return list(messages[start:cutoff])
