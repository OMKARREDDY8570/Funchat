"""
Keyboard builders - all inline and reply keyboards used in the bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from utils.matching import INTERESTS_LIST
from typing import List, Optional


def main_menu_keyboard(online: int = 0, waiting: int = 0, chatting: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Random Chat", callback_data="random_chat"),
            InlineKeyboardButton("🔍 Find by Interest", callback_data="find_interest"),
        ],
        [
            InlineKeyboardButton("👥 Friend Requests", callback_data="view_friends"),
            InlineKeyboardButton("⭐ Profile", callback_data="profile"),
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
            InlineKeyboardButton("🎁 Daily Rewards", callback_data="daily_reward"),
        ],
        [
            InlineKeyboardButton("📊 Statistics", callback_data="statistics"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ],
    ])


def chat_keyboard(has_friend_req: bool = True) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("⏭ Next", callback_data="next_chat"),
            InlineKeyboardButton("🛑 End Chat", callback_data="end_chat"),
        ],
        [
            InlineKeyboardButton("🤝 Friend Request", callback_data="send_friend_req"),
            InlineKeyboardButton("🚨 Report", callback_data="report_user"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def searching_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Search", callback_data="end_chat")]
    ])


def rating_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Good", callback_data=f"rate_good_{session_id}"),
            InlineKeyboardButton("😐 Neutral", callback_data=f"rate_neutral_{session_id}"),
            InlineKeyboardButton("👎 Bad", callback_data=f"rate_bad_{session_id}"),
        ]
    ])


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])


def interests_keyboard(selected: Optional[List[str]] = None) -> InlineKeyboardMarkup:
    selected = selected or []
    buttons = []
    row = []
    for i, interest in enumerate(INTERESTS_LIST):
        check = "✅ " if interest in selected else ""
        row.append(InlineKeyboardButton(f"{check}{interest}", callback_data=f"interest_{interest}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([
        InlineKeyboardButton("🔍 Start Search", callback_data="start_interest_search"),
        InlineKeyboardButton("🏠 Menu", callback_data="main_menu"),
    ])
    return InlineKeyboardMarkup(buttons)


def friend_request_keyboard(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"accept_friend_{req_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_friend_{req_id}"),
        ]
    ])


def friends_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 My Friends", callback_data="view_friends"),
            InlineKeyboardButton("🔑 Friend Code", callback_data="friend_code"),
        ],
        [
            InlineKeyboardButton("🔗 Connect via Code", callback_data="connect_code"),
            InlineKeyboardButton("🏠 Menu", callback_data="main_menu"),
        ]
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Set Gender", callback_data="gender_select"),
            InlineKeyboardButton("🌐 Language", callback_data="lang_select"),
        ],
        [InlineKeyboardButton("🏠 Menu", callback_data="main_menu")]
    ])


def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👨 Male", callback_data="gender_male"),
            InlineKeyboardButton("👩 Female", callback_data="gender_female"),
        ],
        [
            InlineKeyboardButton("🌈 Other", callback_data="gender_other"),
            InlineKeyboardButton("🔒 Prefer not to say", callback_data="gender_unknown"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="settings")]
    ])


def report_reasons_keyboard() -> InlineKeyboardMarkup:
    reasons = ["Spam", "Harassment", "Inappropriate Content", "Scam", "Underage", "Other"]
    buttons = [[InlineKeyboardButton(r, callback_data=f"report_reason_{r}")] for r in reasons]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def ai_chat_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Chat with AI", callback_data="ai_chat")],
        [InlineKeyboardButton("🔄 Keep Searching", callback_data="random_chat")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
    ])
