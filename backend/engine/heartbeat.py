import asyncio
import logging
from sqlalchemy import select

from backend.core.database import AsyncSessionLocal
from backend.models.adventure import Adventure
from backend.models.game_state import GameState

logger = logging.getLogger(__name__)

class HeartbeatManager:
    def __init__(self):
        self.running = False
        self._task = None

    def start(self):
        self.running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        # Time resolves in 1-second ticks
        tick_counter = 0
        while self.running:
            await asyncio.sleep(1)
            tick_counter += 1
            
            try:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(Adventure).where(Adventure.heartbeat_enabled == True)
                    )
                    adventures = result.scalars().all()
                    
                    for adv in adventures:
                        if tick_counter % adv.heartbeat_interval == 0:
                            logger.info(f"Heartbeat tick processing for adventure {adv.id}")
                            # E.g. find all game states for this adv, apply poison damage
                            # state_res = await db.execute(select(GameState).where(GameState.adventure_id == adv.id))
                            # for state in state_res.scalars().all():
                            #     apply_status_effects(...)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

heartbeat_daemon = HeartbeatManager()
