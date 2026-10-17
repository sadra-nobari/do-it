import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import BOT_TOKEN, DATABASE_PATH, PROXY_URL
from bot.database.db import init_db
from bot.handlers import (
    callback_query_handler,
    help_command,
    list_command,
    message_handler,
    start_command,
)
from bot.scheduler.job_manager import restore_pending_jobs

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("do-it-bot")


async def post_init(application) -> None:
    """Runs after application is initialized to restore pending reminders."""
    logger.info("Initializing SQLite database...")
    await init_db(DATABASE_PATH)
    logger.info("Restoring pending reminders from database...")
    await restore_pending_jobs(application)
    logger.info("Bot is ready and listening for reminders!")


def main() -> None:
    """Main entrypoint for Do It Telegram Bot."""
    if not BOT_TOKEN:
        print("\n" + "=" * 60)
        print("❌ خطا: توکن ربات تلگرام (TELEGRAM_BOT_TOKEN) تنظیم نشده است!")
        print("لطفاً توکن ربات خود را در فایل .env یا به صورت متغیر محیطی وارد کنید.")
        print("مثال:")
        print("TELEGRAM_BOT_TOKEN=your_bot_token_here")
        print("=" * 60 + "\n")
        sys.exit(1)

    builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init)

    if PROXY_URL:
        logger.info("Using proxy: %s", PROXY_URL)
        builder = builder.proxy(PROXY_URL).get_updates_proxy(PROXY_URL)

    application = builder.build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Starting Do It Bot polling...")
    application.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
