"""One poll cycle: fetch, classify, store, announce."""
from __future__ import annotations

import logging
from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo

from . import messages
from .classify import classify_all
from .config import TIMEZONE, VARIABLE_BUDGETS, Settings
from .notify import Notifier
from .riseup import fetch_month
from .store import Change, Store

log = logging.getLogger(__name__)
TZ = ZoneInfo(TIMEZONE)


def now_local() -> datetime:
    return datetime.now(TZ)


def in_quiet_hours(moment: datetime, settings: Settings) -> bool:
    """Quiet window wraps midnight, so compare inside or outside accordingly."""
    start = dtime(*settings.quiet_start)
    end = dtime(*settings.quiet_end)
    current = moment.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def months_to_fetch(today: date) -> list[str]:
    """Current cashflow month, plus the previous one early in the month so
    transactions that arrive late are still picked up."""
    months = [today.strftime("%Y-%m")]
    if today.day <= 3:
        prev_year, prev_month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        months.append(f"{prev_year:04d}-{prev_month:02d}")
    return months


def run_cycle(settings: Settings, store: Store, notifier: Notifier,
              moment: datetime | None = None, force: bool = False) -> dict:
    """Returns a small summary dict, which the CLI prints."""
    moment = moment or now_local()
    today = moment.date()
    month = today.strftime("%Y-%m")

    records: list[dict] = []
    for cashflow_month in months_to_fetch(today):
        records.extend(fetch_month(settings, cashflow_month))

    txns = classify_all(records, today)
    changes = store.upsert(txns, moment.isoformat())

    totals = store.bucket_totals(month)
    fixed_spent = store.fixed_total(month)
    summary = {
        "fetched": len(records),
        "kept": len(txns),
        "changes": len(changes),
        "variable_spent": sum(totals.get(b, 0.0) for b in VARIABLE_BUDGETS),
        "fixed_spent": fixed_spent,
        "announced": 0,
        "quiet": False,
        "bootstrapped": False,
    }

    # First run: the month is already half spent. Record it, do not fire a
    # hundred alerts - send one status message instead.
    if store.is_first_run():
        store.mark_alerted([c.txn.id for c in changes])
        store.mark_bootstrapped()
        notifier.send(messages.boot_report(
            totals, fixed_spent, today, settings.pace_warn_ratio,
            speak=settings.persona,
        ))
        summary["bootstrapped"] = True
        return summary

    if in_quiet_hours(moment, settings) and not force:
        summary["quiet"] = True
        return summary

    summary["announced"] = _announce(changes, totals, today, settings, notifier, store)

    digest_time = dtime(*settings.digest_at)
    if moment.time() >= digest_time and not store.digest_sent_today(today):
        notifier.send(messages.status_report(
            totals, fixed_spent, today, settings.pace_warn_ratio,
            title="🌙 סיכום יומי", speak=settings.persona, opener=True,
        ))
        store.mark_digest_sent(today)
        summary["digest"] = True

    return summary


def _announce(changes: list[Change], totals: dict[str, float], today: date,
              settings: Settings, notifier: Notifier, store: Store) -> int:
    new = [c for c in changes if c.kind == "new"]
    updated = [c for c in changes if c.kind == "amount"]

    for change in updated:
        notifier.send(messages.amount_changed(
            change.txn, change.previous or 0.0,
            totals.get(change.txn.bucket, 0.0), today, speak=settings.persona,
        ))

    if not new:
        store.mark_alerted([c.txn.id for c in updated])
        return len(updated)

    if len(new) <= settings.max_individual_alerts:
        for change in new:
            notifier.send(messages.transaction_alert(
                change.txn, totals.get(change.txn.bucket, 0.0),
                today, settings.pace_warn_ratio, speak=settings.persona,
            ))
    else:
        notifier.send(messages.batched_alert(
            [(c.txn, totals.get(c.txn.bucket, 0.0)) for c in new],
            today, settings.pace_warn_ratio, speak=settings.persona,
        ))

    store.mark_alerted([c.txn.id for c in changes])
    return len(changes)


def handle_commands(settings: Settings, store: Store, notifier: Notifier,
                    moment: datetime | None = None) -> int:
    """Answer /status, /month and /help. Returns how many were handled."""
    if not settings.commands_enabled:
        return 0
    moment = moment or now_local()
    today = moment.date()
    month = today.strftime("%Y-%m")

    offset = int(store.get_state("tg_offset", "0") or 0)
    try:
        incoming, next_offset = notifier.poll_commands(offset)
    except Exception as exc:  # never let a Telegram hiccup kill the cycle
        log.warning("could not read commands: %s", exc)
        return 0

    handled = 0
    for message in incoming:
        text = (message.get("text") or "").strip().lower().split("@")[0]
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            continue
        if text.startswith("/status"):
            notifier.reply(chat_id, messages.status_report(
                store.bucket_totals(month), store.fixed_total(month),
                today, settings.pace_warn_ratio, speak=settings.persona,
            ))
        elif text.startswith("/month"):
            totals = store.bucket_totals(month)
            top = {b: store.top_in_bucket(month, b) for b in VARIABLE_BUDGETS}
            notifier.reply(chat_id, messages.month_detail(totals, top, today))
        elif text.startswith(("/help", "/start")):
            notifier.reply(chat_id, messages.HELP)
        else:
            continue
        handled += 1

    if next_offset != offset:
        store.set_state("tg_offset", str(next_offset))
    return handled
