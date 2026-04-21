# QueryEase

Query your SQL database in plain English.

## Features

- Natural language to SQL conversion using LLM (Groq)
- Supports PostgreSQL, MySQL, and SQLite
- Schema caching for faster subsequent queries
- Query validation and safety checks
- LLM judge for write/complex queries
- Query history tracking

## Installation

```bash
pip install -r requirements.txt
```

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your database credentials and Groq API key:
   ```
   GROQ_API_KEY=your_api_key_here
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   ```

## Usage

```bash
# Basic query
python3 main.py "Show me all users who ordered in the last week"

# Refresh schema cache
python3 main.py --refresh "List all tables and their row counts"

# View query history
python3 main.py --history
```

## Project Structure

```
QueryEase/
├── main.py              # CLI entry point
├── requirements.txt     # Python dependencies
├── .env.example        # Environment template
├── sample_data.sql     # Sample SQL data
└── src/queryease/
    ├── config.py       # Configuration validation
    ├── schema.py       # Schema extraction and caching
    ├── generator.py    # SQL generation with LLM
    ├── validator.py    # Query validation
    ├── judge.py        # LLM-based query safety check
    ├── executor.py     # Query execution
    ├── formatter.py    # Output formatting
    └── history.py      # Query history management
```

## License

MIT
