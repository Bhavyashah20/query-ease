"""Tests for queryease.db auto-detection."""

import pytest
from queryease.db import get_connector
from queryease.db.postgres import PostgresConnector
from queryease.db.mysql import MySQLConnector
from queryease.db.sqlite import SQLiteConnector


class TestGetConnector:

    def test_postgresql_url_returns_postgres_connector(self):
        conn = get_connector("postgresql://user:pass@localhost:5432/mydb")
        assert isinstance(conn, PostgresConnector)

    def test_postgres_shorthand_url(self):
        conn = get_connector("postgres://user:pass@localhost:5432/mydb")
        assert isinstance(conn, PostgresConnector)

    def test_mysql_url_returns_mysql_connector(self):
        conn = get_connector("mysql://user:pass@localhost:3306/mydb")
        assert isinstance(conn, MySQLConnector)

    def test_sqlite_url_returns_sqlite_connector(self):
        conn = get_connector("sqlite:///path/to/mydb.sqlite")
        assert isinstance(conn, SQLiteConnector)

    def test_empty_url_raises_value_error(self):
        with pytest.raises(ValueError, match="DATABASE_URL is not set"):
            get_connector("")

    def test_none_url_raises_value_error(self):
        with pytest.raises(ValueError):
            get_connector(None)

    def test_unsupported_url_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported"):
            get_connector("mongodb://localhost:27017/mydb")

    def test_postgres_connector_parses_url(self):
        conn = get_connector("postgresql://alice:secret@db.example.com:5433/mydb")
        assert conn.host == "db.example.com"
        assert conn.port == 5433
        assert conn.user == "alice"
        assert conn.dbname == "mydb"

    def test_mysql_connector_parses_url(self):
        conn = get_connector("mysql://root:pass@localhost:3306/shopdb")
        assert conn.host == "localhost"
        assert conn.port == 3306
        assert conn.dbname == "shopdb"

    def test_sqlite_connector_parses_path(self):
        conn = get_connector("sqlite:///home/user/mydb.sqlite")
        assert "mydb.sqlite" in conn.db_path

    def test_dialect_property_postgresql(self):
        conn = get_connector("postgresql://user:pass@localhost/db")
        assert conn.dialect == "postgresql"

    def test_dialect_property_mysql(self):
        conn = get_connector("mysql://user:pass@localhost/db")
        assert conn.dialect == "mysql"

    def test_dialect_property_sqlite(self):
        conn = get_connector("sqlite:///mydb.sqlite")
        assert conn.dialect == "sqlite"
