"""Configuration loader for QueryEase."""

import os
from dotenv import load_dotenv

load_dotenv()

# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Database — single URL, auto-detected
DATABASE_URL = os.getenv("DATABASE_URL")


def validate_config():
    """Check all required env variables are set."""
    errors = []
    if not GROQ_API_KEY:
        errors.append("GROQ_API_KEY is missing")
    if not DATABASE_URL:
        errors.append("DATABASE_URL is missing (e.g. postgresql://user:pass@localhost:5432/mydb)")

    if errors:
        raise EnvironmentError(
            "Missing required config:\n" + "\n".join(f"  - {e}" for e in errors)
        )
