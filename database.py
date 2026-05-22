import sqlite3
from datetime import datetime
import config

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def init_db() -> None:
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS daily_goals (
            day_of_week INTEGER PRIMARY KEY,
            calorie_goal INTEGER NOT NULL DEFAULT 2000
        );

        CREATE TABLE IF NOT EXISTS meal_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            description TEXT NOT NULL,
            calories INTEGER NOT NULL,
            protein_g REAL NOT NULL,
            carbs_g REAL NOT NULL,
            has_fiber INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_meal_logs_date ON meal_logs(log_date);
    """)
    # Pre-populate default goals for all 7 days if not present
    for day in range(7):
        conn.execute(
            "INSERT OR IGNORE INTO daily_goals (day_of_week, calorie_goal) VALUES (?, 2000)",
            (day,),
        )
    conn.commit()


def get_today_date_str() -> str:
    return datetime.now(config.TIMEZONE).strftime("%Y-%m-%d")


def get_goal(day_of_week: int) -> int:
    row = _get_conn().execute(
        "SELECT calorie_goal FROM daily_goals WHERE day_of_week = ?", (day_of_week,)
    ).fetchone()
    return row["calorie_goal"] if row else 2000


def set_goal(day_of_week: int, calories: int) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO daily_goals (day_of_week, calorie_goal) VALUES (?, ?)"
        " ON CONFLICT(day_of_week) DO UPDATE SET calorie_goal = excluded.calorie_goal",
        (day_of_week, calories),
    )
    conn.commit()


def get_all_goals() -> dict[int, int]:
    rows = _get_conn().execute("SELECT day_of_week, calorie_goal FROM daily_goals").fetchall()
    return {row["day_of_week"]: row["calorie_goal"] for row in rows}


def log_meal(
    log_date: str,
    description: str,
    calories: int,
    protein_g: float,
    carbs_g: float,
    has_fiber: bool,
    created_at: str,
) -> int:
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO meal_logs (log_date, description, calories, protein_g, carbs_g, has_fiber, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (log_date, description, calories, protein_g, carbs_g, int(has_fiber), created_at),
    )
    conn.commit()
    return cursor.lastrowid


def get_day_totals(log_date: str) -> dict:
    row = _get_conn().execute(
        """
        SELECT
            COALESCE(SUM(calories), 0) AS total_calories,
            COALESCE(SUM(protein_g), 0.0) AS total_protein_g,
            COALESCE(SUM(carbs_g), 0.0) AS total_carbs_g,
            COALESCE(SUM(has_fiber), 0) AS fiber_meal_count
        FROM meal_logs
        WHERE log_date = ?
        """,
        (log_date,),
    ).fetchone()
    return dict(row)
