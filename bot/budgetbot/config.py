"""Configuration: budget figures, classification tables and runtime settings.

Budget numbers are the ones approved by the household in November 2026.
Secrets are read from the environment only - never stored here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Budget, approved 2026-11-14
# --------------------------------------------------------------------------

#: Monthly ceiling per variable-spending bucket, in shekels.
VARIABLE_BUDGETS: dict[str, int] = {
    "סופר ומכולת": 3600,
    "רכב": 2000,
    "אוכל בחוץ": 2000,
    "העברות ושונות": 800,
    "בלת״ם ואירועים": 600,
    "פארמה": 500,
    "ביגוד והנעלה": 500,
}
VARIABLE_TOTAL = sum(VARIABLE_BUDGETS.values())  # 10,000

#: Fixed side, for the digest only - the bot does not alert on fixed charges.
FIXED_BUDGET = 21225  # 15,500 + Tiferet 4,300 + afternoon programme 1,075 + Yahad 350
MONTHLY_INCOME = 36000

# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

#: Merchants the household counts as fixed commitments even though RiseUp
#: files them as variable. Matched after whitespace normalisation.
FIXED_OVERRIDES: frozenset[str] = frozenset({
    "תפארת האחוזה",
    "תפארת האחוזה)ע",
    "העשרת צהרים בעמ הוק",
    "יח”ד מודיעין)ע",
    'פלאפון תקשורת בע"מ.',
    'קופ"ח מאוחדת-בימ"ק מ',
    "משרד התחבורה - רשיונות רכב",
})

#: Aggregated credit-card bills landing in the checking account. Counting these
#: alongside the individual card transactions would double every card purchase.
CARD_SETTLEMENTS: frozenset[str] = frozenset({
    "מסטרקרד",
    "ישראכרט בע”מ",
    'ישראכרט בע"מ',
    "מקס איט פיננסי",
})

#: RiseUp categoryLabel -> budget bucket.
CATEGORY_TO_BUCKET: dict[str, str] = {
    "כלכלה": "סופר ומכולת",
    "רכב": "רכב",
    "אוכל בחוץ": "אוכל בחוץ",
    "אחר": "העברות ושונות",
    "פארמה": "פארמה",
    "ביגוד והנעלה": "ביגוד והנעלה",
}

#: Anything uncategorised lands here, which is what the contingency line is for.
DEFAULT_BUCKET = "בלת״ם ואירועים"

#: Deposits, not consumption - excluded from the spending budget entirely.
IGNORED_CATEGORIES: frozenset[str] = frozenset({
    "חיסכון",
    "__saving-hidden-category__",
})

# --------------------------------------------------------------------------
# Runtime
# --------------------------------------------------------------------------

TIMEZONE = "Asia/Jerusalem"
RISEUP_BASE = "https://input.riseup.co.il"
TELEGRAM_BASE = "https://api.telegram.org"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_time(name: str, default: str) -> tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute), falling back to the default."""
    raw = os.environ.get(name, "").strip() or default
    try:
        hh, mm = raw.split(":")
        h, m = int(hh), int(mm)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except ValueError:
        pass
    hh, mm = default.split(":")
    return int(hh), int(mm)


@dataclass(frozen=True)
class Settings:
    riseup_pat: str = ""
    telegram_token: str = ""
    chat_ids: tuple[str, ...] = ()
    db_path: str = "/data/budget.db"
    poll_seconds: int = 1800
    quiet_start: tuple[int, int] = (22, 30)   # no messages from here ...
    quiet_end: tuple[int, int] = (7, 30)      # ... until here
    digest_at: tuple[int, int] = (20, 30)
    max_individual_alerts: int = 3
    pace_warn_ratio: float = 1.15
    http_timeout: int = 30
    retries: int = 3
    commands_enabled: bool = True
    persona: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.riseup_pat and self.telegram_token and self.chat_ids)

    def missing(self) -> list[str]:
        gaps = []
        if not self.riseup_pat:
            gaps.append("RISEUP_PAT")
        if not self.telegram_token:
            gaps.append("TELEGRAM_BOT_TOKEN")
        if not self.chat_ids:
            gaps.append("TELEGRAM_CHAT_IDS")
        return gaps


def load_settings() -> Settings:
    ids = tuple(
        part.strip()
        for part in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",")
        if part.strip()
    )
    return Settings(
        riseup_pat=os.environ.get("RISEUP_PAT", "").strip(),
        telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
        chat_ids=ids,
        db_path=os.environ.get("DB_PATH", "/data/budget.db").strip() or "/data/budget.db",
        poll_seconds=_env_int("POLL_SECONDS", 1800),
        quiet_start=_env_time("QUIET_START", "22:30"),
        quiet_end=_env_time("QUIET_END", "07:30"),
        digest_at=_env_time("DIGEST_AT", "20:30"),
        max_individual_alerts=_env_int("MAX_INDIVIDUAL_ALERTS", 3),
        commands_enabled=os.environ.get("COMMANDS_ENABLED", "1").strip() != "0",
        persona=os.environ.get("PERSONA", "1").strip() != "0",
    )
