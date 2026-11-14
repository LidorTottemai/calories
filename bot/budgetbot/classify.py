"""Transaction filtering, fixed/variable classification and budget bucketing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .config import (
    CARD_SETTLEMENTS,
    CATEGORY_TO_BUCKET,
    DEFAULT_BUCKET,
    FIXED_OVERRIDES,
    IGNORED_CATEGORIES,
)


@dataclass(frozen=True)
class Txn:
    """One spending transaction, normalised."""

    id: str
    date: date
    business: str
    amount: float
    category: str
    bucket: str
    is_fixed: bool
    cashflow_month: str

    @property
    def shekels(self) -> int:
        return round(self.amount)


def normalise_name(raw: str) -> str:
    """Collapse the runs of spaces RiseUp pads merchant names with."""
    return " ".join((raw or "").split())


def _parse_date(raw: str) -> date | None:
    try:
        return date.fromisoformat((raw or "")[:10])
    except ValueError:
        return None


def classify(record: dict, today: date) -> Txn | None:
    """Turn one API record into a Txn, or None if it is not household spending.

    Dropped: income, transactions RiseUp marks excluded, aggregated card bills
    in the checking account (they double-count the card's own rows), savings
    deposits, and anything dated in the future.

    That last one matters: the feed carries scheduled standing orders days
    ahead of time, and counting them would report money that has not left yet.
    """
    if record.get("isIncome") or record.get("isExcluded"):
        return None

    business = normalise_name(record.get("businessName", ""))
    if not business:
        return None

    if record.get("sourceType") == "checkingAccount" and business in CARD_SETTLEMENTS:
        return None

    when = _parse_date(record.get("transactionDate", ""))
    if when is None or when > today:
        return None

    category = record.get("categoryLabel") or ""
    if category in IGNORED_CATEGORIES:
        return None

    try:
        amount = float(record.get("amount", 0) or 0)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None

    txn_id = str(record.get("transactionId") or "").strip()
    if not txn_id:
        return None

    is_fixed = record.get("actualType") == "fixed" or business in FIXED_OVERRIDES
    bucket = "" if is_fixed else CATEGORY_TO_BUCKET.get(category, DEFAULT_BUCKET)

    return Txn(
        id=txn_id,
        date=when,
        business=business,
        amount=amount,
        category=category,
        bucket=bucket,
        is_fixed=is_fixed,
        cashflow_month=str(record.get("cashflowDate") or when.strftime("%Y-%m")),
    )


def classify_all(records: list[dict], today: date) -> list[Txn]:
    out = [classify(r, today) for r in records]
    return [t for t in out if t is not None]
