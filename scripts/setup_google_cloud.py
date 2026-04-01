#!/usr/bin/env python3
"""Standalone Google Cloud & Google Ads API setup guide for SEM Master.

Run this script directly (without the CLI installed) to print the full
step-by-step guide for configuring Google Cloud and the Google Ads API.

Usage:
    python scripts/setup_google_cloud.py
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

_CONFIG_DIR = Path.home() / ".sem-master"
_CLIENT_SECRET_PATH = _CONFIG_DIR / "credentials" / "client_secret.json"

console = Console()


def main() -> None:
    """Print the Google Cloud project setup guide."""
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

    console.print(f"\n[bold]Expected client secret path:[/bold]")
    console.print(f"  [yellow]{_CLIENT_SECRET_PATH}[/yellow]")
    console.print(
        "\n[dim]After completing all steps, run [bold]sem auth login[/bold] to authenticate.[/dim]"
    )


if __name__ == "__main__":
    main()
