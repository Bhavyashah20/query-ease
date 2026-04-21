"""PostgreSQL connector for QueryEase."""

import psycopg2
import psycopg2.extras
from urllib.parse import urlparse
from typing import Dict, List, Tuple, Any
from .base import BaseConnector


class PostgresConnector(BaseConnector):

    def __init__(self, url: str):
        parsed = urlparse(url)
        self.host = parsed.hostname
        self.port = parsed.port or 5432
        self.user = parsed.username
        self.password = parsed.password or ""
        self.dbname = parsed.path.lstrip("/")

    @property
    def dialect(self) -> str:
        return "postgresql"

    def _connect(self):
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            dbname=self.dbname,
        )

    def get_schema(self) -> Dict[str, List[dict]]:
        schema = {}
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row["table_name"] for row in cur.fetchall()]

                for table in tables:
                    cur.execute("""
                        SELECT
                            c.column_name AS name,
                            c.data_type AS type,
                            c.is_nullable AS nullable,
                            CASE
                                WHEN pk.column_name IS NOT NULL THEN 'PRI'
                                WHEN fk.column_name IS NOT NULL THEN 'MUL'
                                ELSE ''
                            END AS key
                        FROM information_schema.columns c
                        LEFT JOIN (
                            SELECT kcu.column_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                                ON tc.constraint_name = kcu.constraint_name
                            WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY'
                        ) pk ON c.column_name = pk.column_name
                        LEFT JOIN (
                            SELECT kcu.column_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                                ON tc.constraint_name = kcu.constraint_name
                            WHERE tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY'
                        ) fk ON c.column_name = fk.column_name
                        WHERE c.table_name = %s AND c.table_schema = 'public'
                        ORDER BY c.ordinal_position
                    """, (table, table, table))

                    schema[table] = [
                        {
                            "name": row["name"],
                            "type": row["type"],
                            "nullable": row["nullable"] == "YES",
                            "key": row["key"],
                        }
                        for row in cur.fetchall()
                    ]
        finally:
            conn.close()
        return schema

    def execute(self, sql: str):
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                first_word = sql.strip().split()[0].upper()

                if first_word == "SELECT":
                    rows = [dict(r) for r in cur.fetchall()]
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
