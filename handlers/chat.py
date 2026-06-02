"""
Chat handler - random matching, message relay, skip, end, ratings, AI fallback.
"""

import asyncio
import logging
from typing import Optional

from telegram import Update, Message
from telegram.ext import ContextTypes

from config import Config
from database.db import Database
from utils.matching import MatchingEngine, INTERESTS_LIST
from utils.keyboards import (
    chat_keyboard, searching_keyboard, rating_keyboard,
    back_to_menu_keyboard, interests_keyboard, ai_chat_keyboard, main_menu_keyboard
)
from utils.helpers import require_not_banned

logger = logging.getLogger(__name__)

# Premium message styles
PREMIUM_STYLES = {
    "glow": ("✨", "✨"),
    "fire": ("🔥", "🔥"),
    "celebrate": ("🎉", "🎉"),
    "vip": ("💎", "💎"),
    "star": ("⭐", "⭐"),
}

# Temporary state storage (user_id -> data)
_user_interests_selection = {}  # user_id -> List[str]
_user_awaiting_ai = {}          # user_id -> bool
_user_premium_mode = {}         # user_id -> style


class ChatHandler:
    def __init__(self, db: Database, config: Config, matching: MatchingEngine):
        self.db = db
        self.config = config
        self.matching = matching

    # ─── Random Chat ──────────────────────────────────────────────

    @require_not_banned
    async def handle_random_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        # End any existing session
        result = await self.matching.end_session(user_id)
        if result:
            session_id, partner_id, msgs = result
            await self._notify_partner_disconnected(partner_id, session_id, msgs, context)

        await self.matching.remove_from_queue(user_id)

        # Add to queue and try to match
        await self.matching.add_to_queue(user_id)
        match = await self.matching.try_match(user_id)

        if match:
            partner_id, session_id, matched_interests = match
            await self._start_chat(user_id, partner_id, session_id, matched_interests, context)
        else:
            online = await self.db.get_online_count()
            await query.edit_message_text(
                f"🔍 <b>Searching for a stranger...</b>\n\n"
                f"🟢 {online} users online\n"
                f"⏳ Finding your match...\n\n"
                f"<i>This may take a moment. Please wait!</i>",
                parse_mode="HTML",
                reply_markup=searching_keyboard(),
            )
            # Schedule periodic match check
            asyncio.create_task(self._poll_for_match(user_id, query.message, context))

    async def _poll_for_match(self, user_id: int, message: Message,
                               context: ContextTypes.DEFAULT_TYPE, attempts: int = 0) -> None:
        """Poll for a match every 2 seconds, up to 5 minutes."""
        max_attempts = 150  # 5 minutes

        await asyncio.sleep(2)

        if not await self.matching.is_in_queue(user_id):
            return  # Already matched or cancelled

        match = await self.matching.try_match(user_id)
        if match:
            partner_id, session_id, matched_interests = match
            await self._start_chat(user_id, partner_id, session_id, matched_interests, context, message)
            return

        if attempts >= max_attempts:
            await self.matching.remove_from_queue(user_id)
            try:
                await message.edit_text(
                    "😔 <b>No one found nearby.</b>\n\n"
                    "Try again or chat with AI!",
                    parse_mode="HTML",
                    reply_markup=ai_chat_keyboard() if self.config.AI_ENABLED else back_to_menu_keyboard(),
                )
            except Exception:
                pass
            return

        if attempts % 15 == 14:  # Update message every 30 seconds
            try:
                online = await self.db.get_online_count()
                await message.edit_text(
                    f"🔍 <b>Still searching...</b>\n\n"
                    f"🟢 {online} users online\n"
                    f"⏳ Waited: {(attempts + 1) * 2}s\n\n"
                    f"<i>Hang tight! We're finding you a match.</i>",
                    parse_mode="HTML",
                    reply_markup=searching_keyboard(),
                )
            except Exception:
                pass

        asyncio.create_task(self._poll_for_match(user_id, message, context, attempts + 1))

    async def _start_chat(self, user1_id: int, user2_id: int, session_id: int,
                           matched_interests, context: ContextTypes.DEFAULT_TYPE,
                           message=None) -> None:
        """Notify both users that chat has started."""
        identity1 = self.matching.get_identity_for_user(user1_id)
        identity2 = self.matching.get_partner_identity(user1_id)

        interest_text = ""
        if matched_interests:
            interest_text = f"\n\n✨ <b>Matched because you both like:</b>\n{', '.join(matched_interests)}"

        msg1 = (
            f"🎉 <b>Connected!</b>\n\n"
            f"You are chatting with:\n<b>{identity2}</b>{interest_text}\n\n"
            f"<i>Say hello! Your identity is anonymous 🎭</i>"
        )
        msg2 = (
            f"🎉 <b>Connected!</b>\n\n"
            f"You are chatting with:\n<b>{identity1}</b>{interest_text}\n\n"
            f"<i>Say hello! Your identity is anonymous 🎭</i>"
        )

        kb = chat_keyboard()
        try:
            if message:
                await message.edit_text(msg1, parse_mode="HTML", reply_markup=kb)
            else:
                await context.bot.send_message(user1_id, msg1, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            logger.error(f"Error notifying user1 {user1_id}: {e}")

        try:
            await context.bot.send_message(user2_id, msg2, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            logger.error(f"Error notifying user2 {user2_id}: {e}")

        # Award XP for starting a chat
        await self.db.add_xp(user1_id, self.config.XP_PER_CHAT)
        await self.db.add_xp(user2_id, self.config.XP_PER_CHAT)

    async def _notify_partner_disconnected(self, partner_id: int, session_id: int,
                                            msgs: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            await context.bot.send_message(
                partner_id,
                "👋 <b>Your partner has left the chat.</b>\n\n"
                "Click below to find a new stranger!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkupDisconnected(),
            )
            # Show rating prompt
            await context.bot.send_message(
                partner_id,
                "⭐ <b>Rate your chat experience:</b>",
                parse_mode="HTML",
                reply_markup=rating_keyboard(session_id),
            )
        except Exception:
            pass

    # ─── Next / Skip ──────────────────────────────────────────────

    @require_not_banned
    async def handle_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer("⏭ Finding next stranger...")
        user_id = update.effective_user.id

        result = await self.matching.end_session(user_id)
        if result:
            session_id, partner_id, msgs = result
            await self._notify_partner_disconnected(partner_id, session_id, msgs, context)
            # Offer rating
            await context.bot.send_message(
                user_id,
                "⭐ <b>Rate your chat:</b>",
                parse_mode="HTML",
                reply_markup=rating_keyboard(session_id),
            )

        # Jump straight back into queue
        await self.matching.remove_from_queue(user_id)
        await self.matching.add_to_queue(user_id)
        match = await self.matching.try_match(user_id)

        if match:
            partner_id, session_id, matched_interests = match
            await context.bot.send_message(
                user_id,
                "✅ New match found immediately!",
            )
            await self._start_chat(user_id, partner_id, session_id, matched_interests, context)
        else:
            online = await self.db.get_online_count()
            try:
                await query.edit_message_text(
                    f"🔍 <b>Searching for next stranger...</b>\n\n"
                    f"🟢 {online} online\n<i>Finding your match...</i>",
                    parse_mode="HTML",
                    reply_markup=searching_keyboard(),
                )
                asyncio.create_task(self._poll_for_match(user_id, query.message, context))
            except Exception:
                pass

    # ─── End Chat ─────────────────────────────────────────────────

    @require_not_banned
    async def handle_end_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer("Chat ended.")
        user_id = update.effective_user.id

        # Remove from queue (if searching)
        was_in_queue = await self.matching.remove_from_queue(user_id)

        # End session (if chatting)
        result = await self.matching.end_session(user_id)

        if result:
            session_id, partner_id, msgs = result
            await self._notify_partner_disconnected(partner_id, session_id, msgs, context)
            await context.bot.send_message(
                user_id,
                "⭐ <b>Rate your chat experience:</b>",
                parse_mode="HTML",
                reply_markup=rating_keyboard(session_id),
            )
            end_text = (
                f"🛑 <b>Chat ended.</b>\n\n"
                f"📊 Messages exchanged: {msgs}\n\n"
                f"Thanks for chatting! Find a new stranger anytime."
            )
        elif was_in_queue:
            end_text = "❌ <b>Search cancelled.</b>"
        else:
            end_text = "You're not in a chat."

        online = await self.db.get_online_count()
        chats_today = await self.db.get_chats_today()

        try:
            await query.edit_message_text(
                end_text + f"\n\n🟢 {online} online · 💬 {chats_today} chats today",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(online),
            )
        except Exception:
            pass

    # ─── Interest Matching ────────────────────────────────────────

    @require_not_banned
    async def handle_find_interest(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        # Load existing interests
        selected = await self.db.get_user_interests(user_id)
        _user_interests_selection[user_id] = selected.copy()

        await query.edit_message_text(
            "🔍 <b>Find by Interest</b>\n\n"
            "Select your interests to find someone with similar tastes.\n"
            "<i>Tap to select/deselect:</i>",
            parse_mode="HTML",
            reply_markup=interests_keyboard(selected),
        )

    @require_not_banned
    async def handle_interest_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        user_id = update.effective_user.id
        interest = query.data.replace("interest_", "")

        selected = _user_interests_selection.get(user_id, [])
        if interest in selected:
            selected.remove(interest)
        else:
            selected.append(interest)
        _user_interests_selection[user_id] = selected

        await query.answer(f"{'✅' if interest in selected else '❌'} {interest}")
        await query.edit_message_reply_markup(reply_markup=interests_keyboard(selected))

    @require_not_banned
    async def handle_start_interest_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        selected = _user_interests_selection.get(user_id, [])
        if not selected:
            await query.answer("⚠️ Please select at least one interest!", show_alert=True)
            return

        # Save interests
        await self.db.set_user_interests(user_id, selected)

        # End current session/queue
        await self.matching.remove_from_queue(user_id)
        result = await self.matching.end_session(user_id)
        if result:
            session_id, partner_id, msgs = result
            await self._notify_partner_disconnected(partner_id, session_id, msgs, context)

        # Queue with interest mode
        await self.matching.add_to_queue(user_id, interests=selected, interest_mode=True)
        match = await self.matching.try_match(user_id)

        if match:
            partner_id, session_id, matched_interests = match
            await self._start_chat(user_id, partner_id, session_id, matched_interests, context, query.message)
        else:
            await query.edit_message_text(
                f"🔍 <b>Searching with interests:</b>\n{', '.join(selected)}\n\n"
                f"⏳ Finding someone who shares your interests...",
                parse_mode="HTML",
                reply_markup=searching_keyboard(),
            )
            asyncio.create_task(self._poll_for_match(user_id, query.message, context))

    # ─── Message Relay ────────────────────────────────────────────

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id

        # Update last seen
        await self.db.update_last_seen(user_id)

        # Rate limiting
        allowed = await self.db.check_rate_limit(
            user_id, "message",
            self.config.RATE_LIMIT_MESSAGES,
            self.config.RATE_LIMIT_WINDOW
        )
        if not allowed:
            await update.message.reply_text("⚠️ You're sending messages too fast! Please slow down.")
            return

        # Check if in AI mode
        if _user_awaiting_ai.get(user_id):
            await self._handle_ai_message(update, context)
            return

        # Check if in active chat
        session = await self.matching.get_session_for_user(user_id)
        if not session:
            # Not in a chat — show menu
            if update.message.text:
                online = await self.db.get_online_count()
                chats_today = await self.db.get_chats_today()
                await update.message.reply_text(
                    f"👋 Use the menu to start chatting!\n\n"
                    f"🟢 {online} online · 💬 {chats_today} chats today",
                    reply_markup=main_menu_keyboard(online),
                )
            return

        partner_id = session.user2_id if session.user1_id == user_id else session.user1_id

        # Check premium mode
        premium_style = _user_premium_mode.pop(user_id, None)

        # Relay message
        try:
            msg = update.message
            partner_identity = self.matching.get_partner_identity(partner_id)

            if msg.text:
                text = msg.text
                if premium_style and premium_style in PREMIUM_STYLES:
                    left, right = PREMIUM_STYLES[premium_style]
                    text = f"{left} {text} {right}"
                await context.bot.send_message(partner_id, text)

            elif msg.photo:
                await context.bot.send_photo(partner_id, msg.photo[-1].file_id,
                                              caption=msg.caption)
            elif msg.sticker:
                await context.bot.send_sticker(partner_id, msg.sticker.file_id)
            elif msg.voice:
                await context.bot.send_voice(partner_id, msg.voice.file_id,
                                              caption=msg.caption)
            elif msg.video:
                await context.bot.send_video(partner_id, msg.video.file_id,
                                              caption=msg.caption)
            elif msg.animation:
                await context.bot.send_animation(partner_id, msg.animation.file_id,
                                                  caption=msg.caption)
            elif msg.document:
                await context.bot.send_document(partner_id, msg.document.file_id,
                                                 caption=msg.caption)
            elif msg.audio:
                await context.bot.send_audio(partner_id, msg.audio.file_id,
                                              caption=msg.caption)
            else:
                return

        except Exception as e:
            logger.error(f"Error relaying message from {user_id} to {partner_id}: {e}")
            await update.message.reply_text("⚠️ Failed to send message. Your partner may have left.")
            return

        # Track stats
        await self.matching.increment_messages(user_id)
        await self.db.add_xp(user_id, self.config.XP_PER_MESSAGE)

    # ─── AI Chat ──────────────────────────────────────────────────

    @require_not_banned
    async def handle_ai_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        if not self.config.AI_ENABLED:
            await query.edit_message_text(
                "🤖 <b>AI Chat is not available right now.</b>\n\n"
                "Our AI mode is currently disabled. Please try finding a human match!",
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        _user_awaiting_ai[user_id] = True
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            "🤖 <b>AI Chat Mode</b>\n\n"
            "You're now chatting with an AI! Ask anything.\n\n"
            "<i>Type /menu or use the button below to exit.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 Exit AI Chat", callback_data="end_chat")]
            ]),
        )

    async def _handle_ai_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle AI conversation."""
        user_id = update.effective_user.id
        if not update.message or not update.message.text:
            return

        await context.bot.send_chat_action(user_id, "typing")

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.config.AI_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 500,
                        "system": (
                            "You are a friendly anonymous chat partner on FunChatBot. "
                            "Be engaging, fun, and keep responses short (2-3 sentences max). "
                            "You're chatting with someone who wants casual conversation."
                        ),
                        "messages": [{"role": "user", "content": update.message.text}],
                    }
                ) as resp:
                    data = await resp.json()
                    ai_text = data["content"][0]["text"]

            await update.message.reply_text(f"🤖 {ai_text}")

        except Exception as e:
            logger.error(f"AI API error: {e}")
            _user_awaiting_ai.pop(user_id, None)
            await update.message.reply_text(
                "🤖 Sorry, I'm having trouble responding. Please try again or find a human match!",
                reply_markup=back_to_menu_keyboard(),
            )

    # ─── Rating ───────────────────────────────────────────────────

    async def handle_rating(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        parts = query.data.split("_")
        rating = parts[1]
        session_id = int(parts[2])
        user_id = update.effective_user.id

        # Get the other user from session
        await query.answer("Thanks for rating!")

        # Store rating (need to find partner from session)
        async with self.db._conn.execute(
            "SELECT user1_id, user2_id FROM chat_sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            partner_id = row[1] if row[0] == user_id else row[0]
            await self.db.add_rating(user_id, partner_id, session_id, rating)

            # Reward for good rating
            if rating == "good":
                await self.db.add_xp(partner_id, 5)

        online = await self.db.get_online_count()
        try:
            await query.edit_message_text(
                f"{'⭐' if rating == 'good' else '😐' if rating == 'neutral' else '👎'} Rating submitted!\n\n"
                f"Thanks for helping keep the community positive.",
                reply_markup=main_menu_keyboard(online),
            )
        except Exception:
            pass


def InlineKeyboardMarkupDisconnected():
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Find New Stranger", callback_data="random_chat"),
            InlineKeyboardButton("🏠 Menu", callback_data="main_menu"),
        ]
    ])
