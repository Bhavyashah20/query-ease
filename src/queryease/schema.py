"""Schema manager with file-based caching for QueryEase."""

import json
import hashlib
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from . import config
from .db import get_connector

# Fix #1: Absolute paths based on module location
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = Path.home() / ".queryease"
CACHE_FILE = CACHE_DIR / "schema_cache.json"
CACHE_META_FILE = CACHE_DIR / "schema_cache_meta.json"

# Fix #2: Cache TTL in seconds (1 hour)
CACHE_TTL = 3600


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
    """Returns True if cache is older than CACHE_TTL."""
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
    Fix #2: Auto-refreshes if cache is stale or schema hash changed.
    Returns (schema, from_cache).
    """
    if refresh:
        clear_cache()

    cached = _load_cache()
    meta = _load_meta()

    if cached is not None and meta is not None:
        if not _is_cache_stale(meta):
            # Verify schema hash hasn't changed against live DB
            try:
                connector = get_connector(config.DATABASE_URL)
                live_schema = connector.get_schema()
                live_hash = _compute_schema_hash(live_schema)
                if live_hash == meta.get("schema_hash"):
                    return cached, True
                # Hash changed — refresh silently
                _save_cache(live_schema)
                return live_schema, False
            except Exception:
                # If DB unreachable, serve stale cache rather than crash
                return cached, True
        # Cache expired
        clear_cache()

    # Cache miss or expired — fetch from DB
    connector = get_connector(config.DATABASE_URL)
    schema = connector.get_schema()
    _save_cache(schema)
    return schema, False


def format_schema_for_prompt(schema: Dict[str, List[dict]], join_hints: Optional[str] = None) -> str:
    """Convert schema dict to a string for the LLM prompt."""
    lines = []
    for table, columns in schema.items():
        lines.append(f"Table: {table}")
        for col in columns:
            key_label = ""
            if col["key"] == "PRI":
                key_label = " [PRIMARY KEY]"
            elif col["key"] == "MUL":
                key_label = " [FOREIGN KEY]"
            nullable = "" if col["nullable"] else " NOT NULL"
            lines.append(f"  - {col['name']} ({col['type']}){nullable}{key_label}")
        lines.append("")

    if join_hints:
        lines.append("JOIN HINTS (use these relationships for JOINs):")
        lines.append(join_hints)
        lines.append("")

    return "\n".join(lines)


# Fix #8: Build a JOIN graph from FK metadata
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
                # fk_ref expected: "referenced_table.referenced_column"
                ref = col["fk_ref"]
                if "." in ref:
                    ref_table, ref_col = ref.split(".", 1)
                    fk_columns.append((table, col["name"], ref_table, ref_col))

    for from_table, from_col, to_table, to_col in fk_columns:
        graph.setdefault(from_table, {})[to_table] = {
            "from": f"{from_table}.{from_col}",
            "to": f"{to_table}.{to_col}",
        }
        # Add reverse edge too
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
