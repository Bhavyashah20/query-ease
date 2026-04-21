"""MySQL connector for QueryEase."""

import pymysql
import pymysql.cursors
from urllib.parse import urlparse
from typing import Dict, List
from .base import BaseConnector


class MySQLConnector(BaseConnector):

    def __init__(self, url: str):
        parsed = urlparse(url)
        self.host = parsed.hostname
        self.port = parsed.port or 3306
        self.user = parsed.username
        self.password = parsed.password or ""
        self.dbname = parsed.path.lstrip("/")

    @property
    def dialect(self) -> str:
        return "mysql"

    def _connect(self):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.dbname,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def get_schema(self) -> Dict[str, List[dict]]:
        schema = {}
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES")
                tables = [list(row.values())[0] for row in cur.fetchall()]

                for table in tables:
                    cur.execute(f"DESCRIBE `{table}`")
                    schema[table] = [
                        {
                            "name": row["Field"],
                            "type": row["Type"],
                            "nullable": row["Null"] == "YES",
                            "key": row["Key"] or "",
                        }
                        for row in cur.fetchall()
                    ]
        finally:
            conn.close()
        return schema

    def execute(self, sql: str):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                first_word = sql.strip().split()[0].upper()

                if first_word == "SELECT":
                    rows = cur.fetchall()
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
