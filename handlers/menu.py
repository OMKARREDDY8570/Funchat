"""
Menu handler - main menu, stats, leaderboard, help.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database.db import Database
from utils.keyboards import main_menu_keyboard, back_to_menu_keyboard
from utils.helpers import format_number, get_rank_badge, MEDALS

logger = logging.getLogger(__name__)


class MenuHandler:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    async def handle_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        online = await self.db.get_online_count()
        chats_today = await self.db.get_chats_today()

        text = (
            f"🏠 <b>FunChatBot Menu</b>\n\n"
            f"🟢 Online: {online} · 💬 Chats today: {chats_today}\n\n"
            f"What would you like to do?"
        )

        if update.message:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard(online))
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard(online))

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        online = await self.db.get_online_count()
        chats_today = await self.db.get_chats_today()

        text = (
            f"🏠 <b>FunChatBot Menu</b>\n\n"
            f"🟢 Online: {online} · 💬 Chats today: {chats_today}\n\n"
            f"What would you like to do?"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard(online))

    async def handle_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        leaders = await self.db.get_leaderboard(10)
        lines = ["🏆 <b>Top Chatters Leaderboard</b>\n"]
        for i, row in enumerate(leaders):
            medal = MEDALS[i] if i < 3 else f"{i+1}."
            badge = get_rank_badge(row["level"])
            lines.append(
                f"{medal} <b>{row['first_name']}</b>\n"
                f"   {badge} · Lv.{row['level']} · {format_number(row['total_xp'])} XP"
            )
        text = "\n".join(lines) if len(lines) > 1 else "🏆 No users on the leaderboard yet!"

        if update.message:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    async def handle_leaderboard_cb(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        leaders = await self.db.get_leaderboard(10)
        lines = ["🏆 <b>Top Chatters Leaderboard</b>\n"]
        for i, row in enumerate(leaders):
            medal = MEDALS[i] if i < 3 else f"{i+1}."
            badge = get_rank_badge(row["level"])
            lines.append(
                f"{medal} <b>{row['first_name']}</b>\n"
                f"   {badge} · Lv.{row['level']} · {format_number(row['total_xp'])} XP"
            )
        text = "\n".join(lines) if len(lines) > 1 else "🏆 No users on the leaderboard yet!"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    async def handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        stats = await self.db.get_full_stats()
        text = self._build_stats_text(stats)
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    async def handle_stats_cb(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        stats = await self.db.get_full_stats()
        text = self._build_stats_text(stats)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    def _build_stats_text(self, stats: dict) -> str:
        return (
            f"📊 <b>FunChatBot Statistics</b>\n\n"
            f"👥 Total Users: <b>{format_number(stats['total_users'])}</b>\n"
            f"🟢 Online Now: <b>{stats['active_today']}</b>\n"
            f"💬 Active Chats: <b>{stats['active_chats']}</b>\n"
            f"📅 Chats Today: <b>{format_number(stats['chats_today'])}</b>\n"
            f"🗨️ Total Chats: <b>{format_number(stats['total_chats'])}</b>\n"
            f"📨 Messages Sent: <b>{format_number(stats['total_messages'])}</b>\n"
        )

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = self._help_text()
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    async def handle_help_cb(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        text = self._help_text()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    def _help_text(self) -> str:
        return (
            "❓ <b>FunChatBot Help</b>\n\n"
            "<b>🎲 Random Chat</b> — Connect with a random stranger anonymously\n"
            "<b>🔍 Find by Interest</b> — Match with people who share your interests\n"
            "<b>⏭ Next</b> — Skip to the next stranger\n"
            "<b>🛑 End Chat</b> — End current conversation\n"
            "<b>🤝 Friend Request</b> — Send a friend request during chat\n"
            "<b>🚨 Report</b> — Report inappropriate behavior\n\n"
            "<b>💰 Earn Coins:</b>\n"
            "• Daily login streak rewards\n"
            "• Complete chats\n"
            "• Refer friends\n\n"
            "<b>⭐ Earn XP:</b>\n"
            "• Send messages (+1 XP each)\n"
            "• Complete chats (+10 XP)\n"
            "• Get good ratings (+5 XP)\n\n"
            "<b>Commands:</b>\n"
            "/start — Start the bot\n"
            "/menu — Show main menu\n"
            "/profile — Your profile\n"
            "/referral — Referral link\n"
            "/stats — Bot statistics\n"
            "/leaderboard — Top users\n"
        )
