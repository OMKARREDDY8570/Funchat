"""
FunChatBot - Anonymous Random Chat Bot
Main entry point for the Telegram bot.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from database.db import Database
from handlers.start import StartHandler
from handlers.chat import ChatHandler
from handlers.menu import MenuHandler
from handlers.profile import ProfileHandler
from handlers.friends import FriendHandler
from handlers.rewards import RewardHandler
from handlers.settings import SettingsHandler
from handlers.admin import AdminHandler
from handlers.report import ReportHandler
from utils.matching import MatchingEngine
from utils.scheduler import Scheduler
from config import Config

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class FunChatBot:
    """Main bot class orchestrating all components."""

    def __init__(self):
        self.config = Config()
        self.db: Optional[Database] = None
        self.app: Optional[Application] = None
        self.matching_engine: Optional[MatchingEngine] = None
        self.scheduler: Optional[Scheduler] = None
        self.web_app: Optional[web.Application] = None

    async def initialize(self) -> None:
        """Initialize all bot components."""
        logger.info("Initializing FunChatBot...")

        # Initialize database
        self.db = Database(self.config.DATABASE_PATH)
        await self.db.initialize()
        logger.info("Database initialized.")

        # Initialize matching engine
        self.matching_engine = MatchingEngine(self.db)

        # Initialize scheduler
        self.scheduler = Scheduler(self.db, self.matching_engine)

        # Build Telegram application
        self.app = (
            Application.builder()
            .token(self.config.BOT_TOKEN)
            .build()
        )

        # Store shared data
        self.app.bot_data["db"] = self.db
        self.app.bot_data["config"] = self.config
        self.app.bot_data["matching_engine"] = self.matching_engine

        # Register handlers
        self._register_handlers()

        logger.info("Bot initialized successfully.")

    def _register_handlers(self) -> None:
        """Register all command and message handlers."""
        app = self.app

        start_h = StartHandler(self.db, self.config)
        chat_h = ChatHandler(self.db, self.config, self.matching_engine)
        menu_h = MenuHandler(self.db, self.config)
        profile_h = ProfileHandler(self.db, self.config)
        friend_h = FriendHandler(self.db, self.config)
        reward_h = RewardHandler(self.db, self.config)
        settings_h = SettingsHandler(self.db, self.config)
        admin_h = AdminHandler(self.db, self.config)
        report_h = ReportHandler(self.db, self.config)

        # Commands
        app.add_handler(CommandHandler("start", start_h.handle_start))
        app.add_handler(CommandHandler("menu", menu_h.handle_menu))
        app.add_handler(CommandHandler("profile", profile_h.handle_profile))
        app.add_handler(CommandHandler("stats", menu_h.handle_stats))
        app.add_handler(CommandHandler("leaderboard", menu_h.handle_leaderboard))
        app.add_handler(CommandHandler("referral", start_h.handle_referral))
        app.add_handler(CommandHandler("admin", admin_h.handle_admin))
        app.add_handler(CommandHandler("ban", admin_h.handle_ban))
        app.add_handler(CommandHandler("unban", admin_h.handle_unban))
        app.add_handler(CommandHandler("broadcast", admin_h.handle_broadcast))
        app.add_handler(CommandHandler("help", menu_h.handle_help))

        # Callback queries (button presses)
        app.add_handler(CallbackQueryHandler(chat_h.handle_random_chat, pattern="^random_chat$"))
        app.add_handler(CallbackQueryHandler(chat_h.handle_find_interest, pattern="^find_interest$"))
        app.add_handler(CallbackQueryHandler(chat_h.handle_next, pattern="^next_chat$"))
        app.add_handler(CallbackQueryHandler(chat_h.handle_end_chat, pattern="^end_chat$"))
        app.add_handler(CallbackQueryHandler(chat_h.handle_interest_select, pattern="^interest_"))
        app.add_handler(CallbackQueryHandler(chat_h.handle_start_interest_search, pattern="^start_interest_search$"))
        app.add_handler(CallbackQueryHandler(chat_h.handle_ai_chat, pattern="^ai_chat$"))
        app.add_handler(CallbackQueryHandler(friend_h.handle_send_request, pattern="^send_friend_req$"))
        app.add_handler(CallbackQueryHandler(friend_h.handle_accept_request, pattern="^accept_friend_"))
        app.add_handler(CallbackQueryHandler(friend_h.handle_reject_request, pattern="^reject_friend_"))
        app.add_handler(CallbackQueryHandler(friend_h.handle_view_friends, pattern="^view_friends$"))
        app.add_handler(CallbackQueryHandler(friend_h.handle_friend_code, pattern="^friend_code$"))
        app.add_handler(CallbackQueryHandler(friend_h.handle_connect_code, pattern="^connect_code$"))
        app.add_handler(CallbackQueryHandler(profile_h.handle_profile_cb, pattern="^profile$"))
        app.add_handler(CallbackQueryHandler(reward_h.handle_daily_reward, pattern="^daily_reward$"))
        app.add_handler(CallbackQueryHandler(menu_h.handle_leaderboard_cb, pattern="^leaderboard$"))
        app.add_handler(CallbackQueryHandler(menu_h.handle_stats_cb, pattern="^statistics$"))
        app.add_handler(CallbackQueryHandler(menu_h.handle_main_menu, pattern="^main_menu$"))
        app.add_handler(CallbackQueryHandler(menu_h.handle_help_cb, pattern="^help$"))
        app.add_handler(CallbackQueryHandler(settings_h.handle_settings, pattern="^settings$"))
        app.add_handler(CallbackQueryHandler(settings_h.handle_gender_select, pattern="^gender_"))
        app.add_handler(CallbackQueryHandler(settings_h.handle_language_select, pattern="^lang_"))
        app.add_handler(CallbackQueryHandler(report_h.handle_report, pattern="^report_user$"))
        app.add_handler(CallbackQueryHandler(report_h.handle_report_reason, pattern="^report_reason_"))
        app.add_handler(CallbackQueryHandler(chat_h.handle_rating, pattern="^rate_"))
        app.add_handler(CallbackQueryHandler(admin_h.handle_admin_cb, pattern="^admin_"))

        # Message relay (must be last)
        app.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND,
            chat_h.handle_message
        ))

        # Error handler
        app.add_error_handler(self._error_handler)

    async def _error_handler(self, update: object, context) -> None:
        """Handle errors in the bot."""
        logger.error("Exception while handling update:", exc_info=context.error)

    async def run_webhook(self) -> None:
        """Run bot in webhook mode (production)."""
        webhook_url = f"{self.config.WEBHOOK_URL}/webhook/{self.config.BOT_TOKEN}"

        # Setup aiohttp web app for health check + webhook
        self.web_app = web.Application()
        self.web_app.router.add_get("/health", self._health_check)
        self.web_app.router.add_get("/", self._health_check)
        self.web_app.router.add_post(f"/webhook/{self.config.BOT_TOKEN}",self.handle_webhook)

        await self.app.initialize()
        await self.app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
        )

        # Start scheduler
        asyncio.create_task(self.scheduler.run())

        runner = web.AppRunner(self.web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.config.PORT)
        await site.start()

        logger.info(f"Webhook running on port {self.config.PORT}")
        logger.info(f"Webhook URL: {webhook_url}")

        # Handle incoming webhook updates
        async with self.app:
            await self.app.start()
            # Keep alive
            while True:
                await asyncio.sleep(3600)

    async def handle_webhook(self, request: web.Request):
        data = await request.json()
        update = Update.de_json(data, self.app.bot)

    await self.app.process_update(update)
    return web.Response(text="OK")

    async def run_polling(self) -> None:
        """Run bot in polling mode (development)."""
        logger.info("Starting bot in polling mode...")

        async with self.app:
            await self.app.initialize()
            asyncio.create_task(self.scheduler.run())
            await self.app.start()
            await self.app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
            logger.info("Bot is running in polling mode. Press Ctrl+C to stop.")

            # Wait for stop signal
            stop_event = asyncio.Event()

            def signal_handler(sig, frame):
                logger.info("Shutdown signal received.")
                asyncio.get_event_loop().call_soon_threadsafe(stop_event.set)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            await stop_event.wait()
            await self.app.updater.stop()
            await self.app.stop()

    async def _health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint for Render."""
        return web.json_response({
            "status": "ok",
            "bot": "FunChatBot",
            "version": "1.0.0",
        })


async def main() -> None:
    """Main entry point."""
    bot = FunChatBot()
    await bot.initialize()

    if os.getenv("WEBHOOK_URL"):
        await bot.run_webhook()
    else:
        await bot.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
