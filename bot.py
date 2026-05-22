from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

import config
import database
from handlers import (
    start_handler,
    help_handler,
    setgoal_handler,
    goals_handler,
    today_handler,
    meal_handler,
)
from scheduler import build_scheduler


async def post_init(application) -> None:
    scheduler = build_scheduler(application)
    scheduler.start()
    application.bot_data["scheduler"] = scheduler


async def post_shutdown(application) -> None:
    scheduler = application.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


def main() -> None:
    database.init_db()

    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("setgoal", setgoal_handler))
    application.add_handler(CommandHandler("goals", goals_handler))
    application.add_handler(CommandHandler("today", today_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, meal_handler)
    )

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
