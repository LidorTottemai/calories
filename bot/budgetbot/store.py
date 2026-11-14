"""SQLite state: transactions seen, alerts sent, Telegram update offset.

Month-to-date totals are always recomputed from this table rather than kept as
running counters, so a transaction that lands days late still lands in the
right month and corrects the figures instead of skewing them.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .classify import Txn

SCHEMA = """
CREATE TABLE IF NOT EXISTS txns (
    id              TEXT PRIMARY KEY,
    txn_date        TEXT NOT NULL,
    business        TEXT NOT NULL,
    amount          REAL NOT NULL,
    category        TEXT NOT NULL,
    bucket          TEXT NOT NULL,
    is_fixed        INTEGER NOT NULL,
    cashflow_month  TEXT NOT NULL,
    first_seen      TEXT NOT NULL,
    alerted         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_txns_month ON txns(cashflow_month, is_fixed);

CREATE TABLE IF NOT EXISTS state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class Change:
    """A transaction the household has not been told about yet."""

    txn: Txn
    kind: str  # "new" | "amount"
    previous: float | None = None


class Store:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ---------------------------------------------------------------- upsert

    def upsert(self, txns: list[Txn], now_iso: str) -> list[Change]:
        """Insert or update, returning the variable ones still to announce."""
        changes: list[Change] = []
        with self._tx() as conn:
            for t in txns:
                row = conn.execute(
                    "SELECT amount, alerted FROM txns WHERE id = ?", (t.id,)
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO txns (id, txn_date, business, amount, category,"
                        " bucket, is_fixed, cashflow_month, first_seen, alerted)"
                        " VALUES (?,?,?,?,?,?,?,?,?,0)",
                        (t.id, t.date.isoformat(), t.business, t.amount, t.category,
                         t.bucket, int(t.is_fixed), t.cashflow_month, now_iso),
                    )
                    if not t.is_fixed:
                        changes.append(Change(t, "new"))
                    continue

                previous = float(row["amount"])
                if abs(previous - t.amount) >= 0.5:
                    # A pending charge settled at a different figure.
                    conn.execute(
                        "UPDATE txns SET amount = ?, business = ?, category = ?,"
                        " bucket = ?, is_fixed = ?, txn_date = ? WHERE id = ?",
                        (t.amount, t.business, t.category, t.bucket,
                         int(t.is_fixed), t.date.isoformat(), t.id),
                    )
                    if not t.is_fixed and row["alerted"]:
                        changes.append(Change(t, "amount", previous))
                    elif not t.is_fixed:
                        changes.append(Change(t, "new"))
        return changes

    def mark_alerted(self, ids: list[str]) -> None:
        if not ids:
            return
        with self._tx() as conn:
            conn.executemany("UPDATE txns SET alerted = 1 WHERE id = ?", [(i,) for i in ids])

    # ----------------------------------------------------------------- reads

    def bucket_totals(self, cashflow_month: str) -> dict[str, float]:
        rows = self._conn.execute(
            "SELECT bucket, SUM(amount) AS total FROM txns"
            " WHERE cashflow_month = ? AND is_fixed = 0 GROUP BY bucket",
            (cashflow_month,),
        ).fetchall()
        return {r["bucket"]: float(r["total"]) for r in rows}

    def fixed_total(self, cashflow_month: str) -> float:
        row = self._conn.execute(
            "SELECT SUM(amount) AS total FROM txns"
            " WHERE cashflow_month = ? AND is_fixed = 1",
            (cashflow_month,),
        ).fetchone()
        return float(row["total"] or 0.0)

    def top_in_bucket(self, cashflow_month: str, bucket: str, limit: int = 5) -> list[tuple[str, float]]:
        rows = self._conn.execute(
            "SELECT business, SUM(amount) AS total FROM txns"
            " WHERE cashflow_month = ? AND is_fixed = 0 AND bucket = ?"
            " GROUP BY business ORDER BY total DESC LIMIT ?",
            (cashflow_month, bucket, limit),
        ).fetchall()
        return [(r["business"], float(r["total"])) for r in rows]

    def count(self, cashflow_month: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM txns WHERE cashflow_month = ?", (cashflow_month,)
        ).fetchone()
        return int(row["n"])

    # ----------------------------------------------------------------- state

    def get_state(self, key: str, default: str = "") -> str:
        row = self._conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO state (key, value) VALUES (?,?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def digest_sent_today(self, day: date) -> bool:
        return self.get_state("last_digest") == day.isoformat()

    def mark_digest_sent(self, day: date) -> None:
        self.set_state("last_digest", day.isoformat())

    def is_first_run(self) -> bool:
        return self.get_state("bootstrapped") != "1"

    def mark_bootstrapped(self) -> None:
        self.set_state("bootstrapped", "1")
