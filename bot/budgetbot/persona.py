"""מוסלם הגובה - the voice of the bot.

Four registers keyed to how badly the budget is doing. Lines are picked
deterministically from the transaction id, so the same charge always draws the
same line (stable tests, and a message that does not change if it is re-sent)
while different charges vary.

Comic debt-collector register: warm, dramatic, put-upon. Moslem is exasperated
by the budget, never by the people. No real threats, no insults.
"""
from __future__ import annotations

import hashlib

OK, WARN, OVER, BLOWN = "ok", "warn", "over", "blown"

LINES: dict[str, tuple[str, ...]] = {
    OK: (
        "יפה. ככה אני אוהב. תמשיכו ככה ואני אפילו לא צריך להתקשר.",
        "בסדר גמור. אני רושם, אבל בסדר גמור.",
        "שקט אצלי. אני שותה קפה, הכול טוב.",
        "אהלן. זה בתוך התקציב, תיהנו, זה מגיע לכם.",
        "מצוין. אתם מהלקוחות הטובים שלי, באמת.",
        "חלק. ככה זה צריך להיראות כל החודש.",
        "אין בעיה. אני כאן בשקט, לא מפריע לאף אחד.",
    ),
    WARN: (
        "הלו הלו נשמות, בואו נרגיע לפני שאני משתגע.",
        "אחי. אני מדבר יפה עכשיו. יפה.",
        "תשמעו, אני אדם סבלני. עד גבול מסוים.",
        "אני לא כועס. אני מאוכזב. בינתיים.",
        "כפרה עליכם, תאטו קצת. בשבילי.",
        "שימו לב לקצב. כי אני שם לב לקצב.",
        "עוד לא קרה כלום. אבל מתחיל לקרות משהו.",
        "אני מסתכל על המספר הזה ולא אוהב אותו. פשוט לא אוהב.",
    ),
    OVER: (
        "נגמר. הקטגוריה הזאת נגמרה. סגרנו.",
        "חרגתם. אני לא אומר את זה בכיף, אני אומר את זה כעובדה.",
        "יא חביבי, מה זה הדבר הזה? מה זה?",
        "אני רושם הכל. הכל רשום אצלי בפנקס.",
        "זה לא אישי. זה עסקים.",
        "אמרתי יפה, אמרתי בנחת. עכשיו אני אומר: עצרו.",
        "תסבירו לי. אני מחכה. יש לי כל הזמן שבעולם.",
        "הגזמתם. ואני אומר את זה באהבה.",
    ),
    BLOWN: (
        "אתם צוחקים עליי? תגידו לי שאתם צוחקים עליי.",
        "אני צריך לשבת רגע. באמת. תנו לי דקה.",
        "לקחתי אוויר. ספרתי עד עשר. עדיין לא מאמין.",
        "המספר הזה והתקציב הזה אפילו לא מדברים אותה שפה.",
        "אני לוקח את זה אישית עכשיו. קצת.",
        "מישהו צריך להסביר לי מה קרה פה. ברצינות.",
    ),
}

DIGEST_OPENERS: dict[str, tuple[str, ...]] = {
    OK: (
        "סוף יום, בואו נעשה חשבון קטן. בכיף.",
        "ערב טוב. היום הייתם בסדר, אז גם אני בסדר.",
        "סוגר את הפנקס. יום שקט, אני אוהב ימים כאלה.",
    ),
    WARN: (
        "סוף יום. בואו נדבר רגע.",
        "ערב טוב. יש לי כמה הערות קטנות.",
        "סוגר את הפנקס, ויש בו דברים שלא מצאו חן בעיניי.",
    ),
    OVER: (
        "סוף יום. שבו. אנחנו צריכים לדבר.",
        "ערב טוב. אני אקצר: לא טוב.",
        "פתחתי את הפנקס ומיד סגרתי אותו. בואו נדבר מחר.",
    ),
    BLOWN: (
        "אני אפילו לא יודע איך לפתוח את זה. שבו.",
        "סוף יום, ואני עוד מתאושש. בואו נעבור על זה ביחד.",
    ),
}

BOOT = "הגעתי. מהיום אני סופר. כל שקל, כל עסקה, בלי יוצא מן הכלל."

SIGNOFF = "— מוסלם"


def tone(spent: float, budget: float, expected: float, warn_ratio: float = 1.15) -> str:
    """Pick the register from the same figures the pace marker uses."""
    if budget <= 0:
        return OK
    if spent > budget * 1.5:
        return BLOWN
    if spent > budget:
        return OVER
    if expected > 0 and spent > expected * warn_ratio:
        return WARN
    return OK


def pick(bank: tuple[str, ...], key: str) -> str:
    """Deterministic choice, so a given key always yields the same line."""
    if not bank:
        return ""
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return bank[int(digest[:8], 16) % len(bank)]


def say(state: str, key: str) -> str:
    return pick(LINES.get(state, LINES[OK]), key)


def digest_opener(state: str, key: str) -> str:
    return pick(DIGEST_OPENERS.get(state, DIGEST_OPENERS[OK]), key)


def quote(line: str) -> str:
    """Render one of Moslem's lines as the closing block of a message."""
    return f"💬 {line}\n{SIGNOFF}" if line else ""
