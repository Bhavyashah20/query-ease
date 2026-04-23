"""Tests for queryease.generator — SQL cleaning and prompt building."""

import pytest
from queryease.generator import clean_sql, build_prompt, build_context_prompt


# ─────────────────────────────────────────────
# clean_sql()
# ─────────────────────────────────────────────

class TestCleanSql:

    def test_plain_select_unchanged(self):
        sql = "SELECT * FROM customers"
        assert clean_sql(sql) == sql

    def test_strips_sql_code_fence(self):
        raw = "```sql\nSELECT * FROM customers\n```"
        assert clean_sql(raw) == "SELECT * FROM customers"

    def test_strips_plain_code_fence(self):
        raw = "```\nSELECT * FROM customers\n```"
        assert clean_sql(raw) == "SELECT * FROM customers"

    def test_strips_leading_explanation(self):
        raw = "Here is the SQL:\nSELECT * FROM customers"
        assert clean_sql(raw) == "SELECT * FROM customers"

    def test_preserves_multiline_sql(self):
        raw = "SELECT c.name,\n       c.email\nFROM customers c"
        result = clean_sql(raw)
        assert "SELECT" in result
        assert "FROM customers" in result

    def test_handles_insert(self):
        raw = "INSERT INTO customers (name) VALUES ('Alice')"
        assert clean_sql(raw) == raw

    def test_handles_update(self):
        raw = "UPDATE customers SET name = 'Bob' WHERE id = 1"
        assert clean_sql(raw) == raw

    def test_handles_delete(self):
        raw = "DELETE FROM customers WHERE id = 1"
        assert clean_sql(raw) == raw

    def test_strips_whitespace(self):
        raw = "   SELECT * FROM customers   "
        assert clean_sql(raw) == "SELECT * FROM customers"

    def test_select_wrapped_in_select_string(self):
        # The bug we fixed — LLM wrapping INSERT inside SELECT
        raw = "SELECT 'INSERT INTO customers (name) VALUES (''Alice'')'"
        # clean_sql starts from SELECT — it returns the SELECT statement
        result = clean_sql(raw)
        assert result.startswith("SELECT")

    def test_insert_not_wrapped_in_select(self):
        raw = "INSERT INTO customers (name) VALUES ('Alice')"
        result = clean_sql(raw)
        assert result.startswith("INSERT")


# ─────────────────────────────────────────────
# build_prompt()
# ─────────────────────────────────────────────

class TestBuildPrompt:

    def test_contains_question(self):
        prompt = build_prompt("Show all customers", "Table: customers\n", "postgresql")
        assert "Show all customers" in prompt

    def test_contains_schema(self):
        prompt = build_prompt("Show all customers", "Table: customers\n", "postgresql")
        assert "Table: customers" in prompt

    def test_contains_dialect(self):
        prompt = build_prompt("Show all customers", "Table: customers\n", "postgresql")
        assert "POSTGRESQL" in prompt

    def test_mysql_dialect_hint(self):
        prompt = build_prompt("Show all customers", "Table: customers\n", "mysql")
        assert "MySQL" in prompt or "MYSQL" in prompt

    def test_error_context_included_when_provided(self):
        prompt = build_prompt(
            "Show all customers",
            "Table: customers\n",
            "postgresql",
            previous_error="syntax error near FROM",
        )
        assert "syntax error near FROM" in prompt

    def test_no_error_context_when_not_provided(self):
        prompt = build_prompt("Show all customers", "Table: customers\n", "postgresql")
        assert "previous attempt failed" not in prompt


# ─────────────────────────────────────────────
# build_context_prompt()
# ─────────────────────────────────────────────

class TestBuildContextPrompt:

    def test_empty_history_no_history_block(self):
        prompt = build_context_prompt(
            "Show all customers", "Table: customers\n", "postgresql", []
        )
        assert "CONVERSATION HISTORY" not in prompt

    def test_history_included_in_prompt(self):
        history = [
            {"question": "Show customers from Canada", "sql": "SELECT * FROM customer WHERE ...", "result": "5 rows"},
        ]
        prompt = build_context_prompt(
            "Now show their orders", "Table: customer\n", "postgresql", history
        )
        assert "CONVERSATION HISTORY" in prompt
        assert "Show customers from Canada" in prompt

    def test_multiple_history_turns_all_included(self):
        history = [
            {"question": "Q1", "sql": "SELECT 1", "result": "1 row"},
            {"question": "Q2", "sql": "SELECT 2", "result": "1 row"},
        ]
        prompt = build_context_prompt(
            "Q3", "Table: t\n", "postgresql", history
        )
        assert "Q1" in prompt
        assert "Q2" in prompt

    def test_contains_current_question(self):
        prompt = build_context_prompt(
            "Filter to delivered orders", "Table: orders\n", "postgresql", []
        )
        assert "Filter to delivered orders" in prompt
