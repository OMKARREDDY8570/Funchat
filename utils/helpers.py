"""
Utility helpers: decorators, formatters, rate limiting helpers.
"""

import functools
import logging
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

from database.db import Database

logger = logging.getLogger(__name__)

MEDALS = ["🥇", "🥈", "🥉"]


def require_not_banned(func: Callable) -> Callable:
    """Decorator to block banned users."""
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        db: Database = context.bot_data.get("db")
        if db and await db.is_banned(user_id):
            msg = "🚫 You have been banned from FunChatBot.\n\nIf you think this is an error, contact support."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            else:
                await update.message.reply_text(msg)
            return
        return await func(self, update, context, *args, **kwargs)
    return wrapper


def format_number(n: int) -> str:
    """Format large numbers with K/M suffix."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def level_progress_bar(current_xp: int, level: int) -> str:
    """Generate ASCII progress bar for XP."""
    level_start_xp = sum(i * 100 for i in range(1, level))
    level_end_xp = level_start_xp + level * 100
    progress_xp = current_xp - level_start_xp
    needed_xp = level * 100
    pct = min(progress_xp / needed_xp, 1.0)
    filled = int(pct * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {progress_xp}/{needed_xp} XP"


def get_rank_badge(level: int) -> str:
    """Get rank badge emoji based on level."""
    if level >= 50:
        return "👑 Legend"
    if level >= 30:
        return "💎 Diamond"
    if level >= 20:
        return "🏆 Platinum"
    if level >= 10:
        return "🥇 Gold"
    if level >= 5:
        return "🥈 Silver"
    return "🥉 Bronze"


def streak_badge(streak: int) -> str:
    """Get streak display with fire emoji."""
    if streak == 0:
        return "❄️ No streak"
    fires = "🔥" * min(streak // 7 + 1, 5)
    return f"{fires} {streak} Day Streak"


def coins_display(coins: int) -> str:
    return f"🪙 {format_number(coins)} coins"
