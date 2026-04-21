"""SQL Validator - safety and complexity checks before query execution."""

import sqlparse
from sqlparse.sql import Where, Comparison, Identifier, IdentifierList
from sqlparse.tokens import Keyword, DML
import re
from typing import Dict, List, Set, Tuple


FORBIDDEN_KEYWORDS = [
    "DROP", "TRUNCATE", "ALTER", "CREATE", "RENAME",
    "GRANT", "REVOKE", "EXEC", "EXECUTE",
]

WRITE_KEYWORDS = ["INSERT", "UPDATE", "DELETE"]


class ValidationError(Exception):
    pass


def check_not_empty(sql: str):
    if not sql or not sql.strip():
        raise ValidationError("Generated SQL is empty. Try rephrasing your question.")


def check_forbidden_keywords(sql: str):
    sql_upper = sql.upper()
    found = [kw for kw in FORBIDDEN_KEYWORDS if kw in sql_upper]
    if found:
        raise ValidationError(
            f"Query contains forbidden keyword(s): {', '.join(found)}"
        )


def check_parseable(sql: str):
    try:
        parsed = sqlparse.parse(sql)
        if not parsed or not parsed[0].tokens:
            raise ValidationError("SQL could not be parsed.")
    except Exception as e:
        raise ValidationError(f"SQL parse error: {e}")


def check_single_statement(sql: str):
    statements = [s for s in sqlparse.parse(sql) if s.value.strip()]
    if len(statements) > 1:
        raise ValidationError("Multiple SQL statements detected. Only one query at a time is allowed.")


def is_write_query(sql: str) -> bool:
    """Returns True if the query modifies data (INSERT/UPDATE/DELETE)."""
    first_word = sql.strip().split()[0].upper()
    return first_word in WRITE_KEYWORDS


def is_complex_query(sql: str) -> bool:
    """
    Returns True if query is complex enough to need an LLM judge.
    Triggers: 2+ JOINs, subqueries, HAVING clause, query length > 300 chars.
    """
    sql_upper = sql.upper()
    join_count = len(re.findall(r'\bJOIN\b', sql_upper))
    has_subquery = "SELECT" in sql_upper[10:]
    has_having = "HAVING" in sql_upper
    is_long = len(sql) > 300

    return join_count >= 2 or has_subquery or has_having or is_long


# Fix #5: Schema-aware table/column validation

def extract_tables_from_sql(sql: str) -> Set[str]:
    """
    Extract table names referenced in the SQL using sqlparse + regex fallback.
    Handles FROM, JOIN, INTO, UPDATE clauses.
    """
    tables: Set[str] = set()
    sql_upper = sql.upper()

    # Regex patterns for table extraction
    patterns = [
        r'\bFROM\s+([`"\[]?[\w]+[`"\]]?)',
        r'\bJOIN\s+([`"\[]?[\w]+[`"\]]?)',
        r'\bINTO\s+([`"\[]?[\w]+[`"\]]?)',
        r'\bUPDATE\s+([`"\[]?[\w]+[`"\]]?)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            name = match.group(1).strip('`"[]').lower()
            # Filter out SQL keywords that might be caught
            if name not in {"select", "where", "set", "values", "returning"}:
                tables.add(name)

    return tables


def extract_columns_from_sql(sql: str) -> Set[str]:
    """
    Extract column names from the SQL (best-effort).
    Looks at SELECT list, WHERE conditions, SET clause.
    """
    columns: Set[str] = set()

    # SELECT col1, col2 or SELECT t.col
    select_match = re.search(r'\bSELECT\b(.*?)\bFROM\b', sql, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_part = select_match.group(1)
        for part in select_part.split(","):
            part = part.strip()
            if part == "*":
                continue
            # Handle table.column or column AS alias
            col = re.split(r'\s+AS\s+', part, flags=re.IGNORECASE)[0].strip()
            col = col.split(".")[-1].strip('`"[] ')
            if col and re.match(r'^\w+$', col):
                columns.add(col.lower())

    # WHERE col = / SET col =
    for pattern in [r'\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bHAVING\b|$)',
                    r'\bSET\b(.*?)\bWHERE\b']:
        match = re.search(pattern, sql, re.IGNORECASE | re.DOTALL)
        if match:
            clause = match.group(1)
            for col_match in re.finditer(r'\b([\w]+)\s*(?:=|<>|<=|>=|!=|ILIKE|LIKE\b|IN\b)', clause, re.IGNORECASE):
                col = col_match.group(1).lower()
                if col not in {"and", "or", "not", "is", "null", "true", "false",
                               "where", "set", "ilike", "like", "in", "between"}:
                    columns.add(col)

    return columns


def validate_against_schema(sql: str, schema: Dict[str, List[dict]]):
    """
    Fix #5: Validate that tables and columns in the SQL exist in the schema.
    Raises ValidationError if hallucinated tables/columns are detected.
    """
    schema_tables = {t.lower(): t for t in schema.keys()}
    all_columns: Set[str] = set()
    for cols in schema.values():
        for c in cols:
            all_columns.add(c["name"].lower())

    # Check tables
    used_tables = extract_tables_from_sql(sql)
    unknown_tables = [t for t in used_tables if t not in schema_tables]
    if unknown_tables:
        raise ValidationError(
            f"Query references table(s) not found in schema: {', '.join(unknown_tables)}. "
            f"Available tables: {', '.join(schema_tables.keys())}"
        )

    # Check columns (only if tables resolved — avoids false positives on *)
    if "*" not in sql:
        used_cols = extract_columns_from_sql(sql)
        # Build column set for referenced tables only
        referenced_cols: Set[str] = set()
        for t in used_tables:
            original = schema_tables.get(t)
            if original and original in schema:
                for c in schema[original]:
                    referenced_cols.add(c["name"].lower())

        if referenced_cols:
            unknown_cols = [c for c in used_cols if c not in referenced_cols and c not in {"id"}]
            if unknown_cols:
                raise ValidationError(
                    f"Query references column(s) not found in schema: {', '.join(unknown_cols)}"
                )


def validate(sql: str, schema: Dict[str, List[dict]] = None) -> str:
    """
    Run all safety checks on the generated SQL.
    Allows SELECT, INSERT, UPDATE, DELETE.
    Blocks DROP, TRUNCATE, ALTER, etc.
    If schema is provided, also validates tables/columns (fix #5).
    """
    check_not_empty(sql)
    check_forbidden_keywords(sql)
    check_parseable(sql)
    check_single_statement(sql)
    if schema:
        validate_against_schema(sql, schema)
    return sql