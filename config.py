import os
import pytz
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val

TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID: int = int(_require("TELEGRAM_AUTHORIZED_USER_ID"))
OPENAI_API_KEY: str = _require("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TIMEZONE = pytz.timezone(os.getenv("TZ", "Asia/Jerusalem"))
DB_PATH: str = os.getenv("DB_PATH", "calories.db")

# Hebrew letter -> Python weekday() int (0=Monday ... 6=Sunday)
HEBREW_DAY_MAP: dict[str, int] = {
    "א": 6,  # Sunday
    "ב": 0,  # Monday
    "ג": 1,  # Tuesday
    "ד": 2,  # Wednesday
    "ה": 3,  # Thursday
    "ו": 4,  # Friday
    "ש": 5,  # Saturday
}

ENGLISH_DAY_MAP: dict[str, int] = {
    "sunday": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
}

# weekday int -> Hebrew display name, ordered Sunday first
WEEKDAY_DISPLAY: dict[int, str] = {
    6: "ראשון (א)",
    0: "שני (ב)",
    1: "שלישי (ג)",
    2: "רביעי (ד)",
    3: "חמישי (ה)",
    4: "שישי (ו)",
    5: "שבת (ש)",
}

# Ordered weekday ints from Sunday to Saturday for display purposes
DAYS_ORDER = [6, 0, 1, 2, 3, 4, 5]
