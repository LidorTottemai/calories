from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import database
from handlers import (
    ALL_BUTTONS,
    BTN_MEAL, BTN_TODAY, BTN_SETUP_WEEKLY, BTN_SETUP_DAILY,
    SETUP_CALORIES, SETUP_PROTEIN,
    SELECT_DAY, ENTER_CAL, ENTER_PROT,
    start_handler,
    help_handler,
    setgoal_handler,
    goals_handler,
    today_handler,
    meal_prompt_handler,
    meal_handler,
    setup_start,
    setup_calories,
    setup_protein,
    setup_cancel,
    daily_goal_start,
    daily_goal_day_cb,
    daily_goal_cal_input,
    daily_goal_prot_input,
    daily_goal_cancel,
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

    setup_conv = ConversationHandler(
        entry_points=[
            CommandHandler("setup", setup_start),
            MessageHandler(filters.Text([BTN_SETUP_WEEKLY]), setup_start),
        ],
        states={
            SETUP_CALORIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_calories)],
            SETUP_PROTEIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_protein)],
        },
        fallbacks=[CommandHandler("cancel", setup_cancel)],
    )

    daily_goal_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Text([BTN_SETUP_DAILY]), daily_goal_start),
        ],
        states={
            SELECT_DAY: [CallbackQueryHandler(daily_goal_day_cb, pattern=r"^day_\d$")],
            ENTER_CAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, daily_goal_cal_input)],
            ENTER_PROT: [MessageHandler(filters.TEXT & ~filters.COMMAND, daily_goal_prot_input)],
        },
        fallbacks=[CommandHandler("cancel", daily_goal_cancel)],
    )

    # ConversationHandlers first — they intercept messages during active flows
    application.add_handler(setup_conv)
    application.add_handler(daily_goal_conv)

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("setgoal", setgoal_handler))
    application.add_handler(CommandHandler("goals", goals_handler))
    application.add_handler(CommandHandler("today", today_handler))

    # Keyboard buttons
    application.add_handler(MessageHandler(filters.Text([BTN_TODAY]), today_handler))
    application.add_handler(MessageHandler(filters.Text([BTN_MEAL]), meal_prompt_handler))

    # Catch-all: any text that isn't a command or button → meal
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Text(ALL_BUTTONS), meal_handler)
    )

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
