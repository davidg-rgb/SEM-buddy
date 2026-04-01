"""CLI commands for client account management."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from src.accounts.manager import (
    create_account,
    list_accounts,
    get_account,
    remove_account,
    set_active_client,
    get_active_client,
)
from src.accounts.state import get_pipeline_state, get_next_stage
from src.utils.config import CLIENTS_DIR

accounts_app = typer.Typer(name="accounts", help="Manage client accounts.")
console = Console()


@accounts_app.command("list")
def list_cmd() -> None:
    """List all registered client accounts."""
    accounts = list_accounts()
    if not accounts:
        rprint("No accounts registered. Use [bold]sem accounts add[/bold] to create one.")
        return

    active = get_active_client()

    table = Table(title="Client Accounts", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Customer ID")
    table.add_column("Industry")
    table.add_column("Budget (SEK)", justify="right")
    table.add_column("Next Stage")
    table.add_column("Active", justify="center")

    for acct in accounts:
        is_active = acct.name == active
        active_marker = "[green]✓[/green]" if is_active else ""
        budget_str = str(acct.monthly_budget_sek) if acct.monthly_budget_sek else "—"
        industry_str = acct.industry or "—"

        try:
            next_stage = get_next_stage(CLIENTS_DIR / acct.name) or "complete"
        except Exception:
            next_stage = "—"

        table.add_row(
            acct.name,
            acct.customer_id,
            industry_str,
            budget_str,
            next_stage,
            active_marker,
        )

    console.print(table)


@accounts_app.command("add")
def add(
    name: str = typer.Argument(..., help="Client slug (kebab-case, used as directory name)"),
    customer_id: str = typer.Argument(..., help="Google Ads Customer ID (XXX-XXX-XXXX)"),
    industry: str = typer.Option(None, "--industry", "-i", help="Industry key"),
    budget: int = typer.Option(None, "--budget", "-b", help="Monthly budget in SEK"),
) -> None:
    """Register a new client account and create its directory structure."""
    try:
        create_account(name, customer_id, industry=industry, budget_sek=budget)
        rprint(f"[green]Added client '{name}' (Customer ID: {customer_id})[/green]")
    except ValueError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)


@accounts_app.command("remove")
def remove(
    name: str = typer.Argument(..., help="Client slug to remove"),
    no_archive: bool = typer.Option(
        False,
        "--no-archive",
        help="Delete permanently instead of archiving",
    ),
) -> None:
    """Remove (or archive) a client account."""
    typer.confirm(f"Remove client '{name}'?", abort=True)
    try:
        remove_account(name, archive=not no_archive)
        if no_archive:
            rprint(f"[green]Deleted client '{name}' permanently.[/green]")
        else:
            rprint(f"[green]Archived client '{name}' to clients/_archived/.[/green]")
    except FileNotFoundError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)


@accounts_app.command("switch")
def switch(
    name: str = typer.Argument(..., help="Client slug to set as the active client"),
) -> None:
    """Set the active client context."""
    try:
        set_active_client(name)
        rprint(f"[green]Active client: {name}[/green]")
    except FileNotFoundError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)


@accounts_app.command("info")
def info(
    name: str = typer.Argument(None, help="Client slug (defaults to active client)"),
) -> None:
    """Show detailed information for a client account."""
    if name is None:
        name = get_active_client()
    if name is None:
        rprint("[red]No active client. Use 'sem accounts switch <name>' or pass a client slug.[/red]")
        raise typer.Exit(1)

    try:
        acct = get_account(name)
    except FileNotFoundError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    # Build pipeline stage table
    stage_table = Table(show_header=True, header_style="bold", box=None)
    stage_table.add_column("Stage", style="bold")
    stage_table.add_column("Status")
    stage_table.add_column("Updated At")

    try:
        pipeline = get_pipeline_state(CLIENTS_DIR / name)
        stages = pipeline.get("stages", {})
        for stage_name, stage_data in stages.items():
            status = stage_data.get("status", "pending")
            updated = stage_data.get("updated_at") or "—"
            status_styled = _style_status(status)
            stage_table.add_row(stage_name, status_styled, str(updated))
    except FileNotFoundError:
        stage_table.add_row("—", "[yellow]No pipeline state found[/yellow]", "—")

    # Format budget and other optional fields
    budget_str = f"{acct.monthly_budget_sek:,} SEK" if acct.monthly_budget_sek else "Not set"
    industry_str = acct.industry or "Not set"
    website_str = acct.website_url or "Not set"
    contact_str = acct.contact_email or "Not set"
    created_str = acct.created_at.strftime("%Y-%m-%d %H:%M") if acct.created_at else "Unknown"

    details = (
        f"[bold]Display Name:[/bold]  {acct.display_name}\n"
        f"[bold]Customer ID:[/bold]   {acct.customer_id}\n"
        f"[bold]Industry:[/bold]      {industry_str}\n"
        f"[bold]Budget:[/bold]        {budget_str}\n"
        f"[bold]Website:[/bold]       {website_str}\n"
        f"[bold]Contact:[/bold]       {contact_str}\n"
        f"[bold]Created:[/bold]       {created_str}\n"
    )

    panel = Panel.fit(
        f"{details}\n[bold]Pipeline Status:[/bold]\n",
        title=f"[bold cyan]{acct.name}[/bold cyan]",
        border_style="cyan",
    )
    console.print(panel)
    console.print(stage_table)


def _style_status(status: str) -> str:
    """Return Rich-styled status string."""
    styles = {
        "completed": "[green]completed[/green]",
        "in_progress": "[yellow]in_progress[/yellow]",
        "failed": "[red]failed[/red]",
        "pending": "[dim]pending[/dim]",
    }
    return styles.get(status, status)
