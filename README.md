# QueryEase 🔍
![QueryEase Demo](assets/demo.gif)
**Query any SQL database in plain English.**

QueryEase converts natural language questions into SQL queries using Groq's LLM, executes them against your database, and returns results — all from your terminal.

```
$ python3 main.py "Show top 5 customers by total spending"

→ Detected database: 🐘 POSTGRESQL
→ Schema ready — 22 table(s) (from cache)
→ Generating POSTGRESQL query with Groq...

╭─ Generated SQL ──────────────────────────────────────────────╮
│ SELECT c.first_name, c.last_name,                            │
│        SUM(p.amount) AS total_spent                          │
│ FROM customer c                                              │
│ JOIN payment p ON c.customer_id = p.customer_id              │
│ GROUP BY c.customer_id                                       │
│ ORDER BY total_spent DESC                                    │
│ LIMIT 5                                                      │
╰──────────────────────────────────────────────────────────────╯

╭────────────────┬───────────────┬─────────────╮
│ first_name     │ last_name     │ total_spent │
├────────────────┼───────────────┼─────────────┤
│ Eleanor        │ Hunt          │ 211.55      │
│ Karl           │ Seal          │ 208.58      │
╰────────────────┴───────────────┴─────────────╯
  ⏱  18ms  |  5 rows
```

---

## Features

- **Natural language to SQL** — powered by Groq's `llama-3.3-70b-versatile`
- **Multi-database support** — PostgreSQL, MySQL, SQLite — auto-detected from URL
- **Schema caching** — schema fetched once, cached locally, auto-refreshes when DB changes
- **LLM judge** — complex queries and write operations are verified before execution
- **Correction loop** — if results are wrong, describe what you wanted and QueryEase fixes the SQL
- **Multi-turn chat** — follow-up questions with full conversation context (`--chat`)
- **Query history** — every query logged locally, viewable with `--history`
- **SQL explanation** — plain English description of what the generated SQL does
- **Write query support** — INSERT, UPDATE, DELETE with confirmation prompt
- **Prompt injection protection** — user input sanitized before hitting the LLM
- **Column descriptions** — annotate cryptic column names to improve LLM accuracy

---

## Requirements

- Python 3.9+
- A [Groq API key](https://console.groq.com) (free tier available)
- A running PostgreSQL, MySQL, or SQLite database

---

## Installation

### Option A — Run locally (recommended for development)

```bash
git clone https://github.com/bhavyashah09/QueryEase.git
cd QueryEase
pip install -r requirements.txt
```

### Option B — Install as a package

```bash
pip install -e .
# Then use anywhere:
queryease "Show all customers from Canada"
```

---

## Setup

**1. Create your `.env` file:**

```bash
cp .env.example .env
```

**2. Fill in your credentials:**

```env
# Groq API key — get one free at console.groq.com
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx

# Your database — pick one:
DATABASE_URL=postgresql://username:password@localhost:5432/mydb
# DATABASE_URL=mysql://username:password@localhost:3306/mydb
# DATABASE_URL=sqlite:///path/to/mydb.sqlite
```

**3. Run your first query:**

```bash
python3 main.py "Show all tables"
```

---

## Usage

### Basic query

```bash
python3 main.py "Show all customers from Canada"
python3 main.py "What are the top 5 products by revenue?"
python3 main.py "How many orders were placed last month?"
```

### Multi-turn chat mode

Have a conversation — QueryEase remembers context across turns:

```bash
python3 main.py --chat
```

```
[Turn 1] Ask: Show all customers from Canada
[Turn 2] Ask: Now show their rental history
[Turn 3] Ask: Filter to rentals from the last 6 months
[Turn 4] Ask: exit
```

### Write queries

QueryEase handles INSERT, UPDATE, DELETE with an LLM judge + confirmation:

```bash
python3 main.py "Add a new customer named Raj with email raj@gmail.com"
python3 main.py "Update the rental rate of all horror films to 3.99"
python3 main.py "Delete all rentals that were never returned"
```

### Other flags

```bash
# Force refresh schema cache
python3 main.py --refresh "Show all tables"

# Skip SQL explanation panel
python3 main.py --no-explain "Show top customers"

# View query history
python3 main.py --history
python3 main.py --history 20   # show last 20
```

---

## How it works

```
Your question
     ↓
Schema loaded from cache (or DB on first run)
     ↓
Groq LLM generates SQL (dialect-aware)
     ↓
Validator checks safety (no DROP/TRUNCATE, SELECT-only for reads)
     ↓
LLM Judge verifies complex queries and write operations
     ↓
Confirmation prompt for write queries
     ↓
SQL executed against your database
     ↓
Results displayed + explanation shown
     ↓
"Were these results correct?" → correction loop if needed
```

---

## Column Descriptions (optional)

For databases with cryptic column names, create `descriptions.json` in the project root:

```json
{
  "orders": {
    "rev_amt": "total revenue amount in dollars",
    "flg_status": "order status: 1=pending, 2=delivered, 3=cancelled"
  },
  "customers": {
    "flg_active": "1 if customer is active, 0 if churned"
  }
}
```

QueryEase injects these into the LLM prompt so it understands abbreviated column names.

---

## Supported Databases

| Database   | URL Format                                      |
|------------|-------------------------------------------------|
| PostgreSQL | `postgresql://user:pass@host:5432/dbname`       |
| MySQL      | `mysql://user:pass@host:3306/dbname`            |
| SQLite     | `sqlite:///path/to/file.db`                     |

---

## Project Structure

```
QueryEase/
├── main.py                    # CLI entry point
├── pyproject.toml             # Package config (pip install)
├── requirements.txt           # Dependencies
├── .env.example               # Environment template
├── descriptions.json.example  # Column descriptions template
├── sample_data.sql            # Sample ecommerce database
└── src/queryease/
    ├── cli.py                 # pip-installed entry point
    ├── config.py              # Config loader + validation
    ├── schema.py              # Schema extraction, caching, descriptions
    ├── generator.py           # SQL generation + correction + multi-turn
    ├── validator.py           # Safety validation + injection protection
    ├── judge.py               # LLM judge for complex/write queries
    ├── executor.py            # Query execution
    ├── formatter.py           # Terminal output formatting
    ├── history.py             # Query history tracking
    └── db/
        ├── __init__.py        # Auto-detects DB type from URL
        ├── base.py            # Abstract connector interface
        ├── postgres.py        # PostgreSQL connector
        ├── mysql.py           # MySQL connector
        └── sqlite.py          # SQLite connector
```

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## License

MIT — see [LICENSE](LICENSE) for details.
