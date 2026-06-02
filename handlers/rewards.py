"""
Rewards handler - daily login, streak claims, coin rewards.
"""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database.db import Database
from utils.keyboards import back_to_menu_keyboard
from utils.helpers import streak_badge, coins_display

logger = logging.getLogger(__name__)


class RewardHandler:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    async def handle_daily_reward(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        success, new_streak, coins_earned = await self.db.claim_daily_streak(user_id)
        streak_data = await self.db.get_streak(user_id)
        total_coins = await self.db.get_coins(user_id)

        if not success:
            # Already claimed today
            last = streak_data.get("last_claim_date", "today")
            text = (
                f"🎁 <b>Daily Reward</b>\n\n"
                f"✅ You already claimed your reward today!\n\n"
                f"{streak_badge(streak_data['current_streak'])}\n\n"
                f"Come back tomorrow for your next reward!\n\n"
                f"💰 Current Balance: {coins_display(total_coins)}"
            )
        else:
            # Grant coins
            await self.db.add_coins(
                user_id, coins_earned, "streak",
                f"Day {new_streak} streak reward"
            )
            # Grant XP
            await self.db.add_xp(user_id, self.config.XP_DAILY_LOGIN)
            total_coins = await self.db.get_coins(user_id)

            # Milestone messages
            milestone = ""
            if new_streak == 7:
                milestone = "\n🎉 <b>MILESTONE: 7-Day Streak!</b> Amazing dedication!"
            elif new_streak == 30:
                milestone = "\n🏆 <b>MILESTONE: 30-Day Streak!</b> You're a legend!"
            elif new_streak % 10 == 0:
                milestone = f"\n🔥 <b>MILESTONE: {new_streak}-Day Streak!</b> Keep it up!"

            text = (
                f"🎁 <b>Daily Reward Claimed!</b>\n\n"
                f"{streak_badge(new_streak)}{milestone}\n\n"
                f"✨ <b>Rewards Earned:</b>\n"
                f"🪙 +{coins_earned} coins\n"
                f"⭐ +{self.config.XP_DAILY_LOGIN} XP\n\n"
                f"💰 Total Balance: {coins_display(total_coins)}\n\n"
                f"<b>Upcoming Rewards:</b>\n"
                f"{self._streak_preview(new_streak)}"
            )

        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    def _streak_preview(self, current: int) -> str:
        lines = []
        for day in [current + 1, current + 7, 30]:
            coins = min(day * 10, 100)
            if day == 30:
                lines.append(f"• Day 30: 🪙 100 coins + 🏆 Special Badge")
            else:
                lines.append(f"• Day {day}: 🪙 {coins} coins")
        return "\n".join(lines)
