"""
Report handler - report users, block users.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database.db import Database
from utils.matching import MatchingEngine
from utils.keyboards import report_reasons_keyboard, back_to_menu_keyboard

logger = logging.getLogger(__name__)


class ReportHandler:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    async def handle_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        matching: MatchingEngine = context.bot_data["matching_engine"]
        user_id = update.effective_user.id
        partner_id = await matching.get_partner_id(user_id)

        if not partner_id:
            await query.answer("You need to be in a chat to report someone.", show_alert=True)
            return

        # Store target in context
        context.user_data["report_target"] = partner_id

        await query.edit_message_text(
            "🚨 <b>Report User</b>\n\n"
            "What's the reason for this report?",
            parse_mode="HTML",
            reply_markup=report_reasons_keyboard(),
        )

    async def handle_report_reason(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        reason = query.data.replace("report_reason_", "")
        reported_id = context.user_data.get("report_target")

        if not reported_id:
            await query.edit_message_text("⚠️ Report session expired.", reply_markup=back_to_menu_keyboard())
            return

        matching: MatchingEngine = context.bot_data["matching_engine"]
        session = await matching.get_session_for_user(user_id)
        session_id = session.session_id if session else None

        report_id = await self.db.create_report(user_id, reported_id, session_id, reason)

        # Auto-ban check
        report_count = await self.db.get_report_count(reported_id)
        if report_count >= self.config.MAX_REPORT_COUNT:
            await self.db.ban_user(reported_id, f"Auto-banned after {report_count} reports")
            logger.warning(f"Auto-banned user {reported_id} after {report_count} reports")
            # Notify admins
            for admin_id in self.config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"🚨 <b>Auto-ban triggered</b>\n\n"
                        f"User {reported_id} was auto-banned after {report_count} reports.\n"
                        f"Latest reason: {reason}",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        # Block user locally
        await self.db.block_user(user_id, reported_id)

        # End current session
        result = await matching.end_session(user_id)
        if result:
            session_id, partner_id, msgs = result

        await query.edit_message_text(
            f"✅ <b>Report submitted.</b>\n\n"
            f"Reason: <b>{reason}</b>\n\n"
            f"Thank you for helping keep FunChatBot safe!\n"
            f"The user has been blocked and will not be matched with you again.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        context.user_data.pop("report_target", None)
