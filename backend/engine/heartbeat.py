"""
Asynchronous Heartbeat Timer for time-based game logic.

Runs a 1-second tick loop. For each adventure with heartbeat enabled,
it fires every `heartbeat_interval` seconds and applies periodic
status-effect damage to all active (non-paused) game states.

Status-effect damage rules (per tick):
    Poisoned  → -5 HP
    Burning   → -10 HP
    Bleeding  → -3 HP, -2 Stamina
    Regenerating → +5 HP (capped at 200)
    Resting   → +3 Stamina, +3 Mana (capped at 200)
"""
import asyncio
import logging
from typing import Optional
from sqlalchemy import select

from backend.core.database import AsyncSessionLocal
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState

logger = logging.getLogger(__name__)

# Maximum resource cap (matches Avatar defaults)
RESOURCE_CAP = 200

# Maps status-effect names to per-tick resource deltas.
# Positive values restore, negative values drain.
STATUS_EFFECT_TICKS: dict = {
    "Poisoned": {"hp": -5},
    "Burning": {"hp": -10},
    "Bleeding": {"hp": -3, "stamina": -2},
    "Regenerating": {"hp": 5},
    "Resting": {"stamina": 3, "mana": 3},
}


def _apply_status_effect_ticks(avatar: Avatar) -> list[str]:
    """
    Applies per-tick resource changes for all active status effects.

    Returns a list of human-readable log messages describing what happened.
    HP is clamped to [0, RESOURCE_CAP]; stamina and mana to [0, RESOURCE_CAP].
    """
    messages: list[str] = []

    for effect in list(avatar.status_effects or []):
        if effect not in STATUS_EFFECT_TICKS:
            continue

        deltas = STATUS_EFFECT_TICKS[effect]
        parts: list[str] = []

        if "hp" in deltas:
            avatar.hp = max(0, min(RESOURCE_CAP, avatar.hp + deltas["hp"]))
            parts.append(f"HP {deltas['hp']:+d}")

        if "stamina" in deltas:
            avatar.stamina = max(0, min(RESOURCE_CAP, avatar.stamina + deltas["stamina"]))
            parts.append(f"Stamina {deltas['stamina']:+d}")

        if "mana" in deltas:
            avatar.mana = max(0, min(RESOURCE_CAP, avatar.mana + deltas["mana"]))
            parts.append(f"Mana {deltas['mana']:+d}")

        if parts:
            messages.append(f"[{effect}] {', '.join(parts)}")

    return messages


class HeartbeatManager:
    """
    Background daemon that drives time-based game logic.

    Runs a 1-second resolution tick loop. For each adventure that has
    `heartbeat_enabled=True`, it triggers processing every
    `heartbeat_interval` seconds for all non-paused game states.
    """

    def __init__(self) -> None:
        self.running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Starts the background tick loop as an asyncio task."""
        self.running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("HeartbeatManager started.")

    async def stop(self) -> None:
        """Gracefully cancels the tick loop and waits for it to finish."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("HeartbeatManager stopped.")

    async def _loop(self) -> None:
        """
        Core tick loop. Resolves at 1-second granularity and delegates
        to `_process_adventure_tick` for each eligible adventure.
        """
        tick_counter = 0
        while self.running:
            await asyncio.sleep(1)
            tick_counter += 1

            try:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(AdventureTemplate).where(AdventureTemplate.heartbeat_enabled == True)  # noqa: E712
                    )
                    adventures = result.scalars().all()

                    for adv in adventures:
                        if tick_counter % adv.heartbeat_interval == 0:
                            await self._process_adventure_tick(db, adv)

                    await db.commit()

            except Exception:
                logger.exception("Heartbeat loop error — continuing.")

    async def _process_adventure_tick(self, db, adventure: AdventureTemplate) -> None:
        """
        Applies time-based status-effect damage/healing to all active
        game states belonging to the given adventure.

        Skips paused game states so players can safely take a break.
        """
        state_res = await db.execute(
            select(SessionState).where(
                SessionState.template_id == adventure.id,
                SessionState.is_paused == False,  # noqa: E712
            )
        )
        states = state_res.scalars().all()

        for state in states:
            av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
            avatar = av_res.scalars().first()
            if not avatar:
                continue

            messages = _apply_status_effect_ticks(avatar)
            if messages:
                logger.info(
                    "Heartbeat tick [adventure=%s, avatar=%s]: %s",
                    adventure.id,
                    avatar.id,
                    " | ".join(messages),
                )

            # Advance in-game time by the heartbeat interval (in seconds)
            state.in_game_time += adventure.heartbeat_interval


heartbeat_daemon = HeartbeatManager()
