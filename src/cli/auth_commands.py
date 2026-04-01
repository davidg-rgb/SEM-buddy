"""CLI commands for OAuth authentication lifecycle."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

from src.auth.oauth import run_oauth_flow
from src.auth.credentials import store_tokens, load_tokens, clear_tokens
from src.auth.token_refresh import check_expiry
from src.auth import AuthError
from src.utils.config_manager import CONFIG_DIR
from src.utils import config_manager

auth_app = typer.Typer(name="auth", help="OAuth authentication and token management.")
console = Console()

_CLIENT_SECRET_PATH = CONFIG_DIR / "credentials" / "client_secret.json"


@auth_app.command("setup")
def setup() -> None:
    """Print a step-by-step Google Cloud project setup guide."""
    console.print(
        Panel(
            "[bold cyan]SEM Master — Google Cloud & Google Ads API Setup Guide[/bold cyan]",
            border_style="cyan",
        )
    )

    steps = [
        (
            "1. Create a Google Cloud project",
            "Go to [link=https://console.cloud.google.com/]https://console.cloud.google.com/[/link]\n"
            "   Click [bold]New Project[/bold] and name it [bold]SEM Master[/bold].",
        ),
        (
            "2. Enable the Google Ads API",
            "In your project, go to [bold]APIs & Services > Library[/bold].\n"
            "   Search for [bold]Google Ads API[/bold] and click [bold]Enable[/bold].",
        ),
        (
            "3. Create OAuth 2.0 credentials",
            "Go to [bold]APIs & Services > Credentials > Create Credentials > OAuth client ID[/bold].\n"
            "   Choose [bold]Desktop app[/bold] as the application type.",
        ),
        (
            "4. Download and save client_secret.json",
            f"Download the credentials file and save it to:\n"
            f"   [bold yellow]{_CLIENT_SECRET_PATH}[/bold yellow]",
        ),
        (
            "5. Apply for a Google Ads API developer token",
            "Go to [link=https://ads.google.com/aw/apicenter]https://ads.google.com/aw/apicenter[/link]\n"
            "   (must be in your MCC account). Apply for [bold]Basic access[/bold].\n"
            "   Note: approval may take a few business days.",
        ),
        (
            "6. Configure your developer token",
            "Once approved, run:\n"
            "   [bold green]sem config set developer_token YOUR_TOKEN[/bold green]",
        ),
        (
            "7. Set your MCC customer ID",
            "Run:\n"
            "   [bold green]sem config set mcc_customer_id 123-456-7890[/bold green]",
        ),
        (
            "8. Authenticate",
            "Run:\n"
            "   [bold green]sem auth login[/bold green]\n"
            "   A browser window will open for Google consent.",
        ),
    ]

    for title, body in steps:
        console.print(Panel(body, title=f"[bold]{title}[/bold]", border_style="dim"))

    rprint("\n[bold]Expected client secret path:[/bold]")
    rprint(f"  [yellow]{_CLIENT_SECRET_PATH}[/yellow]")
    rprint("\n[dim]Run [bold]sem auth login[/bold] after completing all steps.[/dim]")


@auth_app.command("login")
def login() -> None:
    """Start the OAuth flow and store tokens securely."""
    if not _CLIENT_SECRET_PATH.exists():
        rprint(
            f"[red]client_secret.json not found at {_CLIENT_SECRET_PATH}[/red]\n"
            "Run [bold]sem auth setup[/bold] for instructions."
        )
        raise typer.Exit(1)

    rprint("[bold]Starting OAuth flow...[/bold] A browser window will open.")

    try:
        credentials = run_oauth_flow(_CLIENT_SECRET_PATH)
        store_tokens(credentials)
        rprint("[green]Authentication successful! Tokens stored securely.[/green]")
    except AuthError as e:
        rprint(f"[red]Authentication failed: {e}[/red]")
        raise typer.Exit(1)


@auth_app.command("status")
def status() -> None:
    """Show current authentication status, token expiry, and config summary."""
    credentials = load_tokens()
    if credentials is None:
        rprint("[yellow]Not authenticated.[/yellow] Run [bold]sem auth login[/bold].")
        raise typer.Exit(0)

    expiry_info = check_expiry(credentials)
    mcc_customer_id = config_manager.get_value("mcc_customer_id")
    developer_token = config_manager.get_value("developer_token")

    if expiry_info["valid"]:
        auth_line = "Authenticated: [green]Yes[/green]"
    else:
        auth_line = "Authenticated: [red]Token expired[/red]"

    expires_at = expiry_info.get("expires_at")
    minutes_remaining = expiry_info.get("minutes_remaining")

    expires_line = (
        f"Expires:          {expires_at.strftime('%Y-%m-%d %H:%M UTC') if expires_at else 'Unknown'}"
    )
    minutes_line = (
        f"Minutes remaining: {minutes_remaining if minutes_remaining is not None else 'Unknown'}"
    )
    mcc_line = f"MCC Customer ID:  {mcc_customer_id or 'Not set'}"
    token_line = f"Developer Token:  {'Configured' if developer_token else 'Not set'}"

    body = "\n".join([auth_line, expires_line, minutes_line, mcc_line, token_line])

    console.print(
        Panel(
            body,
            title="[bold cyan]Auth Status[/bold cyan]",
            border_style="cyan",
        )
    )


@auth_app.command("logout")
def logout() -> None:
    """Clear all stored credentials from all backends."""
    clear_tokens()
    rprint("[green]All credentials cleared.[/green]")
