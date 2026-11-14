"""CLI entry point.

    python3 -m budgetbot watch            # the long-running mode
    python3 -m budgetbot poll [--dry-run] # one cycle
    python3 -m budgetbot status           # print budget state, send nothing
    python3 -m budgetbot whoami           # chat ids of everyone who messaged
    python3 -m budgetbot selftest [--telegram]
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from . import messages
from .classify import classify_all
from .config import VARIABLE_BUDGETS, load_settings
from .notify import Notifier, describe_chats
from .riseup import RiseUpError, fetch_month
from .runner import handle_commands, months_to_fetch, now_local, run_cycle
from .store import Store


def _logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_poll(args, settings) -> int:
    store = Store(settings.db_path)
    try:
        notifier = Notifier(settings, dry_run=args.dry_run)
        summary = run_cycle(settings, store, notifier, force=args.force)
        if not args.dry_run:
            handle_commands(settings, store, notifier)
        print(
            f"נמשכו {summary['fetched']} · נשמרו {summary['kept']} · "
            f"חדשות {summary['changes']} · נשלחו {summary['announced']}"
            + (" · שעות שקט" if summary["quiet"] else "")
            + (" · אתחול ראשוני" if summary["bootstrapped"] else "")
        )
        return 0
    finally:
        store.close()


def cmd_watch(args, settings) -> int:
    store = Store(settings.db_path)
    notifier = Notifier(settings, dry_run=args.dry_run)
    log = logging.getLogger("budgetbot")
    log.info("watching every %d seconds", settings.poll_seconds)
    try:
        while True:
            try:
                summary = run_cycle(settings, store, notifier)
                handle_commands(settings, store, notifier)
                log.info(
                    "cycle: fetched=%s kept=%s changes=%s announced=%s quiet=%s",
                    summary["fetched"], summary["kept"], summary["changes"],
                    summary["announced"], summary["quiet"],
                )
            except RiseUpError as exc:
                log.error("RiseUp: %s", exc)
            except Exception:
                log.exception("cycle failed; carrying on")
            time.sleep(settings.poll_seconds)
    except KeyboardInterrupt:
        log.info("stopped")
        return 0
    finally:
        store.close()


def cmd_status(args, settings) -> int:
    moment = now_local()
    month = moment.strftime("%Y-%m")
    store = Store(settings.db_path)
    try:
        if args.refresh:
            records: list[dict] = []
            for cashflow_month in months_to_fetch(moment.date()):
                records.extend(fetch_month(settings, cashflow_month))
            txns = classify_all(records, moment.date())
            store.upsert(txns, moment.isoformat())
            store.mark_alerted([t.id for t in txns])
            store.mark_bootstrapped()
        print(messages.status_report(
            store.bucket_totals(month), store.fixed_total(month),
            moment.date(), settings.pace_warn_ratio,
        ))
        return 0
    finally:
        store.close()


def cmd_whoami(args, settings) -> int:
    if not settings.telegram_token:
        print("חסר TELEGRAM_BOT_TOKEN", file=sys.stderr)
        return 2
    chats = describe_chats(settings)
    if not chats:
        print("אף אחד עוד לא כתב לבוט.\n"
              "פתחו קבוצה, הוסיפו את הבוט, שלחו בה הודעה — והריצו שוב.")
        return 1
    print("העתיקו את המזהים לתוך TELEGRAM_CHAT_IDS, מופרדים בפסיק:\n")
    for chat in chats:
        print(f"  {chat['id']:>16}   {chat['type']:<8} {chat['title']}")
    print("\nTELEGRAM_CHAT_IDS=" + ",".join(str(c["id"]) for c in chats))
    return 0


def cmd_selftest(args, settings) -> int:
    gaps = settings.missing()
    print("הגדרות:", "תקין" if not gaps else "חסר " + ", ".join(gaps))

    moment = now_local()
    try:
        records = fetch_month(settings, moment.strftime("%Y-%m"))
    except RiseUpError as exc:
        print(f"RiseUp: נכשל — {exc}", file=sys.stderr)
        return 1
    txns = classify_all(records, moment.date())
    variable = [t for t in txns if not t.is_fixed]
    fixed = [t for t in txns if t.is_fixed]
    print(f"RiseUp: תקין — {len(records)} רשומות, {len(txns)} נשמרו "
          f"({len(variable)} משתנות, {len(fixed)} קבועות)")
    print(f"משתנות עד כה: {messages.nis(sum(t.amount for t in variable))} ₪ "
          f"מתוך {messages.nis(sum(VARIABLE_BUDGETS.values()))}")

    if args.telegram:
        notifier = Notifier(settings, dry_run=False)
        notifier.send("🤖 בדיקה — הבוט מחובר ושומע אתכם.")
        print("Telegram: נשלחה הודעת בדיקה")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="budgetbot")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("poll", help="run one cycle")
    p.add_argument("--dry-run", action="store_true", help="print messages instead of sending")
    p.add_argument("--force", action="store_true", help="ignore quiet hours")
    p.set_defaults(func=cmd_poll)

    p = sub.add_parser("watch", help="run continuously")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("status", help="print budget state")
    p.add_argument("--refresh", action="store_true", help="fetch first, silently")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("whoami", help="list chat ids that messaged the bot")
    p.set_defaults(func=cmd_whoami)

    p = sub.add_parser("selftest", help="check connectivity")
    p.add_argument("--telegram", action="store_true", help="also send a test message")
    p.set_defaults(func=cmd_selftest)

    args = parser.parse_args(argv)
    _logging(args.verbose)
    return args.func(args, load_settings())


if __name__ == "__main__":
    sys.exit(main())
