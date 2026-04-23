"""Shared fixtures for QueryEase tests."""

import pytest
import sys
import os

# Add src to path so tests can import queryease modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def sample_schema():
    """A minimal schema dict used across multiple tests."""
    return {
        "customers": [
            {"name": "id",         "type": "integer", "nullable": False, "key": "PRI"},
            {"name": "name",       "type": "varchar", "nullable": False, "key": ""},
            {"name": "email",      "type": "varchar", "nullable": True,  "key": "UNI"},
            {"name": "city",       "type": "varchar", "nullable": True,  "key": ""},
        ],
        "orders": [
            {"name": "id",          "type": "integer",       "nullable": False, "key": "PRI"},
            {"name": "customer_id", "type": "integer",       "nullable": False, "key": "MUL"},
            {"name": "total",       "type": "decimal(10,2)", "nullable": False, "key": ""},
            {"name": "status",      "type": "varchar",       "nullable": False, "key": ""},
            {"name": "created_at",  "type": "timestamp",     "nullable": True,  "key": ""},
        ],
        "products": [
            {"name": "id",       "type": "integer",       "nullable": False, "key": "PRI"},
            {"name": "name",     "type": "varchar",       "nullable": False, "key": ""},
            {"name": "price",    "type": "decimal(10,2)", "nullable": False, "key": ""},
            {"name": "stock",    "type": "integer",       "nullable": False, "key": ""},
        ],
    }


@pytest.fixture
def sample_descriptions():
    """Sample column descriptions."""
    return {
        "orders": {
            "total":  "total order value in rupees",
            "status": "order status: pending, delivered, or cancelled",
        }
    }
