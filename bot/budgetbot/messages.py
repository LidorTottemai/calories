"""Hebrew message formatting and the pacing arithmetic behind it."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from . import persona
from .classify import Txn
from .config import FIXED_BUDGET, MONTHLY_INCOME, VARIABLE_BUDGETS, VARIABLE_TOTAL

ON_TRACK, AHEAD, OVER = "✅", "⚠️", "🔴"


def nis(value: float) -> str:
    return f"{round(value):,}"


def days_left(today: date) -> int:
    """Days remaining in the month, counting today as still spendable."""
    return calendar.monthrange(today.year, today.month)[1] - today.day + 1


def _elapsed_fraction(today: date) -> float:
    total = calendar.monthrange(today.year, today.month)[1]
    return today.day / total


@dataclass(frozen=True)
class Pace:
    spent: float
    budget: float
    today: date

    @property
    def left(self) -> float:
        return self.budget - self.spent

    @property
    def expected(self) -> float:
        """What an even spend rate would have reached by today."""
        return self.budget * _elapsed_fraction(self.today)

    @property
    def projection(self) -> float:
        """Month-end total if the current rate holds."""
        frac = _elapsed_fraction(self.today)
        return self.spent / frac if frac > 0 else self.spent

    def marker(self, warn_ratio: float = 1.15) -> str:
        if self.spent > self.budget:
            return OVER
        if self.expected > 0 and self.spent > self.expected * warn_ratio:
            return AHEAD
        return ON_TRACK

    def tone(self, warn_ratio: float = 1.15) -> str:
        return persona.tone(self.spent, self.budget, self.expected, warn_ratio)


def _with_voice(lines: list[str], state: str, key: str, speak: bool) -> str:
    text = "\n".join(lines)
    if not speak:
        return text
    return text + "\n\n" + persona.quote(persona.say(state, key))


def transaction_alert(txn: Txn, spent: float, today: date,
                      warn_ratio: float = 1.15, speak: bool = True) -> str:
    budget = VARIABLE_BUDGETS.get(txn.bucket, 0)
    pace = Pace(spent, budget, today)
    left = pace.left
    d = days_left(today)

    lines = [
        "🧾 עסקה חדשה",
        f"{txn.business} · {nis(txn.amount)} ₪",
        f"קטגוריה: {txn.bucket}",
        "",
        f"עד כה החודש: {nis(spent)} מתוך {nis(budget)} ₪",
    ]
    if left >= 0:
        lines.append(f"נותרו {nis(left)} ₪ · {d} ימים לסוף החודש")
    else:
        lines.append(f"חריגה של {nis(-left)} ₪ · {d} ימים לסוף החודש")

    mark = pace.marker(warn_ratio)
    if mark == OVER:
        lines.append(f"{OVER} הקטגוריה הזאת נגמרה")
    elif mark == AHEAD:
        lines.append(f"{AHEAD} מקדימים את הקצב — לפי התאריך היו אמורים להיות ב-{nis(pace.expected)} ₪")

    return _with_voice(lines, pace.tone(warn_ratio), txn.id, speak)


def batched_alert(items: list[tuple[Txn, float]], today: date,
                  warn_ratio: float = 1.15, speak: bool = True) -> str:
    """One message for a burst, so a shopping run does not fire five pings."""
    total = sum(t.amount for t, _ in items)
    lines = [f"🧾 {len(items)} עסקאות חדשות · {nis(total)} ₪ ביחד", ""]
    worst = persona.OK
    order = [persona.OK, persona.WARN, persona.OVER, persona.BLOWN]
    for txn, spent in items:
        budget = VARIABLE_BUDGETS.get(txn.bucket, 0)
        pace = Pace(spent, budget, today)
        lines.append(
            f"{pace.marker(warn_ratio)} {txn.business} · {nis(txn.amount)} ₪ — {txn.bucket}"
            f" ({nis(spent)}/{nis(budget)})"
        )
        state = pace.tone(warn_ratio)
        if order.index(state) > order.index(worst):
            worst = state
    lines += ["", f"{days_left(today)} ימים לסוף החודש"]
    key = items[0][0].id if items else today.isoformat()
    return _with_voice(lines, worst, key, speak)


def amount_changed(txn: Txn, previous: float, spent: float, today: date,
                   speak: bool = True) -> str:
    budget = VARIABLE_BUDGETS.get(txn.bucket, 0)
    lines = [
        "✏️ עסקה עודכנה",
        f"{txn.business} · {nis(previous)} ₪ → {nis(txn.amount)} ₪",
        f"קטגוריה: {txn.bucket}",
        "",
        f"עד כה החודש: {nis(spent)} מתוך {nis(budget)} ₪",
    ]
    state = Pace(spent, budget, today).tone()
    return _with_voice(lines, state, txn.id + "u", speak)


def status_report(
    totals: dict[str, float],
    fixed_spent: float,
    today: date,
    warn_ratio: float = 1.15,
    title: str = "📊 מצב התקציב",
    speak: bool = True,
    opener: bool = False,
) -> str:
    variable_spent = sum(totals.get(b, 0.0) for b in VARIABLE_BUDGETS)
    overall = Pace(variable_spent, VARIABLE_TOTAL, today)
    d = days_left(today)
    state = overall.tone(warn_ratio)

    lines = [f"{title} · {today.strftime('%d/%m')}"]
    if speak and opener:
        lines += ["", persona.digest_opener(state, today.isoformat())]
    lines.append("")

    for bucket, budget in sorted(VARIABLE_BUDGETS.items(), key=lambda kv: -kv[1]):
        spent = totals.get(bucket, 0.0)
        pace = Pace(spent, budget, today)
        lines.append(f"{pace.marker(warn_ratio)} {bucket}")
        lines.append(f"   {_bar(spent, budget)} {nis(spent)}/{nis(budget)} ₪")

    lines += [
        "",
        f"משתנות: {nis(variable_spent)} מתוך {nis(VARIABLE_TOTAL)} ₪ {overall.marker(warn_ratio)}",
        f"קבועות: {nis(fixed_spent)} מתוך {nis(FIXED_BUDGET)} ₪",
        "",
        f"בקצב הזה החודש ייסגר על {nis(overall.projection + fixed_spent)} ₪"
        f" (תקציב {nis(VARIABLE_TOTAL + FIXED_BUDGET)})",
        f"{d} ימים לסוף החודש · הכנסה {nis(MONTHLY_INCOME)} ₪",
    ]
    return _with_voice(lines, state, today.isoformat() + title, speak)


def boot_report(totals: dict[str, float], fixed_spent: float, today: date,
                warn_ratio: float = 1.15, speak: bool = True) -> str:
    text = status_report(totals, fixed_spent, today, warn_ratio,
                         title="🤖 הבוט עלה · מצב נוכחי", speak=False)
    if not speak:
        return text
    return text + "\n\n" + persona.quote(persona.BOOT)


def _bar(spent: float, budget: float, width: int = 10) -> str:
    if budget <= 0:
        return "─" * width
    filled = min(width, round(spent / budget * width))
    return "█" * filled + "░" * (width - filled)


def month_detail(
    totals: dict[str, float],
    top: dict[str, list[tuple[str, float]]],
    today: date,
) -> str:
    lines = [f"🧾 פירוט {today.strftime('%m/%Y')}", ""]
    for bucket, budget in sorted(VARIABLE_BUDGETS.items(), key=lambda kv: -kv[1]):
        spent = totals.get(bucket, 0.0)
        lines.append(f"{bucket} — {nis(spent)}/{nis(budget)} ₪")
        for business, amount in top.get(bucket, []):
            lines.append(f"   · {business} {nis(amount)} ₪")
        lines.append("")
    return "\n".join(lines).rstrip()


HELP = (
    "🤖 מועלם הגובה\n\n"
    "/status — כמה נשאר בכל קטגוריה\n"
    "/month — פירוט בתי העסק לפי קטגוריה\n"
    "/help — ההודעה הזאת\n\n"
    "מעבר לזה אני שולח הודעה על כל עסקה משתנה חדשה, ותקציר בערב.\n"
    "אני רושם הכל."
)
