"""Request models of the Region Builder (docs/specs/region_builder.md, section 8).

A request with only ``brief`` (the old Regions page) stays valid: every context option and
generation option then takes its default (all context on).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Detail = Literal["off", "compact", "full"]
Count = Optional[int]


class RegionContextRequest(BaseModel):
    """Which parts of the existing world go into the prompt, and how detailed."""

    outline: Detail = "full"
    regions: Detail = "full"
    plot: Detail = "full"
    rules: Detail = "full"
    sequences: Detail = "full"
    walkthroughs: bool = True
    quests: Detail = "full"
    scenes: Detail = "compact"
    npcs: Detail = "compact"
    items: Detail = "compact"


def _count() -> Any:
    return Field(default=None, ge=0, le=60)


class RegionOptionsRequest(BaseModel):
    """Size, feature and strictness options; ``None`` min and max = the AI decides."""

    generation_strictness: Literal["creative", "strict"] = "creative"
    min_scenes: Count = _count()
    max_scenes: Count = _count()
    min_items: Count = _count()
    max_items: Count = _count()
    min_quests: Count = _count()
    max_quests: Count = _count()
    min_sequences: Count = _count()
    max_sequences: Count = _count()
    min_containers: Count = _count()
    max_containers: Count = _count()
    min_text_logs: Count = _count()
    max_text_logs: Count = _count()
    min_awards: Count = _count()
    max_awards: Count = _count()
    quest_generation_enabled: bool = True
    container_generation_enabled: bool = True
    scripts_generation_enabled: bool = True
    text_log_generation_enabled: bool = True
    award_generation_enabled: bool = True


class SectionGenerateRequest(BaseModel):
    brief: Optional[str] = Field(default=None, max_length=20000)
    # Which form the builder showed; stored with the settings so it reopens the same way.
    mode: Literal["simple", "advanced"] = "simple"
    context: RegionContextRequest = Field(default_factory=RegionContextRequest)
    options: RegionOptionsRequest = Field(default_factory=RegionOptionsRequest)
    # Unsaved gateway picks per linked region id; only the preview uses them (the builder
    # saves them with the region list before it starts a build).
    gateways: Optional[dict[str, list[str]]] = Field(default=None, max_length=12)

    def settings(self) -> dict[str, Any]:
        return {"context": self.context.model_dump(), "options": self.options.model_dump()}

    def stored_settings(self) -> dict[str, Any]:
        """What the region keeps as ``generation_settings`` for the next build."""
        return {"mode": self.mode, **self.settings()}
