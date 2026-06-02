"""
Scheduler - background tasks like cleanup, stats updates.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from database.db import Database
from utils.matching import MatchingEngine

logger = logging.getLogger(__name__)


class Scheduler:
    """Background task scheduler."""

    def __init__(self, db: Database, matching_engine: MatchingEngine):
        self.db = db
        self.matching_engine = matching_engine
        self._running = True

    async def run(self) -> None:
        """Run all scheduled tasks."""
        logger.info("Scheduler started.")
        tasks = [
            self._cleanup_stale_queue(),
            self._update_daily_stats(),
        ]
        await asyncio.gather(*tasks)

    async def _cleanup_stale_queue(self) -> None:
        """Remove users from queue if they've been waiting too long (10 min)."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                now = datetime.utcnow()
                stale_threshold = now - timedelta(minutes=10)

                stale_users = [
                    uid for uid, user in list(self.matching_engine._waiting.items())
                    if user.joined_at < stale_threshold
                ]
                for uid in stale_users:
                    await self.matching_engine.remove_from_queue(uid)
                    logger.debug(f"Removed stale user {uid} from queue.")

            except Exception as e:
                logger.error(f"Scheduler error in cleanup: {e}")

    async def _update_daily_stats(self) -> None:
        """Update daily stats every 5 minutes."""
        while self._running:
            try:
                await asyncio.sleep(300)
                stats = await self.db.get_full_stats()
                today = datetime.utcnow().date().isoformat()
                await self.db._conn.execute(
                    """INSERT INTO daily_stats (date, active_users, chats_created)
                       VALUES (?, ?, ?)
                       ON CONFLICT(date) DO UPDATE SET
                           active_users = ?,
                           chats_created = ?""",
                    (today, stats["active_today"], stats["chats_today"],
                     stats["active_today"], stats["chats_today"])
                )
                await self.db._conn.commit()
            except Exception as e:
                logger.error(f"Scheduler error in stats: {e}")

    def stop(self) -> None:
        self._running = False
