"""Shared state for one manifest application run."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

StatusCallback = Callable[[str], Awaitable[None]]


def generator_module() -> Any:
    """Returns world_generator lazily (it imports this package, so a top-level import would cycle).

    Helpers are looked up on the module at call time so tests can monkeypatch them.
    """
    from backend.engine import world_generator

    return world_generator


def new_image_counters() -> dict[str, int]:
    return {"attempts": 0, "successes": 0, "moderation": 0}


@dataclass
class ApplyContext:
    """Everything the persistence steps need while a manifest is applied."""

    db: AsyncSession
    template_id: str
    manifest: dict[str, Any]
    user: Optional[User]
    adventure: Optional[AdventureTemplate]
    gen_npc: bool = False
    gen_items: bool = False
    gen_scenes: bool = False
    gen_protagonist_image: bool = False
    existing_images: dict[str, str] = field(default_factory=dict)
    source_assets: Optional[dict[str, Any]] = None
    style_instruction: str = ""
    status_callback: Optional[StatusCallback] = None
    image_counters: dict[str, int] = field(default_factory=new_image_counters)
    seen_scene_ids: set[str] = field(default_factory=set)
    seen_entity_ids: set[str] = field(default_factory=set)

    @property
    def library_dir(self) -> str:
        return os.path.join(settings.DATA_DIR, "adventures", "library", self.template_id)

    @property
    def any_image_generation(self) -> bool:
        return bool(self.gen_scenes or self.gen_npc or self.gen_items or self.gen_protagonist_image)

    async def commit_and_refresh(self, refresh_user: bool = True) -> None:
        """Commits and reloads the adventure (and user) so later steps never see expired rows."""
        await self.db.commit()
        self.adventure = await self.db.get(AdventureTemplate, self.template_id)
        if refresh_user and self.user:
            self.user = await self.db.get(User, self.user.id)
