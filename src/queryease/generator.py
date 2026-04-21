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


# Dialect-specific syntax tips sent to the LLM
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

# Fix #3: Max retries for LLM call
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.5  # seconds


def build_prompt(question: str, schema_text: str, dialect: str, previous_error: str = None) -> str:
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


def generate_sql(question: str, schema_text: str, dialect: str = "postgresql") -> str:
    """
    Fix #3: Generate SQL with retry logic and exponential backoff.
    On failure, retries up to MAX_RETRIES times, passing the error context back to the LLM.
    """
    client = get_client()
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            prompt = build_prompt(question, schema_text, dialect, previous_error=last_error)
            response = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are a {dialect.upper()} expert. Output only the raw SQL statement. "
                            "Never wrap INSERT/UPDATE/DELETE inside a SELECT. "
                            "No markdown, no explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1024,
            )
            return clean_sql(response.choices[0].message.content)

        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE ** attempt
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"SQL generation failed after {MAX_RETRIES} attempts. Last error: {last_error}"
                )


# Fix #4: Explain SQL in plain English
def explain_sql(sql: str, question: str) -> str:
    """
    Ask the LLM to explain what the SQL does in 1-2 sentences.
    Returns an explanation string, or empty string on failure.
    """
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
