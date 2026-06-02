"""
Start handler - /start command, onboarding, referral system.
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database.db import Database
from utils.keyboards import main_menu_keyboard, back_to_menu_keyboard
from utils.helpers import require_not_banned

logger = logging.getLogger(__name__)


class StartHandler:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        args = context.args

        # Check for referral code
        referred_by: Optional[int] = None
        if args:
            ref_code = args[0]
            if ref_code.startswith("FC-") or ref_code.startswith("ref_"):
                raw_code = ref_code.replace("ref_", "FC-") if ref_code.startswith("ref_") else ref_code
                referrer = await self.db.get_user_by_referral(raw_code)
                if referrer and referrer["user_id"] != user.id:
                    referred_by = referrer["user_id"]

        # Get or create user
        db_user = await self.db.get_or_create_user(
            user_id=user.id,
            first_name=user.first_name,
            username=user.username,
            language_code=user.language_code or "en",
            referred_by=referred_by,
        )

        # Grant referral bonus
        if referred_by and db_user.get("referred_by") == referred_by:
            referrer = await self.db.get_user(referred_by)
            if referrer:
                await self.db.add_coins(
                    referred_by, self.config.REFERRAL_BONUS_COINS,
                    "referral", f"Referral bonus: {user.first_name} joined"
                )
                await self.db.add_coins(
                    user.id, 25, "referral_welcome", "Welcome bonus for joining via referral"
                )
                try:
                    await context.bot.send_message(
                        referred_by,
                        f"🎉 <b>Referral Bonus!</b>\n\n"
                        f"Someone joined using your referral link!\n"
                        f"You earned <b>🪙 {self.config.REFERRAL_BONUS_COINS} coins</b>!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # Build stats for welcome message
        online = await self.db.get_online_count()
        chats_today = await self.db.get_chats_today()
        waiting = await self.db.get_full_stats()

        welcome_text = (
            f"👋 <b>Welcome to FunChatBot!</b>\n\n"
            f"🌐 Connect with random strangers anonymously.\n"
            f"Chat, make friends, and have fun — no personal info shared!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 <b>Online:</b> {online} users\n"
            f"💬 <b>Chats Today:</b> {chats_today}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Choose what you'd like to do:"
        )

        await update.message.reply_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(online),
        )

    async def handle_referral(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        db_user = await self.db.get_user(user_id)
        if not db_user:
            await update.message.reply_text("Please /start first!")
            return

        ref_code = db_user["referral_code"]
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={ref_code.replace('-', '_').replace('FC_', 'ref_')}"

        text = (
            f"🎁 <b>Your Referral Program</b>\n\n"
            f"Share your unique link and earn coins!\n\n"
            f"<b>Your Code:</b> <code>{ref_code}</code>\n"
            f"<b>Your Link:</b>\n{ref_link}\n\n"
            f"💰 <b>Rewards:</b>\n"
            f"• You earn <b>🪙 {self.config.REFERRAL_BONUS_COINS} coins</b> per referral\n"
            f"• Your friend gets <b>🪙 25 welcome coins</b>\n\n"
            f"Share with friends and grow together! 🚀"
        )

        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
