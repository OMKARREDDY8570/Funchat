"""
Profile handler - user profile, XP, coins, reputation display.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database.db import Database
from utils.keyboards import back_to_menu_keyboard
from utils.helpers import get_rank_badge, level_progress_bar, coins_display, streak_badge, format_number

logger = logging.getLogger(__name__)


class ProfileHandler:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    async def handle_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        text = await self._build_profile(user_id)
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    async def handle_profile_cb(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        text = await self._build_profile(user_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    async def _build_profile(self, user_id: int) -> str:
        user = await self.db.get_user(user_id)
        if not user:
            return "❌ Profile not found. Use /start first."

        xp_data = await self.db.get_xp(user_id)
        coins = await self.db.get_coins(user_id)
        streak = await self.db.get_streak(user_id)
        rep = await self.db.get_reputation(user_id)
        rank = await self.db.get_user_rank(user_id)
        friends = await self.db.get_friends(user_id)

        level = xp_data["level"]
        total_xp = xp_data["total_xp"]
        badge = get_rank_badge(level)
        progress = level_progress_bar(total_xp, level)
        streak_text = streak_badge(streak["current_streak"])

        rep_bar = "🟢" * min(rep["percentage"] // 10, 10) or "⚪"

        return (
            f"⭐ <b>Your Profile</b>\n\n"
            f"👤 <b>{user['first_name']}</b>\n"
            f"🏅 {badge}\n"
            f"🌍 Global Rank: #{rank}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📈 <b>Level {level}</b>\n"
            f"{progress}\n"
            f"🔷 Total XP: {format_number(total_xp)}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Coins:</b> {format_number(coins)}\n"
            f"{streak_text}\n"
            f"👥 Friends: {len(friends)}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 <b>Reputation: {rep['percentage']}%</b>\n"
            f"{rep_bar}\n"
            f"⭐ {rep['positive']} good · 👎 {rep['negative']} bad\n\n"
            f"🎫 <b>Referral Code:</b> <code>{user['referral_code']}</code>"
        )
