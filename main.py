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
    build_join_graph, format_join_hints,
)
from queryease.generator import generate_sql, explain_sql
from queryease.validator import validate, ValidationError, is_write_query, is_complex_query
from queryease.judge import judge_sql
from queryease.executor import execute, ExecutionError
from queryease import formatter
from queryease.history import save_query, get_history

console = Console()

DB_ICONS = {
    "postgresql": "🐘",
    "mysql": "🐬",
    "sqlite": "📁",
}


def confirm_execution(sql: str) -> bool:
    console.print(Panel(
        "[bold yellow]This query will modify your database.[/bold yellow]\nType [bold]yes[/bold] to proceed or [bold]no[/bold] to cancel.",
        title="[bold yellow]⚠  Confirmation Required[/bold yellow]",
        border_style="yellow"
    ))
    answer = input("  Proceed? (yes/no): ").strip().lower()
    return answer in ("yes", "y")


def show_history(limit: int = 10):
    """Fix #7: Display query history."""
    entries = get_history(limit)
    if not entries:
        console.print("[dim]No query history found.[/dim]")
        return

    table = Table(title=f"Last {len(entries)} Queries", border_style="green", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Time", style="cyan", width=20)
    table.add_column("DB", style="magenta", width=10)
    table.add_column("Question", style="white")
    table.add_column("SQL Preview", style="green")

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


def run(question: str, refresh: bool = False, no_explain: bool = False):
    console.print()
    console.print(Panel(
        f"[bold white]{question}[/bold white]",
        title="[bold green]QueryEase[/bold green]",
        border_style="green"
    ))
    console.print()

    # Step 1: Validate config
    try:
        validate_config()
    except EnvironmentError as e:
        formatter.print_error(str(e))
        sys.exit(1)

    # Step 2: Auto-detect DB type
    try:
        dialect = get_dialect()
        icon = DB_ICONS.get(dialect, "🗄")
        formatter.print_step(f"Detected database: {icon} {dialect.upper()}")
    except Exception as e:
        formatter.print_error(f"Could not detect database type:\n{e}")
        sys.exit(1)

    # Step 3: Load schema
    if refresh:
        formatter.print_step("Refreshing schema from database...")
    elif cache_exists():
        formatter.print_step("Loading schema from cache...")
    else:
        formatter.print_step("Connecting to database (first run — building cache)...")

    try:
        schema, from_cache = get_schema(refresh=refresh)
    except Exception as e:
        formatter.print_error(f"Could not load schema:\n{e}")
        sys.exit(1)

    source = "[dim](from cache)[/dim]" if from_cache else "[dim](fetched from DB + cached)[/dim]"
    formatter.print_step(
        f"Schema ready — {len(schema)} table(s): {', '.join(schema.keys())} {source}"
    )

    # Fix #8: Build JOIN graph and include hints in schema prompt
    join_graph = build_join_graph(schema)
    join_hints = format_join_hints(join_graph) if join_graph else None
    schema_text = format_schema_for_prompt(schema, join_hints=join_hints)

    if join_graph:
        formatter.print_step(f"JOIN graph built — {sum(len(v) for v in join_graph.values()) // 2} relationship(s) detected")

    # Step 4: Generate SQL (dialect-aware)
    formatter.print_step(f"Generating {dialect.upper()} query with Groq...")
    try:
        sql = generate_sql(question, schema_text, dialect)
    except Exception as e:
        formatter.print_error(f"SQL generation failed:\n{e}")
        sys.exit(1)

    # Step 5: Validate (fix #5: pass schema for table/column check)
    formatter.print_step("Validating query...")
    try:
        validate(sql, schema=schema)
    except ValidationError as e:
        formatter.print_error(f"Validation failed:\n{e}")
        console.print(f"[dim]Generated SQL was:[/dim]\n{sql}")
        sys.exit(1)

    # Fix #4: Explain SQL
    if not no_explain:
        explanation = explain_sql(sql, question)
        if explanation:
            console.print()
            console.print(Panel(
                f"[italic]{explanation}[/italic]",
                title="[bold cyan]What this query does[/bold cyan]",
                border_style="cyan"
            ))

    console.print()
    formatter.print_sql(sql)
    console.print()

    # Step 6: LLM Judge for write or complex queries
    write = is_write_query(sql)
    complex_q = is_complex_query(sql)

    if write or complex_q:
        reason = "write operation" if write else "complex query"
        formatter.print_step(f"Sending to LLM judge ({reason})...")
        try:
            verdict = judge_sql(question, sql, schema_text)
        except Exception as e:
            formatter.print_error(f"Judge failed:\n{e}")
            sys.exit(1)

        if not verdict.approved:
            formatter.print_judge_warning(verdict.reason)
            if verdict.suggestion:
                console.print("[dim]Suggested fix:[/dim]")
                formatter.print_sql(verdict.suggestion)
                use_suggestion = input("\n  Use suggested SQL instead? (yes/no): ").strip().lower()
                if use_suggestion in ("yes", "y"):
                    sql = verdict.suggestion
                    console.print()
                else:
                    console.print("[dim]Cancelled.[/dim]")
                    sys.exit(0)
            else:
                console.print("[dim]No suggestion provided. Cancelled.[/dim]")
                sys.exit(0)
        else:
            formatter.print_judge_approved(verdict.reason)

    # Step 7: Confirm write queries
    if write:
        if not confirm_execution(sql):
            console.print("\n[dim]Cancelled.[/dim]")
            sys.exit(0)
        console.print()

    # Step 8: Execute
    formatter.print_step("Executing query...")
    try:
        result = execute(sql)
    except ExecutionError as e:
        formatter.print_error(str(e))
        sys.exit(1)

    # Step 9: Display
    console.print()
    if result.is_write():
        formatter.print_write_result(result)
    else:
        formatter.print_results(result)

    # Fix #7: Save to history
    try:
        result_summary = (
            f"{result.rowcount} row(s) affected"
            if result.is_write()
            else f"{len(result.rows)} row(s) returned"
        )
        save_query(question, sql, result_summary=result_summary, dialect=dialect)
    except Exception:
        pass  # History save failure should never crash the main flow


def main():
    args = sys.argv[1:]
    if not args:
        console.print("[bold red]Usage:[/bold red] python3 main.py \"your question here\"")
        console.print("[dim]       python3 main.py --refresh \"question\"    ← refresh schema cache[/dim]")
        console.print("[dim]       python3 main.py --history [N]           ← show last N queries (default 10)[/dim]")
        console.print("[dim]       python3 main.py --no-explain \"question\" ← skip SQL explanation[/dim]")
        sys.exit(1)

    refresh = False
    no_explain = False

    if "--refresh" in args:
        refresh = True
        args = [a for a in args if a != "--refresh"]

    if "--no-explain" in args:
        no_explain = True
        args = [a for a in args if a != "--no-explain"]

    # Fix #7: --history flag
    if "--history" in args:
        idx = args.index("--history")
        limit = 10
        if idx + 1 < len(args) and args[idx + 1].isdigit():
            limit = int(args[idx + 1])
            args.pop(idx + 1)
        args.pop(idx)
        show_history(limit)
        if not args:
            sys.exit(0)

    if not args:
        console.print("[bold red]Error:[/bold red] Please provide a question.")
        sys.exit(1)

    question = " ".join(args)
    run(question, refresh=refresh, no_explain=no_explain)


if __name__ == "__main__":
    main()
