"""SQL Generator - uses Groq LLM to convert natural language to SQL."""

import re
import time
from groq import Groq
from . import config

_client = None

def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


DIALECT_HINTS = {
    "postgresql": (
        "Use PostgreSQL syntax. "
        "Use ILIKE for case-insensitive text matching. "
        "Use INTERVAL for date arithmetic (e.g. NOW() - INTERVAL '7 days'). "
        "Use SERIAL for auto-increment."
    ),
    "mysql": (
        "Use MySQL syntax. "
        "Use backticks for identifiers if needed. "
        "Use DATE_SUB for date arithmetic. "
        "Use AUTO_INCREMENT for auto-increment."
    ),
    "sqlite": (
        "Use SQLite syntax. "
        "Use LIKE for text matching (case-insensitive by default for ASCII). "
        "Use datetime('now') for current timestamp. "
        "Use INTEGER PRIMARY KEY for auto-increment."
    ),
}

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.5
MAX_CORRECTIONS = 3


def build_prompt(
    question: str,
    schema_text: str,
    dialect: str,
    previous_error: str = None,
) -> str:
    hint = DIALECT_HINTS.get(dialect, "Use standard SQL syntax.")
    error_context = ""
    if previous_error:
        error_context = f"\nNOTE: A previous attempt failed with this error — fix it:\n{previous_error}\n"

    return f"""You are an expert {dialect.upper()} SQL generator.

Convert the user's question into a valid {dialect.upper()} query.

DATABASE SCHEMA:
{schema_text}

DIALECT NOTES:
{hint}
{error_context}
RULES:
1. Generate SELECT, INSERT, UPDATE, or DELETE based on what the question asks.
2. NEVER generate DROP, TRUNCATE, ALTER, or CREATE.
3. For UPDATE and DELETE always include a WHERE clause — never modify all rows blindly.
4. IMPORTANT: Output the raw SQL statement directly.
   Wrong:  SELECT 'INSERT INTO ...'
   Right:  INSERT INTO ...
5. No markdown, no code fences, no explanation — just the raw SQL.

QUESTION:
{question}

SQL:"""


def _format_row(row) -> str:
    """
    Safely format a result row for the context prompt.
    Handles RealDictRow, plain dict, named tuples, and bare tuples.
    FIX #5: guard against dict(row) crashing on tuple rows.
    """
    try:
        return str(dict(row))
    except (TypeError, ValueError):
        try:
            # Named tuple — has _asdict()
            return str(row._asdict())
        except AttributeError:
            # Plain tuple or anything else
            return str(row)


def build_context_prompt(
    question: str,
    schema_text: str,
    dialect: str,
    history: list,
) -> str:
    """
    Build a prompt that includes conversation history for multi-turn sessions.

    history is a list of dicts:
    [
        {"question": "Show customers from Canada", "sql": "SELECT ...", "result": "5 rows",
         "result_data": [<row>, ...]},
        {"question": "Now show their orders",      "sql": "SELECT ...", "result": "12 rows"},
    ]

    The LLM uses this to understand references like "their", "those", "now filter by X".
    """
    hint = DIALECT_HINTS.get(dialect, "Use standard SQL syntax.")

    # Format the conversation history into readable context
    history_text = ""
    if history:
        history_text = "CONVERSATION HISTORY (use this to understand references like 'their', 'those', 'now filter'):\n"
        for i, entry in enumerate(history, 1):
            history_text += f"\nTurn {i}:\n"
            history_text += f"  Question: {entry['question']}\n"
            history_text += f"  SQL: {entry['sql']}\n"
            history_text += f"  Result: {entry.get('result', 'executed successfully')}\n"
            result_data = entry.get("result_data")
            if result_data:
                # FIX #5: use safe _format_row() instead of bare dict(row)
                history_text += "  Actual data returned:\n"
                for row in result_data[:10]:  # limit to 10 rows in prompt
                    history_text += f"    {_format_row(row)}\n"
        history_text += "\n"

    return f"""You are an expert {dialect.upper()} SQL generator in a multi-turn conversation.

The user is asking follow-up questions. Use the conversation history to understand
what "they", "those", "their", "same", "now filter" refer to.

DATABASE SCHEMA:
{schema_text}

DIALECT NOTES:
{hint}

{history_text}RULES:
1. Generate SELECT, INSERT, UPDATE, or DELETE based on what the question asks.
2. NEVER generate DROP, TRUNCATE, ALTER, or CREATE.
3. For UPDATE and DELETE always include a WHERE clause.
4. Use conversation history to resolve references like "their orders" or "those customers".
5. Output raw SQL only — no markdown, no explanation.

CURRENT QUESTION:
{question}

SQL:"""


def clean_sql(raw: str) -> str:
    """Strip markdown and extract the actual SQL statement."""
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("```", "").strip()

    lines = raw.splitlines()
    VALID_STARTS = ("SELECT", "INSERT", "UPDATE", "DELETE")
    sql_lines = []
    started = False
    for line in lines:
        if not started and any(line.strip().upper().startswith(k) for k in VALID_STARTS):
            started = True
        if started:
            sql_lines.append(line)

    return "\n".join(sql_lines).strip() if sql_lines else raw


def _call_groq(messages: list) -> str:
    """Shared Groq call with retry logic."""
    client = get_client()
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
            return clean_sql(response.choices[0].message.content)
        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_BASE ** attempt)
            else:
                raise RuntimeError(
                    f"Groq call failed after {MAX_RETRIES} attempts. Last error: {last_error}"
                )


def generate_sql(
    question: str,
    schema_text: str,
    dialect: str = "postgresql",
    previous_error: str = None,
) -> str:
    """Generate SQL from a single question (no conversation context)."""
    prompt = build_prompt(question, schema_text, dialect, previous_error)
    return _call_groq([
        {
            "role": "system",
            "content": (
                f"You are a {dialect.upper()} expert. Output only the raw SQL statement. "
                "Never wrap INSERT/UPDATE/DELETE inside a SELECT. "
                "No markdown, no explanation."
            ),
        },
        {"role": "user", "content": prompt},
    ])


def generate_sql_with_context(
    question: str,
    schema_text: str,
    dialect: str,
    history: list,
) -> str:
    """
    #8 Multi-turn: Generate SQL using conversation history as context.
    Used in --chat mode when the user refers to previous results.
    """
    prompt = build_context_prompt(question, schema_text, dialect, history)
    return _call_groq([
        {
            "role": "system",
            "content": (
                f"You are a {dialect.upper()} expert in a multi-turn conversation. "
                "Use conversation history to resolve references. "
                "Output only raw SQL. No markdown, no explanation."
            ),
        },
        {"role": "user", "content": prompt},
    ])


def regenerate_sql(
    question: str,
    schema_text: str,
    dialect: str,
    previous_sql: str,
    feedback: str,
) -> str:
    """Correction loop: regenerate SQL given what was wrong."""
    hint = DIALECT_HINTS.get(dialect, "Use standard SQL syntax.")
    prompt = f"""You are an expert {dialect.upper()} SQL generator.

The user asked a question and you generated SQL, but it was wrong.
Fix it based on the feedback provided.

ORIGINAL QUESTION:
{question}

DATABASE SCHEMA:
{schema_text}

DIALECT NOTES:
{hint}

PREVIOUS SQL (incorrect):
{previous_sql}

WHAT WAS WRONG / USER FEEDBACK:
{feedback}

Output only the corrected raw SQL. No markdown, no explanation.

SQL:"""

    return _call_groq([
        {
            "role": "system",
            "content": (
                f"You are a {dialect.upper()} expert fixing incorrect SQL. "
                "Output only the corrected raw SQL. No markdown, no explanation."
            ),
        },
        {"role": "user", "content": prompt},
    ])


def explain_sql(sql: str, question: str) -> str:
    """Ask the LLM to explain what the SQL does in 1-2 sentences."""
    client = get_client()
    try:
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a SQL teacher. Explain what a SQL query does in plain English, "
                        "in 1-2 concise sentences. No jargon. No markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Original question: {question}\n\n"
                        f"SQL:\n{sql}\n\n"
                        "Explain what this SQL does in 1-2 sentences:"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""