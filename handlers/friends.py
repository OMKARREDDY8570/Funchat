"""
Friends handler - friend requests, friendships, friend codes.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database.db import Database
from utils.matching import MatchingEngine
from utils.keyboards import (
    friend_request_keyboard, friends_menu_keyboard, back_to_menu_keyboard
)

logger = logging.getLogger(__name__)

# Track pending state
_awaiting_friend_code = {}  # user_id -> True


class FriendHandler:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    async def handle_send_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        # Get current session
        matching: MatchingEngine = context.bot_data["matching_engine"]
        session = await matching.get_session_for_user(user_id)

        if not session:
            await query.answer("You need to be in a chat to send a friend request!", show_alert=True)
            return

        partner_id = session.user2_id if session.user1_id == user_id else session.user1_id

        if await self.db.are_friends(user_id, partner_id):
            await query.answer("You're already friends!", show_alert=True)
            return

        req_id = await self.db.send_friend_request(user_id, partner_id, session.session_id)
        if not req_id:
            await query.answer("Friend request already sent!", show_alert=True)
            return

        # Notify partner
        partner_identity = matching.get_identity_for_user(user_id)
        try:
            await context.bot.send_message(
                partner_id,
                f"🤝 <b>Friend Request!</b>\n\n"
                f"<b>{partner_identity}</b> wants to connect with you.\n\n"
                f"<i>This is completely anonymous — no personal info will be shared.</i>",
                parse_mode="HTML",
                reply_markup=friend_request_keyboard(req_id),
            )
        except Exception as e:
            logger.error(f"Error sending friend request notification: {e}")

        await query.answer("✅ Friend request sent!", show_alert=True)

    async def handle_accept_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        req_id = int(query.data.replace("accept_friend_", ""))

        req = await self.db.get_friend_request(req_id)
        if not req or req["status"] != "pending":
            await query.edit_message_text("⚠️ This friend request is no longer valid.")
            return

        if req["to_user_id"] != user_id:
            await query.answer("This request isn't for you!", show_alert=True)
            return

        # Create friendship
        code = await self.db.create_friendship(req["from_user_id"], user_id)
        await self.db.update_friend_request(req_id, "accepted")

        # Notify sender
        from_user = await self.db.get_user(req["from_user_id"])
        try:
            await context.bot.send_message(
                req["from_user_id"],
                f"🎉 <b>Friend Request Accepted!</b>\n\n"
                f"You're now anonymous friends!\n\n"
                f"🔑 <b>Your Friend Code:</b> <code>{code}</code>\n\n"
                f"<i>You can use this code to reconnect anytime.</i>",
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard(),
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"✅ <b>You're now friends!</b>\n\n"
            f"🔑 <b>Friend Code:</b> <code>{code}</code>\n\n"
            f"<i>Use this code to reconnect with your friend anytime!</i>",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )

    async def handle_reject_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer("Request declined.")
        req_id = int(query.data.replace("reject_friend_", ""))
        await self.db.update_friend_request(req_id, "rejected")
        await query.edit_message_text(
            "❌ Friend request declined.",
            reply_markup=back_to_menu_keyboard(),
        )

    async def handle_view_friends(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        friends = await self.db.get_friends(user_id)
        pending = await self.db.get_pending_requests(user_id)

        if not friends and not pending:
            text = (
                "👥 <b>Friends</b>\n\n"
                "You don't have any friends yet.\n\n"
                "Start a chat and send friend requests to connect anonymously!"
            )
        else:
            lines = ["👥 <b>Your Friends</b>\n"]
            for f in friends:
                lines.append(f"• <b>{f['first_name']}</b> · Code: <code>{f['friend_code']}</code>")

            if pending:
                lines.append(f"\n📬 <b>Pending Requests ({len(pending)})</b>")
                for r in pending:
                    sender = await self.db.get_user(r["from_user_id"])
                    name = sender["first_name"] if sender else "Someone"
                    lines.append(f"• From: {name}")

            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=friends_menu_keyboard(),
        )

    async def handle_friend_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        friends = await self.db.get_friends(user_id)
        if not friends:
            await query.edit_message_text(
                "🔑 <b>Friend Codes</b>\n\nYou don't have any friends yet!\n\n"
                "Complete chats and send friend requests to connect.",
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        lines = ["🔑 <b>Your Friend Codes</b>\n"]
        for f in friends:
            lines.append(f"• <b>{f['first_name']}</b>\n  Code: <code>{f['friend_code']}</code>")

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )

    async def handle_connect_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        _awaiting_friend_code[user_id] = True
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
        await query.edit_message_text(
            "🔗 <b>Connect via Friend Code</b>\n\n"
            "Please type your friend's code below.\n\n"
            "Example: <code>FC-84XK91</code>",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
