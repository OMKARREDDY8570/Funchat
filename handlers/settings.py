"""
Settings handler - user preferences, gender, language.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database.db import Database
from utils.keyboards import settings_keyboard, gender_keyboard, back_to_menu_keyboard

logger = logging.getLogger(__name__)


class SettingsHandler:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    async def handle_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        user = await self.db.get_user(user_id)

        gender_map = {
            "male": "👨 Male",
            "female": "👩 Female",
            "other": "🌈 Other",
            "unknown": "🔒 Not set",
        }
        gender = gender_map.get(user.get("gender", "unknown"), "Not set") if user else "Not set"

        text = (
            f"⚙️ <b>Settings</b>\n\n"
            f"👤 Gender: {gender}\n"
            f"🌐 Language: {user.get('language_code', 'en').upper() if user else 'EN'}\n\n"
            f"Customize your experience:"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=settings_keyboard())

    async def handle_gender_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "👤 <b>Select your gender:</b>\n\n<i>This is optional and used only for matching preferences.</i>",
            parse_mode="HTML",
            reply_markup=gender_keyboard(),
        )

    async def handle_language_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        # For now, English only
        await query.answer("🌐 More languages coming soon!", show_alert=True)

    async def handle_set_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle gender_* callbacks from gender_keyboard."""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        gender = query.data.replace("gender_", "")

        await self.db._conn.execute(
            "UPDATE users SET gender = ? WHERE user_id = ?", (gender, user_id)
        )
        await self.db._conn.commit()

        gender_map = {
            "male": "👨 Male",
            "female": "👩 Female",
            "other": "🌈 Other",
            "unknown": "🔒 Prefer not to say",
        }
        await query.edit_message_text(
            f"✅ Gender set to <b>{gender_map.get(gender, gender)}</b>",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
