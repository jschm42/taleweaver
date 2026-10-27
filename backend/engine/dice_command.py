"""``/roll [sides]`` player command: rolls a single die without involving the narrator.

The result is stored and streamed as a system message in a fixed format that the frontend
recognizes and renders as a die (see ``frontend/src/components/game/immersive/diceRolls.ts``).
"""

from __future__ import annotations

import json
import secrets
from collections.abc import AsyncGenerator
from typing import Any

ROLL_COMMAND = "/roll"
DEFAULT_SIDES = 6
MIN_SIDES = 2
MAX_SIDES = 30


class RollCommandError(ValueError):
    """The ``/roll`` argument is not a whole number between MIN_SIDES and MAX_SIDES."""


def is_roll_command(user_msg: str) -> bool:
    parts = user_msg.strip().split(None, 1)
    return bool(parts) and parts[0].lower() == ROLL_COMMAND


def _validate_roll_sides(user_msg: str) -> tuple[int | None, str | None]:
    """Validates ``/roll [sides]`` and returns ``(sides, error_message)``."""
    parts = user_msg.strip().split(None, 1)
    if len(parts) < 2:
        return DEFAULT_SIDES, None
    raw = parts[1].strip().lower().removeprefix("d")
    if not raw.isdigit():
        return None, f"Usage: /roll {MIN_SIDES}-{MAX_SIDES} (sides), e.g. /roll 20."
    sides = int(raw)
    if not MIN_SIDES <= sides <= MAX_SIDES:
        return None, f"A die needs between {MIN_SIDES} and {MAX_SIDES} sides."
    return sides, None


def parse_roll_sides(user_msg: str) -> int:
    """Number of die sides requested by ``/roll [sides]`` (``d`` prefix allowed, e.g. ``d20``)."""
    sides, error = _validate_roll_sides(user_msg)
    if error is not None or sides is None:
        raise RollCommandError(error or "Invalid roll command.")
    return sides


def roll_die(sides: int) -> int:
    return secrets.randbelow(sides) + 1


def roll_from_args(args: str) -> str:
    """Parses the ``/roll`` arguments, rolls and returns the system message text."""
    sides = parse_roll_sides(f"{ROLL_COMMAND} {args}".strip())
    return format_roll_message(sides, roll_die(sides))


def format_roll_message(sides: int, value: int) -> str:
    """Fixed wording parsed by the frontend dice display: ``ROLL d<sides>: **<value>**``."""
    return f"🎲 **ROLL d{sides}**: **{value}**"


async def handle_roll_command(manager: Any, user_msg: str) -> AsyncGenerator[str, None]:
    """Rolls the die, persists the result as a system message and streams it."""
    sides, error = _validate_roll_sides(user_msg)
    if error is not None or sides is None:
        payload = {"role": "system", "content": error or "Invalid roll command."}
        yield f"event: system\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        return

    content = format_roll_message(sides, roll_die(sides))
    await manager._save_chat_message("system", content)
    await manager.db.commit()
    payload = {"role": "system", "content": content}
    yield f"event: system\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
