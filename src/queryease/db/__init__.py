"""Auto-detect database type from URL and return the right connector."""

from .base import BaseConnector


def get_connector(url: str) -> BaseConnector:
    """
    Auto-detect DB type from DATABASE_URL prefix and return the right connector.

    Supported formats:
        postgresql://user:pass@host:5432/dbname
        postgres://user:pass@host:5432/dbname
        mysql://user:pass@host:3306/dbname
        sqlite:///path/to/file.db
    """
    if not url:
        raise ValueError(
            "DATABASE_URL is not set.\n"
            "Set it in your .env file. Examples:\n"
            "  postgresql://user:pass@localhost:5432/mydb\n"
            "  mysql://user:pass@localhost:3306/mydb\n"
            "  sqlite:///path/to/mydb.sqlite"
        )

    url_lower = url.lower()

    if url_lower.startswith("postgresql://") or url_lower.startswith("postgres://"):
        from .postgres import PostgresConnector
        return PostgresConnector(url)

    elif url_lower.startswith("mysql://"):
        from .mysql import MySQLConnector
        return MySQLConnector(url)

    elif url_lower.startswith("sqlite:///"):
        from .sqlite import SQLiteConnector
        return SQLiteConnector(url)

    else:
        raise ValueError(
            f"Unsupported database URL: '{url[:30]}...'\n"
            "Supported prefixes: postgresql://, mysql://, sqlite:///"
        )
