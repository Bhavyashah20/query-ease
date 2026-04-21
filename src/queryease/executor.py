"""SQL Executor - delegates to the right DB connector."""

import time
from . import config
from .db import get_connector


class QueryResult:
    def __init__(self, sql, columns, rows, row_count, execution_time_ms, rows_affected=0):
        self.sql = sql
        self.columns = columns
        self.rows = rows
        self.row_count = row_count
        self.execution_time_ms = execution_time_ms
        self.rows_affected = rows_affected

    def is_empty(self):
        return self.row_count == 0

    def is_write(self):
        return self.rows_affected > 0 and self.row_count == 0


class ExecutionError(Exception):
    pass


def execute(sql: str) -> QueryResult:
    """Execute SQL using the auto-detected connector."""
    connector = get_connector(config.DATABASE_URL)
    start = time.time()

    try:
        columns, rows, rows_affected = connector.execute(sql)
        elapsed_ms = round((time.time() - start) * 1000, 2)

        return QueryResult(
            sql=sql,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=elapsed_ms,
            rows_affected=rows_affected,
        )
    except Exception as e:
        raise ExecutionError(f"Query failed: {e}") from e
