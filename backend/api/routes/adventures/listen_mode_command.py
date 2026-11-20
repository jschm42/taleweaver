"""``/listen_mode <code>``: the play view's listening mode switched on or off.

Listening mode itself runs in the client (``frontend/src/composables/useListeningMode.ts``: it
sends ``/listen`` after each narration was read aloud). The client reports every switch with this
command so the story keeps a system message about it; no LLM call, no clock tick.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

LISTEN_MODE_COMMAND = "/listen_mode"
LISTEN_MODE_MESSAGES = {
    "on": "Listening mode on: you keep quiet and listen to the characters around you.",
    "off": "Listening mode off.",
    "nobody": "Listening mode off: nobody here is talking.",
    "interrupted": "Listening mode off: the situation changed.",
    "limit": "Listening mode off after a long conversation. Switch it on again to keep listening.",
}


def is_listen_mode_command(user_msg: str) -> bool:
    parts = user_msg.strip().split()
    return bool(parts) and parts[0].lower() == LISTEN_MODE_COMMAND


async def handle_listen_mode_command(manager: Any, user_msg: str) -> AsyncGenerator[str, None]:
    """Saves and streams the system message of a listening-mode switch (unknown code: nothing)."""
    parts = user_msg.strip().split()
    code = parts[1].lower() if len(parts) > 1 else ""
    content = LISTEN_MODE_MESSAGES.get(code)
    if not content:
        return
    await manager._save_chat_message("system", content)
    await manager.db.commit()
    payload = {"role": "system", "content": content}
    yield f"event: system\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
