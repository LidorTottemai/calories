from functools import wraps
from datetime import datetime

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

import config
import database
import nutrition


def authorized_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user and update.effective_user.id != config.AUTHORIZED_USER_ID:
            return
        return await func(update, context)
    return wrapper


@authorized_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ברוך הבא לבוט מעקב הקלוריות! 🥗\n\n"
        "שלח לי מה אכלת ואחשב עבורך קלוריות, חלבון, פחמימות וסיבים.\n\n"
        "פקודות:\n"
        "/setgoal <יום> <קלוריות> — הגדרת יעד יומי\n"
        "  לדוגמה: /setgoal א 1800\n"
        "/goals — הצגת כל היעדים היומיים\n"
        "/today — סיכום היום הנוכחי\n"
        "/help — עזרה"
    )


@authorized_only
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 עזרה\n\n"
        "כדי לרשום ארוחה, פשוט שלח מה אכלת:\n"
        "  'אכלתי שתי ביצים עם טוסט'\n"
        "  '100 גרם חזה עוף עם אורז'\n\n"
        "פקודות:\n"
        "/setgoal <יום> <קלוריות>\n"
        "  ימים: א ב ג ד ה ו ש\n"
        "  לדוגמה: /setgoal א 1800\n\n"
        "/goals — הצגת כל היעדים\n"
        "/today — סיכום היום\n"
        "/start — הודעת פתיחה"
    )


@authorized_only
async def setgoal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "שימוש: /setgoal <יום> <קלוריות>\n"
            "ימים: א ב ג ד ה ו ש\n"
            "לדוגמה: /setgoal א 1800"
        )
        return

    day_str = args[0].strip()
    day_of_week = config.HEBREW_DAY_MAP.get(day_str) or config.ENGLISH_DAY_MAP.get(day_str.lower())

    if day_of_week is None:
        await update.message.reply_text(
            "יום לא מזוהה. השתמש באחד מ: א ב ג ד ה ו ש"
        )
        return

    try:
        calories = int(args[1])
    except ValueError:
        await update.message.reply_text("מספר קלוריות לא תקין.")
        return

    if not (500 <= calories <= 5000):
        await update.message.reply_text("יעד קלוריות חייב להיות בין 500 ל-5000.")
        return

    database.set_goal(day_of_week, calories)
    day_name = config.WEEKDAY_DISPLAY[day_of_week]
    await update.message.reply_text(f"✅ יעד יום {day_name} עודכן ל-{calories:,} קלוריות.")


@authorized_only
async def goals_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    all_goals = database.get_all_goals()
    lines = ["📋 יעדי קלוריות יומיים:\n"]
    for day in config.DAYS_ORDER:
        goal = all_goals.get(day, 2000)
        lines.append(f"{config.WEEKDAY_DISPLAY[day]}: {goal:,} קלוריות")
    await update.message.reply_text("\n".join(lines))


@authorized_only
async def today_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = database.get_today_date_str()
    now = datetime.now(config.TIMEZONE)
    day_of_week = now.weekday()
    goal = database.get_goal(day_of_week)
    totals = database.get_day_totals(today)

    consumed = totals["total_calories"]
    remaining = goal - consumed
    remaining_str = f"{remaining:,}" if remaining >= 0 else f"-{abs(remaining):,}"
    status = "✅" if remaining >= 0 else "❌"

    fiber_str = "🌿 " * totals["fiber_meal_count"] if totals["fiber_meal_count"] > 0 else "אין"

    date_display = now.strftime("%d/%m/%Y")
    day_name = config.WEEKDAY_DISPLAY[day_of_week]

    await update.message.reply_text(
        f"📊 סיכום היום — {day_name}, {date_display}\n\n"
        f"🎯 יעד: {goal:,} קלוריות\n"
        f"🔥 נצרך: {consumed:,} קלוריות {status}\n"
        f"נותרו: {remaining_str} קלוריות\n\n"
        f"💪 חלבון: {totals['total_protein_g']:.1f} גר'\n"
        f"🌾 פחמימות: {totals['total_carbs_g']:.1f} גר'\n"
        f"🌿 ארוחות עם סיבים: {fiber_str}"
    )


@authorized_only
async def meal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action(ChatAction.TYPING)

    user_text = update.message.text.strip()
    today = database.get_today_date_str()
    now = datetime.now(config.TIMEZONE)

    try:
        result = await nutrition.analyze_meal(user_text)
    except ValueError:
        await update.message.reply_text(
            "לא הצלחתי לזהות את האוכל. נסה לתאר בצורה קצת יותר מפורטת 🙏"
        )
        return
    except Exception:
        await update.message.reply_text(
            "שגיאה בחישוב הערכים, נסה שוב בעוד רגע."
        )
        return

    database.log_meal(
        log_date=today,
        description=user_text,
        calories=result.calories,
        protein_g=result.protein_g,
        carbs_g=result.carbs_g,
        has_fiber=result.has_fiber,
        created_at=now.isoformat(),
    )

    day_of_week = now.weekday()
    goal = database.get_goal(day_of_week)
    totals = database.get_day_totals(today)

    remaining = goal - totals["total_calories"]
    remaining_str = f"{remaining:,}" if remaining >= 0 else f"-{abs(remaining):,}"

    fiber_line = "\n🌿" if result.has_fiber else ""

    await update.message.reply_text(
        f"🍽 {result.raw_description}"
        f"{fiber_line}\n\n"
        f"🔥 קלוריות: {result.calories:,}\n"
        f"💪 חלבון: {result.protein_g:.1f} גר'\n"
        f"🌾 פחמימות: {result.carbs_g:.1f} גר'\n\n"
        f"—\n"
        f"יומי עד כה: {totals['total_calories']:,} קלוריות\n"
        f"נותרו: {remaining_str} מתוך {goal:,}"
    )
