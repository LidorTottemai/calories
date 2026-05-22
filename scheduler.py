from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
import database


def build_scheduler(application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        send_daily_summary,
        CronTrigger(hour=23, minute=59, timezone=config.TIMEZONE),
        args=[application],
        id="daily_summary",
        replace_existing=True,
    )
    return scheduler


async def send_daily_summary(application) -> None:
    now = datetime.now(config.TIMEZONE)
    today = now.strftime("%Y-%m-%d")
    day_of_week = now.weekday()
    goals = database.get_goals_for_day(day_of_week)
    totals = database.get_day_totals(today)

    date_display = now.strftime("%d/%m/%Y")
    day_name = config.WEEKDAY_DISPLAY[day_of_week]

    cal_consumed = totals["total_calories"]
    prot_consumed = totals["total_protein_g"]

    if cal_consumed == 0:
        text = (
            f"📊 סיכום יומי — {day_name}, {date_display}\n\n"
            "לא נרשמו ארוחות היום."
        )
    else:
        cal_status = "✅" if cal_consumed <= goals["calories"] else "❌"
        prot_status = "✅" if prot_consumed >= goals["protein"] else "❌"
        fiber_count = totals["fiber_meal_count"]
        fiber_str = ("🌿 " * fiber_count).strip() if fiber_count > 0 else "—"

        text = (
            f"📊 סיכום יומי — {day_name}, {date_display}\n\n"
            f"🔥 קלוריות: {cal_consumed:,} / {goals['calories']:,} {cal_status}\n"
            f"💪 חלבון: {prot_consumed:.1f} / {goals['protein']:.0f} גר' {prot_status}\n"
            f"🌾 פחמימות: {totals['total_carbs_g']:.1f} גר'\n"
            f"🌿 ארוחות עם סיבים: {fiber_str}"
        )

    await application.bot.send_message(chat_id=config.AUTHORIZED_USER_ID, text=text)
