"""Formatter - displays query results beautifully in the terminal."""

from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel
from rich import box
from rich.text import Text
from .executor import QueryResult

console = Console()

# Max rows to display before truncating
MAX_DISPLAY_ROWS = 50


def print_sql(sql: str):
    """Print the generated SQL with syntax highlighting."""
    syntax = Syntax(sql, "sql", theme="monokai", word_wrap=True)
    console.print(Panel(syntax, title="[bold cyan]Generated SQL[/bold cyan]", border_style="cyan"))


def print_results(result: QueryResult):
    """Print query results as a rich table."""

    if result.is_empty():
        console.print(Panel(
            "[yellow]No rows returned.[/yellow]",
            title="[bold]Results[/bold]",
            border_style="yellow"
        ))
        _print_stats(result)
        return

    # Build table
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="bright_black",
        row_styles=["", "dim"],  # alternating row style
    )

    # Add columns
    for col in result.columns:
        table.add_column(str(col), overflow="fold", max_width=40)

    # Add rows (truncated if too many)
    display_rows = result.rows[:MAX_DISPLAY_ROWS]
    for row in display_rows:
        table.add_row(*[str(v) if v is not None else "[dim]NULL[/dim]" for v in row.values()])

    console.print(table)

    # Warn if truncated
    if result.row_count > MAX_DISPLAY_ROWS:
        console.print(
            f"[yellow]  ⚠  Showing {MAX_DISPLAY_ROWS} of {result.row_count} rows[/yellow]"
        )

    _print_stats(result)


def _print_stats(result: QueryResult):
    """Print execution stats below the table."""
    stats = Text()
    stats.append(f"  ⏱  {result.execution_time_ms}ms", style="dim")
    stats.append("  |  ", style="dim")
    stats.append(f"{result.row_count} row{'s' if result.row_count != 1 else ''}", style="bold green")
    console.print(stats)
    console.print()


def print_error(message: str, hint: str = None):
    """Print an error message in a styled panel, with an optional actionable hint."""
    body = f"[red]{message}[/red]"
    if hint:
        body += f"\n\n[yellow]💡 {hint}[/yellow]"
    console.print(Panel(
        body,
        title="[bold red]Error[/bold red]",
        border_style="red"
    ))


def print_injection_error(message: str):
    """Print a prompt injection warning panel."""
    console.print(Panel(
        f"[bold red]🚫 Blocked:[/bold red] [red]{message}[/red]",
        title="[bold red]⚠ Prompt Injection Detected[/bold red]",
        border_style="red"
    ))


def print_step(message: str):
    """Print a progress step (e.g. 'Connecting...', 'Generating SQL...')."""
    console.print(f"[dim]→ {message}[/dim]")


def print_write_result(result):
    """Print result of INSERT/UPDATE/DELETE."""
    first_word = result.sql.strip().split()[0].upper()
    action = {"INSERT": "inserted", "UPDATE": "updated", "DELETE": "deleted"}.get(first_word, "affected")
    console.print(Panel(
        f"[bold green]✓ {result.rows_affected} row(s) {action} successfully[/bold green]",
        title="[bold]Result[/bold]",
        border_style="green"
    ))
    _print_stats(result)


def print_judge_warning(reason: str):
    """Print a warning when LLM judge flags something."""
    console.print(Panel(
        f"[yellow]{reason}[/yellow]",
        title="[bold yellow]⚠ Judge Warning[/bold yellow]",
        border_style="yellow"
    ))


def print_judge_approved(reason: str):
    """Print approval message from LLM judge."""
    console.print(f"[dim green]✓ Judge approved: {reason}[/dim green]")
    console.print()
