"""NPCs that may speak the short quote shown while a dynamic scene is generated.

Only HUMANOID and BEING NPCs speak. Each candidate carries its cast TTS voice (the same
casting as ``npc_metadata``), so the quote sounds like the NPC does in the narration, also
when no voice is stored on the row.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.audio.voice_casting import cast_adventure_voices
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)


async def _cast_npc_voices(
    db: AsyncSession, state: SessionState, npc_rows: list[WorldEntity]
) -> dict[str, Optional[str]]:
    """Cast voices for the session NPCs; a casting failure only loses the voice, not the quote."""
    try:
        voices, _protagonist = await cast_adventure_voices(
            db, npc_rows, state.template_id, state.session_id
        )
    except Exception:
        logger.warning("Voice casting for the interlude quote failed", exc_info=True)
        return {}
    return voices


async def load_interlude_candidates(db: AsyncSession, state: SessionState) -> list[dict[str, Any]]:
    """Preload humanoid/being NPC candidates on ``db`` before starting concurrent tasks.

    ``voice`` is the NPC's cast TTS voice (the same casting as ``npc_metadata``), so the quote
    is spoken in the voice the NPC has in the narration, also when none is stored on the row.
    """
    npc_rows = (
        (
            await db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == state.session_id,
                    WorldEntity.entity_type == "NPC",
                )
            )
        )
        .scalars()
        .all()
    )
    voices = await _cast_npc_voices(db, state, npc_rows)
    return [
        {
            "id": n.id,
            "name": n.name,
            "npc_type": str(n.npc_type or "HUMANOID").strip().upper(),
            "goal": n.goal or "",
            "role": str(n.npc_type or "HUMANOID").strip().upper(),
            "character": n.character or "",
            "description": n.description or "",
            "image_url": n.image_url,
            "voice": voices.get(n.id) or n.voice,
            "is_defeated": bool((state.entity_states or {}).get(n.id, {}).get("is_defeated")),
        }
        for n in npc_rows
        if str(n.npc_type or "HUMANOID").strip().upper() in {"HUMANOID", "BEING"}
    ]
