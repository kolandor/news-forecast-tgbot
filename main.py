import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database as db
import handlers
import scheduler_service

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def seed_default_schedule_if_empty():
    schedules = db.get_all_schedules()
    if not schedules:
        logger.info("No schedules found. Seeding default schedule.")
        db.add_schedule(
            time_utc="08:00",
            countries="uk,fr,de",
            topics="top_headlines,economy",
            time_horizon="24h",
            depth="standard",
            language="en",
            title="Morning Briefing"
        )

async def post_init(application: Application):
    """
    Initializes and starts the scheduler after the bot's event loop is running.
    """
    scheduler = AsyncIOScheduler()
    # Attach to application.bot_data to ensure persistence (avoid GC) and avoid AttributeError
    application.bot_data["scheduler"] = scheduler
    
    scheduler_service.setup_scheduler(application, scheduler)
    scheduler.start()
    logger.info("APScheduler started via post_init hook.")

def main():
    # 1. Initialize Database
    db.init_db()
    seed_default_schedule_if_empty()

    # 2. Build Telegram Application
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables.")
        return

    # post_init is used to start the scheduler inside the asyncio loop
    application = ApplicationBuilder().token(config.BOT_TOKEN).post_init(post_init).build()

    # 3. Register Handlers
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.start))
    application.add_handler(CommandHandler("subscribe", handlers.subscribe))
    application.add_handler(CommandHandler("unsubscribe", handlers.unsubscribe))
    application.add_handler(CommandHandler("status", handlers.status))
    
    # Admin Handlers
    application.add_handler(CommandHandler("schedule_list", handlers.schedule_list))
    application.add_handler(CommandHandler("subscribers_count", handlers.subscribers_count))
    application.add_handler(CommandHandler("run_now", handlers.run_now))

    # 5. Run Bot
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
