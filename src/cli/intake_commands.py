"""CLI command for the intake pipeline stage — collect client business information."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.stage_helpers import resolve_client, require_prerequisites, complete_stage, mark_stage_started
from src.models.client import ClientProfile, GeoTarget, TargetAudience

intake_app = typer.Typer(name="intake", help="Client onboarding — collect business information.")
console = Console()

_STAGE = "intake"


@intake_app.callback(invoke_without_command=True)
def run(
    client: Optional[str] = typer.Argument(None, help="Client slug (defaults to active client)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without prompts using synthetic data"),
) -> None:
    """Collect business information and create a client profile JSON."""
    name, client_dir = resolve_client(client)
    require_prerequisites(client_dir, _STAGE)

    # Load the account for defaults
    from src.accounts.manager import get_account
    account = get_account(name)

    mark_stage_started(client_dir, _STAGE)
    start = time.monotonic()

    try:
        if dry_run:
            profile = _build_dry_run_profile(account)
            console.print(f"[dim]Dry-run: created synthetic client profile for '{name}'[/dim]")
        else:
            profile = _prompt_for_profile(account)

        # Write to clients/{name}/intake/client_profile.json
        output_path = client_dir / "intake" / "client_profile.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")

        # Print summary panel
        geo_names = ", ".join(g.name for g in profile.geographic_targets) or "—"
        services_str = ", ".join(profile.products_services[:5]) or "—"
        console.print(
            Panel(
                f"[bold]Business:[/bold] {profile.business_name}\n"
                f"[bold]Website:[/bold]  {profile.website_url}\n"
                f"[bold]Industry:[/bold] {profile.industry}\n"
                f"[bold]Budget:[/bold]   {profile.monthly_budget_sek:,} SEK/month\n"
                f"[bold]Targets:[/bold]  {geo_names}\n"
                f"[bold]Services:[/bold] {services_str}\n"
                f"[bold]Saved to:[/bold] {output_path}",
                title=f"[bold cyan]Intake — {name}[/bold cyan]",
                border_style="cyan",
            )
        )

    except Exception:
        from src.accounts.state import update_state
        update_state(client_dir, _STAGE, "failed")
        raise

    duration = time.monotonic() - start
    complete_stage(client_dir, _STAGE, console, duration_seconds=duration)


def _build_dry_run_profile(account) -> ClientProfile:
    """Return a synthetic ClientProfile using data from the account record."""
    return ClientProfile(
        business_name=account.display_name,
        website_url="https://example.com",  # type: ignore[arg-type]
        industry=account.industry or "general",
        products_services=["Service A", "Service B", "Service C"],
        monthly_budget_sek=account.monthly_budget_sek or 15000,
        geographic_targets=[GeoTarget(name="Stockholm", google_geo_id=1011766)],
    )


def _prompt_for_profile(account) -> ClientProfile:
    """Interactively collect client profile data using typer.prompt()."""
    console.print(f"\n[bold]Collecting intake data for:[/bold] {account.display_name}\n")

    business_name = typer.prompt("Business name", default=account.display_name)
    website_url = typer.prompt("Website URL (e.g. https://example.se)")
    industry = typer.prompt("Industry", default=account.industry or "")
    services_raw = typer.prompt(
        "Products/services (comma-separated, e.g. tandläkare, implantat, tandblekning)"
    )
    products_services = [s.strip() for s in services_raw.split(",") if s.strip()]
    budget = typer.prompt(
        "Monthly budget (SEK)",
        default=str(account.monthly_budget_sek or 10000),
    )
    monthly_budget_sek = int(budget)
    cities_raw = typer.prompt(
        "Geographic targets (comma-separated city names, e.g. Stockholm, Göteborg)"
    )
    geographic_targets = [
        GeoTarget(name=city.strip())
        for city in cities_raw.split(",")
        if city.strip()
    ]

    return ClientProfile(
        business_name=business_name,
        website_url=website_url,  # type: ignore[arg-type]
        industry=industry,
        products_services=products_services,
        monthly_budget_sek=monthly_budget_sek,
        geographic_targets=geographic_targets,
    )
