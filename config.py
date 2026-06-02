"""
Configuration module - loads all settings from environment variables.
"""

import os
from typing import List


class Config:
    """Central configuration class loaded from environment variables."""

    def __init__(self):
        # Core Bot Settings
        self.BOT_TOKEN: str = self._require("BOT_TOKEN")
        self.ADMIN_IDS: List[int] = self._parse_admin_ids(os.getenv("ADMIN_IDS", ""))
        self.DATABASE_PATH: str = os.getenv("DATABASE_PATH", "/data/funchatbot.db")
        self.AI_API_KEY: str = os.getenv("AI_API_KEY", "")

        # Webhook settings
        self.WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
        self.PORT: int = int(os.getenv("PORT", "8080"))

        # Feature flags
        self.AI_ENABLED: bool = bool(self.AI_API_KEY)
        self.MAX_REPORT_COUNT: int = int(os.getenv("MAX_REPORT_COUNT", "5"))
        self.RATE_LIMIT_MESSAGES: int = int(os.getenv("RATE_LIMIT_MESSAGES", "30"))
        self.RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

        # Gamification
        self.XP_PER_MESSAGE: int = 1
        self.XP_PER_CHAT: int = 10
        self.XP_DAILY_LOGIN: int = 20
        self.COINS_PER_STREAK_DAY: int = 10
        self.REFERRAL_BONUS_COINS: int = 50

    def _require(self, key: str) -> str:
        val = os.getenv(key)
        if not val:
            raise ValueError(f"Required environment variable '{key}' is not set.")
        return val

    def _parse_admin_ids(self, raw: str) -> List[int]:
        if not raw:
            return []
        try:
            return [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            return []

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.ADMIN_IDS
