"""LLM Judge - verifies complex or write SQL queries before execution."""

from groq import Groq
from . import config

_client = None

def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


class JudgeResult:
    def __init__(self, approved: bool, reason: str, suggestion: str = ""):
        self.approved = approved
        self.reason = reason
        self.suggestion = suggestion


def judge_sql(question: str, sql: str, schema_text: str) -> JudgeResult:
    """
    Ask the LLM to verify if the generated SQL correctly answers the question.

    Returns a JudgeResult with approved=True/False and a reason.
    """
    prompt = f"""You are a strict SQL reviewer. Your job is to verify if a SQL query correctly and safely answers the user's question.

DATABASE SCHEMA:
{schema_text}

USER'S QUESTION:
{question}

GENERATED SQL:
{sql}

Review the SQL and respond in this exact format:
APPROVED: yes or no
REASON: one sentence explaining why
SUGGESTION: (only if not approved) a corrected SQL query

Rules for approval:
- SQL must correctly answer the question
- SQL must only touch tables/columns that exist in the schema
- For UPDATE/DELETE: must have a WHERE clause (never update/delete all rows blindly)
- For INSERT: values must match column types
- Logic must be correct (right JOINs, right filters, right aggregations)
"""

    client = get_client()
    response = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a strict SQL reviewer. Always respond in the exact format requested."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=512,
    )

    raw = response.choices[0].message.content.strip()

    # Parse the response
    approved = False
    reason = "Could not parse judge response."
    suggestion = ""

    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("APPROVED:"):
            approved = "yes" in line.lower()
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[-1].strip()
        elif line.upper().startswith("SUGGESTION:"):
            suggestion = line.split(":", 1)[-1].strip()

    return JudgeResult(approved=approved, reason=reason, suggestion=suggestion)
