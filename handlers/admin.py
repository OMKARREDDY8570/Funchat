"""
Admin handler - admin panel, ban/unban, broadcast, stats review.
"""

import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import Config
from database.db import Database
from utils.helpers import format_number

logger = logging.getLogger(__name__)


def admin_only(func):
    """Decorator to restrict to admins."""
    import functools

    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not self.config.is_admin(user_id):
            if update.message:
                await update.message.reply_text("🚫 Admin access required.")
            elif update.callback_query:
                await update.callback_query.answer("🚫 Admin access required.", show_alert=True)
            return
        return await func(self, update, context, *args, **kwargs)

    return wrapper


class AdminHandler:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    @admin_only
    async def handle_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text, kb = await self._admin_panel_content()
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

    @admin_only
    async def handle_admin_cb(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        action = query.data.replace("admin_", "")

        if action == "panel":
            text, kb = await self._admin_panel_content()
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

        elif action == "reports":
            reports = await self.db.get_pending_reports()
            if not reports:
                text = "📋 <b>Reports</b>\n\nNo pending reports. 🎉"
            else:
                lines = [f"📋 <b>Pending Reports ({len(reports)})</b>\n"]
                for r in reports[:10]:
                    lines.append(
                        f"• #{r['id']} | <b>{r['reported_name']}</b>\n"
                        f"  Reason: {r['reason']} | By: {r['reporter_name']}"
                    )
                text = "\n".join(lines)

            await query.edit_message_text(
                text, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
                ]])
            )

        elif action == "stats":
            stats = await self.db.get_full_stats()
            matching = context.bot_data["matching_engine"]
            queue = await matching.get_queue_count()
            active = await matching.get_active_sessions_count()

            text = (
                f"📊 <b>Live Admin Stats</b>\n\n"
                f"👥 Total Users: {format_number(stats['total_users'])}\n"
                f"🟢 Online: {stats['active_today']}\n"
                f"⏳ In Queue: {queue}\n"
                f"💬 Active Chats: {active}\n"
                f"📅 Chats Today: {format_number(stats['chats_today'])}\n"
                f"📨 Total Messages: {format_number(stats['total_messages'])}\n"
                f"🗨️ Total Chats: {format_number(stats['total_chats'])}\n"
            )
            await query.edit_message_text(
                text, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
                ]])
            )

    async def _admin_panel_content(self):
        stats = await self.db.get_full_stats()
        text = (
            f"🔧 <b>Admin Panel</b>\n\n"
            f"👥 Users: {format_number(stats['total_users'])}\n"
            f"🟢 Online: {stats['active_today']}\n"
            f"💬 Chats Today: {format_number(stats['chats_today'])}\n\n"
            f"Use the buttons below to manage the bot:"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Live Stats", callback_data="admin_stats"),
                InlineKeyboardButton("📋 Reports", callback_data="admin_reports"),
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            ],
        ])
        return text, kb

    @admin_only
    async def handle_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Usage: /ban <user_id> [reason]")
            return

        target_id = int(args[0])
        reason = " ".join(args[1:]) if len(args) > 1 else "Admin ban"
        await self.db.ban_user(target_id, reason)
        await update.message.reply_text(
            f"✅ User <code>{target_id}</code> banned.\nReason: {reason}",
            parse_mode="HTML"
        )
        try:
            await context.bot.send_message(
                target_id,
                f"🚫 You have been banned from FunChatBot.\nReason: {reason}"
            )
        except Exception:
            pass

    @admin_only
    async def handle_unban(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Usage: /unban <user_id>")
            return

        target_id = int(args[0])
        await self.db.unban_user(target_id)
        await update.message.reply_text(
            f"✅ User <code>{target_id}</code> unbanned.",
            parse_mode="HTML"
        )
        try:
            await context.bot.send_message(target_id, "✅ Your ban has been lifted. Welcome back to FunChatBot!")
        except Exception:
            pass

    @admin_only
    async def handle_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Broadcast a message to all users. Usage: /broadcast <message>"""
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /broadcast <your message here>")
            return

        message = " ".join(args)
        broadcast_text = (
            f"📢 <b>Announcement from FunChatBot</b>\n\n"
            f"{message}"
        )

        # Get all non-banned users
        async with self.db._conn.execute(
            "SELECT user_id FROM users WHERE is_banned = 0"
        ) as cursor:
            rows = await cursor.fetchall()

        sent = 0
        failed = 0
        for row in rows:
            try:
                await context.bot.send_message(row[0], broadcast_text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1

        await update.message.reply_text(
            f"📢 Broadcast complete!\n✅ Sent: {sent}\n❌ Failed: {failed}"
        )
