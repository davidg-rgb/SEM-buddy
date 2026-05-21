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
    customer_id: str = typer.Argument(
        None,
        help="Google Ads Customer ID (XXX-XXX-XXXX). Omit when using --create-remote.",
    ),
    industry: str = typer.Option(None, "--industry", "-i", help="Industry key"),
    budget: int = typer.Option(None, "--budget", "-b", help="Monthly budget in SEK"),
    verify_mcc: bool = typer.Option(
        False, "--verify", help="Verify account is accessible under MCC via Google Ads API"
    ),
    create_remote: bool = typer.Option(
        False,
        "--create-remote",
        help="Create a new Google Ads account under the configured MCC via API.",
    ),
    descriptive_name: str = typer.Option(
        None,
        "--descriptive-name",
        help="Descriptive name for the new account (used with --create-remote).",
    ),
    currency: str = typer.Option(
        "SEK", "--currency", help="Currency code for the new account (e.g. SEK, USD)."
    ),
    timezone: str = typer.Option(
        "Europe/Stockholm",
        "--timezone",
        help="IANA timezone for the new account.",
    ),
    admin_emails: list[str] = typer.Option(
        None,
        "--admin-email",
        help="Email address to invite as ADMIN (repeatable).",
    ),
) -> None:
    """Register a new client account and create its directory structure."""
    if create_remote:
        # Provision the remote account via the Google Ads API
        from src.apis.google_ads import create_customer_client, invite_admin
        from src.utils.config_manager import get_value

        mcc_id = get_value("mcc_customer_id")
        if not mcc_id:
            rprint(
                "[red]No MCC configured. Run `sem config set mcc_customer_id <id>` first.[/red]"
            )
            raise typer.Exit(1)
        if not descriptive_name:
            descriptive_name = name.replace("-", " ").title()
        rprint(
            f"Creating remote Google Ads account [bold]{descriptive_name}[/bold] "
            f"under MCC {mcc_id} ..."
        )
        try:
            customer_id = create_customer_client(
                mcc_id=mcc_id,
                descriptive_name=descriptive_name,
                currency_code=currency,
                time_zone=timezone,
            )
        except Exception as exc:
            rprint(f"[red]Failed to create remote account: {exc}[/red]")
            raise typer.Exit(1)
        rprint(f"[green]Created remote account: {customer_id}[/green]")
    else:
        if not customer_id:
            rprint(
                "[red]Either provide a CUSTOMER_ID positional argument or pass --create-remote.[/red]"
            )
            raise typer.Exit(1)

    try:
        create_account(name, customer_id, industry=industry, budget_sek=budget)
        rprint(f"[green]Added client '{name}' (Customer ID: {customer_id})[/green]")
    except ValueError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    if admin_emails:
        from src.apis.google_ads import invite_admin
        for email in admin_emails:
            try:
                resource = invite_admin(customer_id, email, access_role="ADMIN")
                rprint(f"[green]Invited {email} as ADMIN ({resource}).[/green]")
            except Exception as exc:
                rprint(f"[yellow]Could not invite {email}: {exc}[/yellow]")

    if verify_mcc:
        _verify_mcc_access(customer_id)


@accounts_app.command("invite")
def invite(
    name: str = typer.Argument(..., help="Client slug (use 'sem accounts list' to see)"),
    email: str = typer.Argument(..., help="Email address to invite"),
    role: str = typer.Option(
        "ADMIN",
        "--role",
        help="Access role: ADMIN | STANDARD | READ_ONLY | EMAIL_ONLY",
    ),
) -> None:
    """Invite an email to a client's Google Ads account."""
    try:
        acct = get_account(name)
    except FileNotFoundError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    from src.apis.google_ads import invite_admin

    try:
        resource = invite_admin(acct.customer_id, email, access_role=role.upper())
        rprint(f"[green]Invited {email} as {role.upper()} to {acct.customer_id}.[/green]")
        rprint(f"[dim]{resource}[/dim]")
    except ValueError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        rprint(f"[red]Failed to invite {email}: {exc}[/red]")
        raise typer.Exit(1)


def _verify_mcc_access(customer_id: str) -> bool:
    """Verify customer_id is reachable through the configured MCC.

    Queries the MCC's customer_client tree via GoogleAdsService.search_stream
    using the MCC as login_customer_id. This is the only reliable way to
    confirm sub-account access — list_accessible_customers only returns
    top-level managers the user can sign in as, not sub-accounts under them.

    Prints a styled result line. Returns True on confirmed access, False on
    any error or absence.
    """
    try:
        from src.auth.google_ads_auth import get_google_ads_client
        from src.utils.config_manager import get_value

        mcc_id = get_value("mcc_customer_id")
        if not mcc_id:
            rprint("[yellow]No MCC configured. Run `sem config set mcc_customer_id <id>` first.[/yellow]")
            return False

        client = get_google_ads_client()
        ga_service = client.get_service("GoogleAdsService")
        clean_id = customer_id.replace("-", "")
        clean_mcc = mcc_id.replace("-", "")

        # customer_client lists every customer reachable beneath the MCC, including itself
        query = """
            SELECT
              customer_client.id,
              customer_client.manager,
              customer_client.test_account,
              customer_client.status,
              customer_client.descriptive_name
            FROM customer_client
        """
        stream = ga_service.search_stream(customer_id=clean_mcc, query=query)
        for batch in stream:
            for row in batch.results:
                cc = row.customer_client
                if str(cc.id) == clean_id:
                    role = "manager" if cc.manager else "ad account"
                    test_marker = " · test" if cc.test_account else ""
                    rprint(
                        f"[green]Verified: {customer_id} reachable under MCC {mcc_id} "
                        f"({role}{test_marker}, status={cc.status.name}).[/green]"
                    )
                    return True

        rprint(
            f"[yellow]Warning: {customer_id} not found in MCC {mcc_id}'s sub-account tree. "
            f"Check that the account is linked to this MCC.[/yellow]"
        )
        return False
    except Exception as exc:
        rprint(f"[yellow]Could not verify MCC access: {exc}[/yellow]")
        rprint("[dim]Confirm `sem auth login` has run and developer_token + mcc_customer_id are set.[/dim]")
        return False


@accounts_app.command("verify")
def verify(
    name: str = typer.Argument(None, help="Client slug to verify (defaults to active client)"),
) -> None:
    """Verify a client account is accessible under your MCC via the Google Ads API."""
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

    rprint(f"Verifying [bold]{name}[/bold] (Customer ID: {acct.customer_id}) ...")
    ok = _verify_mcc_access(acct.customer_id)
    if not ok:
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
