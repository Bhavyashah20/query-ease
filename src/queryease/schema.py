"""Schema manager with file-based caching for QueryEase."""

import json
import hashlib
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from . import config
from .db import get_connector

# Absolute paths based on module location
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = Path.home() / ".queryease"
CACHE_FILE = CACHE_DIR / "schema_cache.json"
CACHE_META_FILE = CACHE_DIR / "schema_cache_meta.json"

# Cache TTL in seconds (1 hour)
CACHE_TTL = 3600

# Descriptions file lives in project root next to main.py
DESCRIPTIONS_FILE = Path(__file__).resolve().parent.parent.parent / "descriptions.json"


def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_cache() -> Optional[Dict]:
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _load_meta() -> Optional[Dict]:
    if not CACHE_META_FILE.exists():
        return None
    try:
        with open(CACHE_META_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _save_cache(schema: Dict[str, List[dict]]):
    _ensure_cache_dir()
    schema_hash = _compute_schema_hash(schema)
    with open(CACHE_FILE, "w") as f:
        json.dump(schema, f, indent=2)
    with open(CACHE_META_FILE, "w") as f:
        json.dump({
            "timestamp": time.time(),
            "schema_hash": schema_hash,
            "tables_count": len(schema),
        }, f, indent=2)


def _compute_schema_hash(schema: Dict) -> str:
    raw = json.dumps(schema, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _is_cache_stale(meta: Dict) -> bool:
    age = time.time() - meta.get("timestamp", 0)
    return age > CACHE_TTL


def clear_cache():
    removed = False
    for f in (CACHE_FILE, CACHE_META_FILE):
        if f.exists():
            f.unlink()
            removed = True
    return removed


def cache_exists() -> bool:
    return CACHE_FILE.exists()


def get_schema(refresh: bool = False) -> Tuple:
    """
    Get schema using cache when available.
    Auto-refreshes if cache is stale or schema hash changed.
    Returns (schema, from_cache).
    """
    if refresh:
        clear_cache()

    cached = _load_cache()
    meta = _load_meta()

    if cached is not None and meta is not None:
        if not _is_cache_stale(meta):
            try:
                connector = get_connector(config.DATABASE_URL)
                live_schema = connector.get_schema()
                live_hash = _compute_schema_hash(live_schema)
                if live_hash == meta.get("schema_hash"):
                    return cached, True
                _save_cache(live_schema)
                return live_schema, False
            except Exception:
                return cached, True
        clear_cache()

    connector = get_connector(config.DATABASE_URL)
    schema = connector.get_schema()
    _save_cache(schema)
    return schema, False


# ─────────────────────────────────────────────
# #5 COLUMN DESCRIPTIONS
# ─────────────────────────────────────────────

def load_descriptions() -> Dict[str, Dict[str, str]]:
    """
    Load user-defined column descriptions from descriptions.json.

    File format:
    {
        "orders": {
            "rev_amt": "total revenue amount in rupees",
            "cust_id": "the customer who placed this order"
        },
        "customers": {
            "flg_active": "1 if customer is active, 0 if churned"
        }
    }

    Returns empty dict if file doesn't exist — descriptions are optional.
    """
    if not DESCRIPTIONS_FILE.exists():
        return {}
    try:
        with open(DESCRIPTIONS_FILE, "r") as f:
            data = json.load(f)
        # Normalize all keys to lowercase for case-insensitive matching
        return {
            table.lower(): {col.lower(): desc for col, desc in cols.items()}
            for table, cols in data.items()
            if isinstance(cols, dict)   # skip _readme and other non-table keys
        }
    except (json.JSONDecodeError, IOError):
        return {}


def descriptions_exist() -> bool:
    """Check if a descriptions.json file exists."""
    return DESCRIPTIONS_FILE.exists()


def format_schema_for_prompt(
    schema: Dict[str, List[dict]],
    join_hints: Optional[str] = None,
    descriptions: Optional[Dict[str, Dict[str, str]]] = None,
) -> str:
    """
    Convert schema dict to a string for the LLM prompt.

    If descriptions are provided, they are injected next to column names:
      - rev_amt (integer) NOT NULL  → "total revenue amount in rupees"
    This helps the LLM understand cryptic column names.
    """
    descriptions = descriptions or {}
    lines = []

    for table, columns in schema.items():
        lines.append(f"Table: {table}")
        table_descs = descriptions.get(table.lower(), {})

        for col in columns:
            key_label = ""
            if col["key"] == "PRI":
                key_label = " [PRIMARY KEY]"
            elif col["key"] == "MUL":
                key_label = " [FOREIGN KEY]"
            nullable = "" if col["nullable"] else " NOT NULL"

            # Inject description if available for this column
            col_desc = table_descs.get(col["name"].lower(), "")
            desc_label = f'  → "{col_desc}"' if col_desc else ""

            lines.append(
                f"  - {col['name']} ({col['type']}){nullable}{key_label}{desc_label}"
            )
        lines.append("")

    if join_hints:
        lines.append("JOIN HINTS (use these relationships for JOINs):")
        lines.append(join_hints)
        lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# JOIN GRAPH
# ─────────────────────────────────────────────

def build_join_graph(schema: Dict[str, List[dict]]) -> Dict[str, Dict]:
    """
    Build a graph of FK relationships between tables.
    Returns: {table: {related_table: {"from": col, "to": col}}}
    """
    graph: Dict[str, Dict] = {}
    fk_columns: List[Tuple] = []

    for table, columns in schema.items():
        for col in columns:
            if col.get("key") == "MUL" and col.get("fk_ref"):
                ref = col["fk_ref"]
                if "." in ref:
                    ref_table, ref_col = ref.split(".", 1)
                    fk_columns.append((table, col["name"], ref_table, ref_col))

    for from_table, from_col, to_table, to_col in fk_columns:
        graph.setdefault(from_table, {})[to_table] = {
            "from": f"{from_table}.{from_col}",
            "to": f"{to_table}.{to_col}",
        }
        graph.setdefault(to_table, {})[from_table] = {
            "from": f"{to_table}.{to_col}",
            "to": f"{from_table}.{from_col}",
        }

    return graph


def format_join_hints(join_graph: Dict) -> str:
    """Format the JOIN graph as a human-readable string for the LLM."""
    if not join_graph:
        return ""
    hints = []
    seen = set()
    for table, relations in join_graph.items():
        for related, edge in relations.items():
            key = tuple(sorted([edge["from"], edge["to"]]))
            if key not in seen:
                hints.append(f"  {edge['from']} → {edge['to']}")
                seen.add(key)
    return "\n".join(hints)


def get_dialect() -> str:
    """Return the DB dialect for the current DATABASE_URL."""
    connector = get_connector(config.DATABASE_URL)
    return connector.dialect