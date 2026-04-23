"""Tests for queryease.schema"""

import json
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from queryease.schema import (
    format_schema_for_prompt,
    build_join_graph,
    format_join_hints,
    load_descriptions,
    _compute_schema_hash,
    _is_cache_stale,
)


# ─────────────────────────────────────────────
# format_schema_for_prompt()
# ─────────────────────────────────────────────

class TestFormatSchemaForPrompt:

    def test_basic_output_contains_table_name(self, sample_schema):
        result = format_schema_for_prompt(sample_schema)
        assert "Table: customers" in result
        assert "Table: orders" in result

    def test_columns_listed(self, sample_schema):
        result = format_schema_for_prompt(sample_schema)
        assert "id" in result
        assert "email" in result

    def test_primary_key_label(self, sample_schema):
        result = format_schema_for_prompt(sample_schema)
        assert "[PRIMARY KEY]" in result

    def test_foreign_key_label(self, sample_schema):
        result = format_schema_for_prompt(sample_schema)
        assert "[FOREIGN KEY]" in result

    def test_not_null_label(self, sample_schema):
        result = format_schema_for_prompt(sample_schema)
        assert "NOT NULL" in result

    def test_join_hints_included_when_provided(self, sample_schema):
        result = format_schema_for_prompt(sample_schema, join_hints="  orders.customer_id → customers.id")
        assert "JOIN HINTS" in result
        assert "orders.customer_id" in result

    def test_descriptions_injected(self, sample_schema, sample_descriptions):
        result = format_schema_for_prompt(sample_schema, descriptions=sample_descriptions)
        assert "total order value in rupees" in result

    def test_description_not_shown_for_undescribed_column(self, sample_schema, sample_descriptions):
        result = format_schema_for_prompt(sample_schema, descriptions=sample_descriptions)
        # customers.name has no description — should not have → marker
        lines = [l for l in result.splitlines() if "- name" in l and "customers" not in l]
        for line in lines:
            if "customers" not in result[:result.find(line)].split("Table:")[-1]:
                assert "→" not in line


# ─────────────────────────────────────────────
# build_join_graph()
# ─────────────────────────────────────────────

class TestBuildJoinGraph:

    def test_empty_schema_returns_empty_graph(self):
        assert build_join_graph({}) == {}

    def test_schema_without_fk_refs_returns_empty(self, sample_schema):
        # sample_schema has MUL key but no fk_ref field
        graph = build_join_graph(sample_schema)
        assert graph == {}

    def test_schema_with_fk_ref_builds_graph(self):
        schema = {
            "orders": [
                {"name": "id",          "type": "integer", "nullable": False, "key": "PRI", "fk_ref": None},
                {"name": "customer_id", "type": "integer", "nullable": False, "key": "MUL", "fk_ref": "customers.id"},
            ],
            "customers": [
                {"name": "id", "type": "integer", "nullable": False, "key": "PRI", "fk_ref": None},
            ],
        }
        graph = build_join_graph(schema)
        assert "orders" in graph
        assert "customers" in graph["orders"]

    def test_bidirectional_edges(self):
        schema = {
            "orders": [
                {"name": "customer_id", "type": "integer", "nullable": False, "key": "MUL", "fk_ref": "customers.id"},
            ],
            "customers": [
                {"name": "id", "type": "integer", "nullable": False, "key": "PRI", "fk_ref": None},
            ],
        }
        graph = build_join_graph(schema)
        # Both directions should exist
        assert "customers" in graph.get("orders", {})
        assert "orders" in graph.get("customers", {})


# ─────────────────────────────────────────────
# load_descriptions()
# ─────────────────────────────────────────────

class TestLoadDescriptions:

    def test_returns_empty_dict_when_no_file(self):
        with patch("queryease.schema.DESCRIPTIONS_FILE") as mock_path:
            mock_path.exists.return_value = False
            result = load_descriptions()
        assert result == {}

    def test_loads_valid_descriptions_file(self, tmp_path):
        data = {
            "orders": {"total": "order total in USD"},
            "customers": {"active": "1 if active"}
        }
        f = tmp_path / "descriptions.json"
        f.write_text(json.dumps(data))

        with patch("queryease.schema.DESCRIPTIONS_FILE", f):
            result = load_descriptions()

        assert "orders" in result
        assert result["orders"]["total"] == "order total in USD"

    def test_skips_non_dict_keys(self, tmp_path):
        data = {
            "_readme": "this is a comment",
            "orders": {"total": "order total"}
        }
        f = tmp_path / "descriptions.json"
        f.write_text(json.dumps(data))

        with patch("queryease.schema.DESCRIPTIONS_FILE", f):
            result = load_descriptions()

        assert "_readme" not in result
        assert "orders" in result

    def test_keys_normalized_to_lowercase(self, tmp_path):
        data = {"Orders": {"Total": "order total"}}
        f = tmp_path / "descriptions.json"
        f.write_text(json.dumps(data))

        with patch("queryease.schema.DESCRIPTIONS_FILE", f):
            result = load_descriptions()

        assert "orders" in result
        assert "total" in result["orders"]

    def test_returns_empty_on_invalid_json(self, tmp_path):
        f = tmp_path / "descriptions.json"
        f.write_text("this is not json {{{")

        with patch("queryease.schema.DESCRIPTIONS_FILE", f):
            result = load_descriptions()

        assert result == {}


# ─────────────────────────────────────────────
# _compute_schema_hash()
# ─────────────────────────────────────────────

class TestComputeSchemaHash:

    def test_same_schema_same_hash(self, sample_schema):
        h1 = _compute_schema_hash(sample_schema)
        h2 = _compute_schema_hash(sample_schema)
        assert h1 == h2

    def test_different_schema_different_hash(self, sample_schema):
        modified = dict(sample_schema)
        modified["new_table"] = [{"name": "id", "type": "integer", "nullable": False, "key": "PRI"}]
        h1 = _compute_schema_hash(sample_schema)
        h2 = _compute_schema_hash(modified)
        assert h1 != h2

    def test_hash_is_string(self, sample_schema):
        h = _compute_schema_hash(sample_schema)
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 hex digest


# ─────────────────────────────────────────────
# _is_cache_stale()
# ─────────────────────────────────────────────

class TestIsCacheStale:

    def test_fresh_cache_not_stale(self):
        import time
        meta = {"timestamp": time.time()}
        assert _is_cache_stale(meta) is False

    def test_old_cache_is_stale(self):
        meta = {"timestamp": 0}  # epoch — definitely stale
        assert _is_cache_stale(meta) is True

    def test_missing_timestamp_is_stale(self):
        assert _is_cache_stale({}) is True
