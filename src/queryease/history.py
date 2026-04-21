"""Query history manager for QueryEase — stores past queries in SQLite."""

import sqlite3
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

HISTORY_DIR = Path.home() / ".queryease"
HISTORY_DB = HISTORY_DIR / "history.db"


@dataclass
class HistoryEntry:
    id: int
    question: str
    sql: str
    result_summary: str
    dialect: str
    timestamp: float

    @property
    def formatted_time(self) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _get_conn() -> sqlite3.Connection:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(HISTORY_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            question       TEXT NOT NULL,
            sql            TEXT NOT NULL,
            result_summary TEXT DEFAULT '',
            dialect        TEXT DEFAULT '',
            timestamp      REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_query(question: str, sql: str, result_summary: str = "", dialect: str = ""):
    """Save a successful query to history."""
    _init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO queries (question, sql, result_summary, dialect, timestamp) VALUES (?, ?, ?, ?, ?)",
        (question, sql, result_summary, dialect, time.time()),
    )
    conn.commit()
    conn.close()


def get_history(limit: int = 10) -> List[HistoryEntry]:
    """Retrieve the last N queries, most recent first."""
    _init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM queries ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [
        HistoryEntry(
            id=row["id"],
            question=row["question"],
            sql=row["sql"],
            result_summary=row["result_summary"],
            dialect=row["dialect"],
            timestamp=row["timestamp"],
        )
        for row in rows
    ]


def clear_history():
    """Delete all history entries."""
    _init_db()
    conn = _get_conn()
    conn.execute("DELETE FROM queries")
    conn.commit()
    conn.close()
