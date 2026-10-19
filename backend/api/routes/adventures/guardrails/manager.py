"""Facade combining every Pass 1.5 guardrail."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.api.routes.adventures.guardrails.base import GuardrailBase
from backend.api.routes.adventures.guardrails.containers import ContainerGuardMixin
from backend.api.routes.adventures.guardrails.crafting import CraftingGuardMixin
from backend.api.routes.adventures.guardrails.exits import ExitGuardMixin
from backend.api.routes.adventures.guardrails.inspect import InspectGuardMixin
from backend.api.routes.adventures.guardrails.items import ItemIntegrityMixin
from backend.api.routes.adventures.guardrails.locks import LockEngineMixin
from backend.api.routes.adventures.guardrails.progress import ProgressGuardMixin
from backend.api.routes.adventures.guardrails.reading import ReadingMixin
from backend.api.routes.adventures.guardrails.reveals import RevealGuardMixin
from backend.api.routes.adventures.guardrails.world_rules import WorldRulesMixin

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager


class TurnGuardrailsManager(
    InspectGuardMixin,
    ContainerGuardMixin,
    ExitGuardMixin,
    LockEngineMixin,
    ItemIntegrityMixin,
    CraftingGuardMixin,
    RevealGuardMixin,
    ProgressGuardMixin,
    WorldRulesMixin,
    ReadingMixin,
    GuardrailBase,
):
    """Server-side visibility authority and Pass 1.5 rule validations & reversions."""

    def __init__(self, manager: GameTurnManager) -> None:
        self.manager = manager


TurnGuardrailEnforcer = TurnGuardrailsManager
