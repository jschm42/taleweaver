"""To be continued: finishing the last chapter does not end a campaign that is still growing.

A campaign whose template still has planned regions, or built regions this session has not
taken in yet (``session_expansion.pending_sections``), is not over when the session finished
every chapter it knows. Instead of the victory ending the player gets one notice and stays in
the world; ``tw.game.win()`` and a win guard still end the adventure as before.
Spec: docs/specs/world_sections.md (9.7).
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.session_expansion import pending_sections
from backend.engine.world.sections import is_stub, normalize_sections
from backend.models.adventure_template import AdventureTemplate

TO_BE_CONTINUED_KEY = "__to_be_continued__"
TO_BE_CONTINUED_NOTE = (
    "To be continued: you finished every chapter written so far. The next regions of this "
    "adventure are still being built; you can keep exploring the world."
)


async def campaign_continues(db: AsyncSession, state: Any) -> bool:
    """True while the adventure has regions this session cannot play yet."""
    template_id = getattr(state, "template_id", None)
    template = await db.get(AdventureTemplate, template_id) if template_id else None
    if template is None:
        return False
    if any(is_stub(s) for s in normalize_sections(template.world_sections)):
        return True
    return bool(await pending_sections(db, state))


def take_to_be_continued_note(state: Any) -> Optional[str]:
    """The notice the first time only (remembered in ``entity_states``, so in checkpoints)."""
    states = dict(state.entity_states or {})
    if states.get(TO_BE_CONTINUED_KEY):
        return None
    states[TO_BE_CONTINUED_KEY] = True
    state.entity_states = states
    flag_modified(state, "entity_states")
    return TO_BE_CONTINUED_NOTE
