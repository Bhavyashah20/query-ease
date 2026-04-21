"""SQLite connector for QueryEase."""

import sqlite3
from urllib.parse import urlparse
from typing import Dict, List
from .base import BaseConnector


class SQLiteConnector(BaseConnector):

    def __init__(self, url: str):
        # sqlite:///path/to/db.sqlite  or  sqlite:////absolute/path.sqlite
        path = url.replace("sqlite:///", "", 1)
        self.db_path = path

    @property
    def dialect(self) -> str:
        return "sqlite"

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_schema(self) -> Dict[str, List[dict]]:
        schema = {}
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cur.fetchall()]

            for table in tables:
                cur.execute(f"PRAGMA table_info(`{table}`)")
                schema[table] = [
                    {
                        "name": row["name"],
                        "type": row["type"] or "TEXT",
                        "nullable": not row["notnull"],
                        "key": "PRI" if row["pk"] else "",
                    }
                    for row in cur.fetchall()
                ]

                # Mark foreign keys
                cur.execute(f"PRAGMA foreign_key_list(`{table}`)")
                fk_cols = {row["from"] for row in cur.fetchall()}
                for col in schema[table]:
                    if col["name"] in fk_cols and col["key"] != "PRI":
                        col["key"] = "MUL"
        finally:
            conn.close()
        return schema

    def execute(self, sql: str):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(sql)
            first_word = sql.strip().split()[0].upper()

            if first_word == "SELECT":
                rows = [dict(row) for row in cur.fetchall()]
                columns = list(rows[0].keys()) if rows else (
                    [d[0] for d in cur.description] if cur.description else []
                )
                conn.commit()
                return columns, rows, 0
            else:
                rows_affected = cur.rowcount
                conn.commit()
                return [], [], rows_affected
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
