from functools import wraps
from datetime import datetime

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, ConversationHandler

import config
import database
import nutrition

SETUP_CALORIES = 0
SETUP_PROTEIN = 1


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
        "/setup — הגדרת יעדים מודרכת (מומלץ להתחלה)\n"
        "/setgoal <יום> <קלוריות> [חלבון] — שינוי יעד ליום מסוים\n"
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
        "/setup — הגדרת יעדים מודרכת לכל ימי השבוע\n"
        "/setgoal <יום> <קלוריות> [חלבון גר'] — שינוי יעד ליום בודד\n"
        "  לדוגמה: /setgoal א 1800 150\n\n"
        "/goals — הצגת כל היעדים\n"
        "/today — סיכום היום\n"
        "/start — הודעת פתיחה"
    )


@authorized_only
async def setgoal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 2 or len(args) > 3:
        await update.message.reply_text(
            "שימוש: /setgoal <יום> <קלוריות> [חלבון גר']\n"
            "ימים: א ב ג ד ה ו ש\n"
            "לדוגמה: /setgoal א 1800 150"
        )
        return

    day_str = args[0].strip()
    day_of_week = config.HEBREW_DAY_MAP.get(day_str) or config.ENGLISH_DAY_MAP.get(day_str.lower())

    if day_of_week is None:
        await update.message.reply_text("יום לא מזוהה. השתמש באחד מ: א ב ג ד ה ו ש")
        return

    try:
        calories = int(args[1])
    except ValueError:
        await update.message.reply_text("מספר קלוריות לא תקין.")
        return

    if not (500 <= calories <= 5000):
        await update.message.reply_text("יעד קלוריות חייב להיות בין 500 ל-5000.")
        return

    protein = None
    if len(args) == 3:
        try:
            protein = float(args[2])
        except ValueError:
            await update.message.reply_text("מספר חלבון לא תקין.")
            return
        if not (10 <= protein <= 500):
            await update.message.reply_text("יעד חלבון חייב להיות בין 10 ל-500 גר'.")
            return

    database.set_goal(day_of_week, calories=calories, protein=protein)
    day_name = config.WEEKDAY_DISPLAY[day_of_week]

    if protein is not None:
        await update.message.reply_text(
            f"✅ יום {day_name} עודכן:\n"
            f"🔥 קלוריות: {calories:,}\n"
            f"💪 חלבון: {protein:.0f} גר'"
        )
    else:
        await update.message.reply_text(
            f"✅ יעד קלוריות ליום {day_name} עודכן ל-{calories:,}."
        )


@authorized_only
async def goals_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    all_goals = database.get_all_goals()
    lines = ["📋 יעדים יומיים:\n"]
    for day in config.DAYS_ORDER:
        g = all_goals.get(day, {"calories": 2000, "protein": 150})
        lines.append(f"{config.WEEKDAY_DISPLAY[day]}: 🔥 {g['calories']:,} קל'  💪 {g['protein']:.0f} גר' חלבון")
    await update.message.reply_text("\n".join(lines))


@authorized_only
async def today_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = database.get_today_date_str()
    now = datetime.now(config.TIMEZONE)
    day_of_week = now.weekday()
    goals = database.get_goals_for_day(day_of_week)
    totals = database.get_day_totals(today)

    cal_consumed = totals["total_calories"]
    cal_remaining = goals["calories"] - cal_consumed
    cal_remaining_str = f"{cal_remaining:,}" if cal_remaining >= 0 else f"-{abs(cal_remaining):,}"
    cal_status = "✅" if cal_remaining >= 0 else "❌"

    prot_consumed = totals["total_protein_g"]
    prot_remaining = goals["protein"] - prot_consumed
    prot_remaining_str = f"{prot_remaining:.1f}" if prot_remaining >= 0 else f"-{abs(prot_remaining):.1f}"
    prot_status = "✅" if prot_remaining >= 0 else "❌"

    fiber_str = "🌿 " * totals["fiber_meal_count"] if totals["fiber_meal_count"] > 0 else "אין"

    date_display = now.strftime("%d/%m/%Y")
    day_name = config.WEEKDAY_DISPLAY[day_of_week]

    await update.message.reply_text(
        f"📊 סיכום היום — {day_name}, {date_display}\n\n"
        f"🔥 קלוריות: {cal_consumed:,} / {goals['calories']:,} {cal_status}\n"
        f"   נותרו: {cal_remaining_str} קל'\n\n"
        f"💪 חלבון: {prot_consumed:.1f} / {goals['protein']:.0f} גר' {prot_status}\n"
        f"   נותרו: {prot_remaining_str} גר'\n\n"
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
        await update.message.reply_text("שגיאה בחישוב הערכים, נסה שוב בעוד רגע.")
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
    goals = database.get_goals_for_day(day_of_week)
    totals = database.get_day_totals(today)

    cal_remaining = goals["calories"] - totals["total_calories"]
    cal_remaining_str = f"{cal_remaining:,}" if cal_remaining >= 0 else f"-{abs(cal_remaining):,}"

    prot_remaining = goals["protein"] - totals["total_protein_g"]
    prot_remaining_str = f"{prot_remaining:.1f}" if prot_remaining >= 0 else f"-{abs(prot_remaining):.1f}"

    fiber_line = "\n🌿" if result.has_fiber else ""

    await update.message.reply_text(
        f"🍽 {result.raw_description}"
        f"{fiber_line}\n\n"
        f"🔥 קלוריות: {result.calories:,}\n"
        f"💪 חלבון: {result.protein_g:.1f} גר'\n"
        f"🌾 פחמימות: {result.carbs_g:.1f} גר'\n\n"
        f"—\n"
        f"קלוריות — נותרו: {cal_remaining_str} מתוך {goals['calories']:,}\n"
        f"חלבון — נותרו: {prot_remaining_str} גר' מתוך {goals['protein']:.0f}"
    )


def _ask_calories_prompt(day_idx: int) -> str:
    day_name = config.WEEKDAY_DISPLAY[config.DAYS_ORDER[day_idx]]
    return f"🔥 כמה קלוריות ביום {day_name}?"


def _ask_protein_prompt(day_idx: int) -> str:
    day_name = config.WEEKDAY_DISPLAY[config.DAYS_ORDER[day_idx]]
    return f"💪 כמה גרם חלבון ביום {day_name}?"


@authorized_only
async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["setup_idx"] = 0
    await update.message.reply_text(
        "בוא נגדיר את יעדי הקלוריות והחלבון לכל ימי השבוע 📋\n"
        "שלח /cancel בכל שלב לביטול.\n\n"
        + _ask_calories_prompt(0)
    )
    return SETUP_CALORIES


@authorized_only
async def setup_calories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    idx = context.user_data.get("setup_idx", 0)

    try:
        calories = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("נא להזין מספר בלבד.\n" + _ask_calories_prompt(idx))
        return SETUP_CALORIES

    if not (500 <= calories <= 5000):
        await update.message.reply_text(
            "יעד חייב להיות בין 500 ל-5000.\n" + _ask_calories_prompt(idx)
        )
        return SETUP_CALORIES

    context.user_data["setup_calories_tmp"] = calories
    await update.message.reply_text(_ask_protein_prompt(idx))
    return SETUP_PROTEIN


@authorized_only
async def setup_protein(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    idx = context.user_data.get("setup_idx", 0)
    day_of_week = config.DAYS_ORDER[idx]

    try:
        protein = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("נא להזין מספר בלבד.\n" + _ask_protein_prompt(idx))
        return SETUP_PROTEIN

    if not (10 <= protein <= 500):
        await update.message.reply_text(
            "יעד חלבון חייב להיות בין 10 ל-500 גר'.\n" + _ask_protein_prompt(idx)
        )
        return SETUP_PROTEIN

    calories = context.user_data.pop("setup_calories_tmp")
    database.set_goal(day_of_week, calories=calories, protein=protein)

    idx += 1
    context.user_data["setup_idx"] = idx

    if idx < len(config.DAYS_ORDER):
        await update.message.reply_text("✅ שמור!\n\n" + _ask_calories_prompt(idx))
        return SETUP_CALORIES

    all_goals = database.get_all_goals()
    lines = ["✅ כל היעדים הוגדרו!\n\n📋 סיכום:\n"]
    for day in config.DAYS_ORDER:
        g = all_goals.get(day, {"calories": 2000, "protein": 150})
        lines.append(f"{config.WEEKDAY_DISPLAY[day]}: 🔥 {g['calories']:,} קל'  💪 {g['protein']:.0f} גר'")
    await update.message.reply_text("\n".join(lines))
    return ConversationHandler.END


async def setup_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("ביטלת את ההגדרה. היעדים שהוגדרו עד כה נשמרו.")
    return ConversationHandler.END
