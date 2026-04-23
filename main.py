"""QueryEase CLI - Query any SQL database in plain English."""

import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from queryease.config import validate_config
from queryease.schema import (
    get_schema, format_schema_for_prompt, cache_exists, get_dialect,
    build_join_graph, format_join_hints, load_descriptions, descriptions_exist,
)
from queryease.generator import (
    generate_sql, generate_sql_with_context, explain_sql,
    regenerate_sql, MAX_CORRECTIONS,
)
from queryease.validator import (
    validate, ValidationError, InjectionError,
    check_prompt_injection, is_write_query, is_complex_query,
)
from queryease.judge import judge_sql
from queryease.executor import execute, ExecutionError
from queryease import formatter
from queryease.history import save_query, get_history

console = Console()

DB_ICONS = {
    "postgresql": "🐘",
    "mysql":      "🐬",
    "sqlite":     "📁",
}


def confirm_execution(sql: str) -> bool:
    console.print(Panel(
        "[bold yellow]This query will modify your database.[/bold yellow]\n"
        "Type [bold]yes[/bold] to proceed or [bold]no[/bold] to cancel.",
        title="[bold yellow]⚠  Confirmation Required[/bold yellow]",
        border_style="yellow",
    ))
    return input("  Proceed? (yes/no): ").strip().lower() in ("yes", "y")


def show_history(limit: int = 10):
    entries = get_history(limit)
    if not entries:
        console.print("[dim]No query history found.[/dim]")
        return

    table = Table(title=f"Last {len(entries)} Queries", border_style="green", show_lines=True)
    table.add_column("#",          style="dim",     width=4)
    table.add_column("Time",       style="cyan",    width=20)
    table.add_column("DB",         style="magenta", width=10)
    table.add_column("Question",   style="white")
    table.add_column("SQL Preview",style="green")

    for entry in entries:
        sql_preview = entry.sql.replace("\n", " ")[:60] + ("..." if len(entry.sql) > 60 else "")
        table.add_row(
            str(entry.id),
            entry.formatted_time,
            entry.dialect.upper() if entry.dialect else "—",
            entry.question,
            sql_preview,
        )
    console.print()
    console.print(table)
    console.print()


# ─────────────────────────────────────────────
# SHARED SETUP (used by both single and chat mode)
# ─────────────────────────────────────────────

def setup(refresh: bool = False):
    """
    Validate config, detect DB, load schema and descriptions.
    Returns (dialect, schema, schema_text) or exits on error.
    """
    try:
        validate_config()
    except EnvironmentError as e:
        formatter.print_error(str(e), hint="Check that GROQ_API_KEY and DATABASE_URL are set in your .env file.")
        sys.exit(1)

    try:
        dialect = get_dialect()
        icon = DB_ICONS.get(dialect, "🗄")
        formatter.print_step(f"Detected database: {icon} {dialect.upper()}")
    except Exception as e:
        formatter.print_error(
            f"Could not detect database type:\n{e}",
            hint="Check that DATABASE_URL in your .env is valid (e.g. postgresql://user:pass@localhost/dbname).",
        )
        sys.exit(1)

    if refresh:
        formatter.print_step("Refreshing schema from database...")
    elif cache_exists():
        formatter.print_step("Loading schema from cache...")
    else:
        formatter.print_step("Connecting to database (first run — building cache)...")

    try:
        schema, from_cache = get_schema(refresh=refresh)
    except Exception as e:
        formatter.print_error(
            f"Could not load schema:\n{e}",
            hint="Try running with --refresh to force a fresh schema fetch.",
        )
        sys.exit(1)

    source = "[dim](from cache)[/dim]" if from_cache else "[dim](fetched from DB + cached)[/dim]"
    formatter.print_step(f"Schema ready — {len(schema)} table(s): {', '.join(schema.keys())} {source}")

    # #5 Column descriptions
    descriptions = load_descriptions()
    if descriptions:
        described_tables = list(descriptions.keys())
        formatter.print_step(
            f"Column descriptions loaded — {len(described_tables)} table(s) annotated: "
            f"{', '.join(described_tables)}"
        )

    join_graph  = build_join_graph(schema)
    join_hints  = format_join_hints(join_graph) if join_graph else None
    schema_text = format_schema_for_prompt(schema, join_hints=join_hints, descriptions=descriptions)

    if join_graph:
        formatter.print_step(
            f"JOIN graph built — "
            f"{sum(len(v) for v in join_graph.values()) // 2} relationship(s) detected"
        )

    return dialect, schema, schema_text


# ─────────────────────────────────────────────
# EXECUTE ONE QUERY (shared between single + chat)
# ─────────────────────────────────────────────

def execute_query(
    question: str,
    schema_text: str,
    dialect: str,
    schema: dict,
    no_explain: bool = False,
    history: list = None,       # None = single mode, list = chat mode
) -> dict:
    """
    Generate → validate → judge → execute one question.
    Returns a history entry dict {"question", "sql", "result"} on success.
    Returns None if user cancels.
    """
    history = history or []

    # Prompt injection check
    try:
        check_prompt_injection(question)
    except InjectionError as e:
        formatter.print_injection_error(str(e))
        return None

    # Generate SQL
    formatter.print_step(f"Generating {dialect.upper()} query with Groq...")
    try:
        if history:
            # #8 Multi-turn: pass conversation history for context
            sql = generate_sql_with_context(question, schema_text, dialect, history)
        else:
            sql = generate_sql(question, schema_text, dialect)
    except Exception as e:
        formatter.print_error(
            f"SQL generation failed:\n{e}",
            hint="Check your GROQ_API_KEY is valid and you have available API credits.",
        )
        return None

    # Validate
    formatter.print_step("Validating query...")
    try:
        validate(sql, schema=schema)
    except ValidationError as e:
        formatter.print_error(
            f"Validation failed:\n{e}",
            hint="Try rephrasing your question, or run with --refresh if your schema has changed.",
        )
        console.print(f"[dim]Generated SQL was:[/dim]\n{sql}")
        return None

    # Explain
    if not no_explain:
        explanation = explain_sql(sql, question)
        if explanation:
            console.print()
            console.print(Panel(
                f"[italic]{explanation}[/italic]",
                title="[bold cyan]What this query does[/bold cyan]",
                border_style="cyan",
            ))

    console.print()
    formatter.print_sql(sql)
    console.print()

    # LLM Judge for write or complex queries
    write     = is_write_query(sql)
    complex_q = is_complex_query(sql)

    if write or complex_q:
        reason = "write operation" if write else "complex query"
        formatter.print_step(f"Sending to LLM judge ({reason})...")
        try:
            verdict = judge_sql(question, sql, schema_text)
        except Exception as e:
            formatter.print_error(f"Judge failed:\n{e}", hint="Check your GROQ_API_KEY and network connection.")
            return None

        if not verdict.approved:
            formatter.print_judge_warning(verdict.reason)
            if verdict.suggestion:
                console.print("[dim]Suggested fix:[/dim]")
                formatter.print_sql(verdict.suggestion)
                if input("\n  Use suggested SQL instead? (yes/no): ").strip().lower() in ("yes", "y"):
                    sql = verdict.suggestion
                    console.print()
                else:
                    console.print("[dim]Cancelled.[/dim]")
                    return None
            else:
                feedback = f"The LLM judge flagged this issue: {verdict.reason}"
                formatter.print_step("Regenerating based on judge feedback...")
                try:
                    sql = regenerate_sql(question, schema_text, dialect, sql, feedback)
                    validate(sql, schema=schema)
                except Exception as err:
                    formatter.print_error(f"Regeneration failed:\n{err}")
                    return None
                console.print()
                formatter.print_sql(sql)
                console.print()
        else:
            formatter.print_judge_approved(verdict.reason)

    # Confirm write queries
    if write:
        if not confirm_execution(sql):
            console.print("\n[dim]Cancelled.[/dim]")
            return None
        console.print()

    # Execute with correction loop
    for correction in range(MAX_CORRECTIONS + 1):
        formatter.print_step("Executing query...")
        try:
            result = execute(sql)
        except ExecutionError as e:
            console.print()
            formatter.print_error(str(e))
            if correction >= MAX_CORRECTIONS:
                console.print("[dim]Max corrections reached. Giving up.[/dim]")
                return None

            console.print(Panel(
                f"[bold yellow]The query failed with a database error.[/bold yellow]\n"
                f"[dim]{e}[/dim]\n\n"
                "Describe what you actually wanted, or press Enter to let QueryEase auto-fix.",
                title="[bold yellow]✦ Correction[/bold yellow]",
                border_style="yellow",
            ))
            user_feedback = input("  Feedback (or Enter to auto-fix): ").strip()
            feedback = user_feedback if user_feedback else f"Execution failed with error: {e}"

            formatter.print_step("Regenerating query...")
            try:
                sql = regenerate_sql(question, schema_text, dialect, sql, feedback)
                validate(sql, schema=schema)
            except Exception as err:
                formatter.print_error(f"Regeneration failed:\n{err}")
                return None

            console.print()
            formatter.print_sql(sql)
            console.print()
            continue

        # Successful execution
        console.print()
        if result.is_write():
            formatter.print_write_result(result)
        else:
            formatter.print_results(result)

        result_summary = (
            f"{result.rows_affected} row(s) affected"
            if result.is_write()
            else f"{result.row_count} row(s) returned"
        )

        try:
            save_query(question, sql, result_summary=result_summary, dialect=dialect)
        except Exception:
            pass

        # Ask if results were correct (skip for write queries)
        if not write and correction < MAX_CORRECTIONS:
            console.print()
            if input("  ✓ Were these results correct? (yes/no): ").strip().lower() in ("no", "n"):
                console.print()
                console.print(Panel(
                    "Describe what was wrong or what you actually wanted:",
                    title="[bold yellow]✦ Correction[/bold yellow]",
                    border_style="yellow",
                ))
                feedback = input("  Feedback: ").strip()
                if not feedback:
                    console.print("[dim]No feedback given. Keeping result.[/dim]")
                    # FIX #8: build and return the entry even when user skips feedback
                    result_data = None
                    if not result.is_write() and result.rows:
                        try:
                            result_data = result.rows[:20]
                        except Exception:
                            result_data = None
                    return {
                        "question": question,
                        "sql": sql,
                        "result": result_summary,
                        "result_data": result_data,
                    }
                formatter.print_step("Regenerating query...")
                try:
                    sql = regenerate_sql(question, schema_text, dialect, sql, feedback)
                    validate(sql, schema=schema)
                except Exception as err:
                    formatter.print_error(f"Regeneration failed:\n{err}")
                    return None
                console.print()
                formatter.print_sql(sql)
                console.print()
                continue

        # FIX #8: return statement is now BEFORE break, so it always runs on success
        result_data = None
        if not result.is_write() and result.rows:
            try:
                result_data = result.rows[:20]
            except Exception:
                result_data = None

        return {
            "question": question,
            "sql": sql,
            "result": result_summary,
            "result_data": result_data,
        }

    # Fell through all corrections without returning — should not happen
    return None


# ─────────────────────────────────────────────
# SINGLE QUERY MODE
# ─────────────────────────────────────────────

def run(question: str, refresh: bool = False, no_explain: bool = False):
    console.print()
    console.print(Panel(
        f"[bold white]{question}[/bold white]",
        title="[bold green]QueryEase[/bold green]",
        border_style="green",
    ))
    console.print()

    dialect, schema, schema_text = setup(refresh=refresh)
    execute_query(question, schema_text, dialect, schema, no_explain=no_explain)


# ─────────────────────────────────────────────
# #8 MULTI-TURN CHAT MODE
# ─────────────────────────────────────────────

def run_chat(refresh: bool = False, no_explain: bool = False):
    """
    Interactive multi-turn session.

    The LLM remembers previous questions and SQL within the session,
    so you can say things like:
      > Show customers from Canada
      > Now show their orders
      > Filter to only delivered ones
    """
    console.print()
    console.print(Panel(
        "[bold white]QueryEase Chat Mode[/bold white]\n"
        "[dim]Ask follow-up questions — the LLM remembers context.\n"
        "Type [bold]exit[/bold] or [bold]quit[/bold] to end the session.\n"
        "Type [bold]clear[/bold] to reset conversation history.[/dim]",
        title="[bold green]💬 QueryEase[/bold green]",
        border_style="green",
    ))
    console.print()

    dialect, schema, schema_text = setup(refresh=refresh)

    # Conversation history kept in memory for this session only
    # Format: [{"question": str, "sql": str, "result": str}, ...]
    history = []
    turn = 1

    while True:
        try:
            question = input(f"  [Turn {turn}] Ask: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if not question:
            continue

        if question.lower() in ("exit", "quit", "q"):
            console.print("[dim]Session ended.[/dim]")
            break

        if question.lower() == "clear":
            history.clear()
            turn = 1
            console.print("[dim]Conversation history cleared.[/dim]\n")
            continue

        if question.lower() == "history":
            if not history:
                console.print("[dim]No history in this session yet.[/dim]\n")
            else:
                for i, entry in enumerate(history, 1):
                    console.print(f"[dim]Turn {i}: {entry['question']}[/dim]")
                    console.print(f"[dim]  SQL: {entry['sql'][:80]}...[/dim]\n")
            continue

        console.print()
        entry = execute_query(
            question,
            schema_text,
            dialect,
            schema,
            no_explain=no_explain,
            history=history,        # pass full history so LLM has context
        )

        if entry:
            history.append(entry)
            # Keep last 10 turns in memory — avoids prompt getting too long
            if len(history) > 10:
                history.pop(0)
            turn += 1

        console.print()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        console.print("[bold red]Usage:[/bold red] python3 main.py \"your question here\"")
        console.print("[dim]       python3 main.py --chat               ← multi-turn session[/dim]")
        console.print("[dim]       python3 main.py --refresh \"question\" ← refresh schema cache[/dim]")
        console.print("[dim]       python3 main.py --history [N]        ← show last N queries[/dim]")
        console.print("[dim]       python3 main.py --no-explain          ← skip SQL explanation[/dim]")
        sys.exit(1)

    refresh    = False
    no_explain = False
    chat_mode  = False

    if "--refresh" in args:
        refresh = True
        args = [a for a in args if a != "--refresh"]

    if "--no-explain" in args:
        no_explain = True
        args = [a for a in args if a != "--no-explain"]

    if "--chat" in args:
        chat_mode = True
        args = [a for a in args if a != "--chat"]

    if "--history" in args:
        idx = args.index("--history")
        limit = 10
        if idx + 1 < len(args) and args[idx + 1].isdigit():
            limit = int(args[idx + 1])
            args.pop(idx + 1)
        args.pop(idx)
        show_history(limit)
        if not args and not chat_mode:
            sys.exit(0)

    if chat_mode:
        run_chat(refresh=refresh, no_explain=no_explain)
        sys.exit(0)

    if not args:
        console.print("[bold red]Error:[/bold red] Please provide a question.")
        sys.exit(1)

    question = " ".join(args)
    run(question, refresh=refresh, no_explain=no_explain)


if __name__ == "__main__":
    main()