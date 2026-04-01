"""CLI command group for campaign template management.

Provides `sem templates` sub-commands: list, save, load, delete.
Templates enable the operator to reuse proven campaign structures across
clients without rebuilding from scratch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.stage_helpers import resolve_client
from src.models.campaign import CampaignPlan
from src.models.client import ClientProfile
from src.templates.adapter import apply_template
from src.templates.manager import (
    CampaignTemplate,
    delete_template,
    list_templates,
    load_template,
    save_template,
)

template_app = typer.Typer(name="templates", help="Save and reuse campaign templates.")
console = Console()


@template_app.command("list")
def list_cmd() -> None:
    """List all saved campaign templates."""
    templates = list_templates()

    if not templates:
        console.print("[yellow]No templates saved yet.[/yellow]")
        return

    table = Table(title="Saved Templates", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Industry")
    table.add_column("Source Client")
    table.add_column("Created")

    for tmpl in templates:
        created = tmpl["created_at"].strftime("%Y-%m-%d")
        table.add_row(
            tmpl["name"],
            tmpl["description"] or "-",
            tmpl["source_industry"] or "-",
            tmpl["source_client"],
            created,
        )

    console.print(table)


@template_app.command("save")
def save_cmd(
    name: str = typer.Argument(..., help="Template slug (e.g. dental-basic)."),
    client: Optional[str] = typer.Argument(
        None,
        help="Client slug to save from (defaults to active client).",
    ),
    description: str = typer.Option("", help="Template description."),
) -> None:
    """Save a client's campaign plan as a reusable template."""
    client_name, client_dir = resolve_client(client)

    # Load campaign plan
    campaign_path = client_dir / "campaigns" / "campaign.json"
    if not campaign_path.exists():
        console.print(
            f"[red]campaign.json not found at {campaign_path}. "
            "Run 'sem campaign' first.[/red]"
        )
        raise typer.Exit(1)

    plan = CampaignPlan.model_validate_json(campaign_path.read_text(encoding="utf-8"))

    # Load client profile
    profile_path = client_dir / "intake" / "client_profile.json"
    if not profile_path.exists():
        console.print(f"[red]client_profile.json not found at {profile_path}.[/red]")
        raise typer.Exit(1)

    profile = ClientProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))

    output_path = save_template(name, plan, profile, description)
    console.print(
        f"[green]Template '{name}' saved from client '{client_name}'.[/green]\n"
        f"  Stored at: {output_path}"
    )


@template_app.command("load")
def load_cmd(
    name: str = typer.Argument(..., help="Template slug to apply."),
    client: Optional[str] = typer.Argument(
        None,
        help="Target client slug (defaults to active client).",
    ),
) -> None:
    """Apply a saved template to a client, regenerating ad copy for that client."""
    client_name, client_dir = resolve_client(client)

    # Load template
    try:
        template: CampaignTemplate = load_template(name)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}. Use 'sem templates list' to see available templates.[/red]")
        raise typer.Exit(1)

    # Load target client profile
    profile_path = client_dir / "intake" / "client_profile.json"
    if not profile_path.exists():
        console.print(
            f"[red]client_profile.json not found at {profile_path}. "
            "Run 'sem intake' first.[/red]"
        )
        raise typer.Exit(1)

    profile = ClientProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))

    # Optionally load keyword groups
    keyword_groups: dict | None = None
    keyword_path = client_dir / "keywords" / "keyword_data.json"
    if keyword_path.exists():
        try:
            with open(keyword_path, encoding="utf-8") as f:
                kw_data = json.load(f)
            keyword_groups = kw_data.get("groups")
        except Exception as exc:
            console.print(f"[yellow]Could not load keyword_data.json: {exc}. Proceeding without keywords.[/yellow]")

    # Apply template
    plan = apply_template(template, profile, keyword_groups)

    # Write adapted campaign plan
    campaigns_dir = client_dir / "campaigns"
    campaigns_dir.mkdir(parents=True, exist_ok=True)
    output_path = campaigns_dir / "campaign.json"
    output_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    total_campaigns = len(plan.campaigns)
    total_ad_groups = sum(len(c.ad_groups) for c in plan.campaigns)
    total_keywords = sum(
        len(ag.keywords)
        for c in plan.campaigns
        for ag in c.ad_groups
    )

    console.print(
        Panel(
            f"[bold]{profile.business_name}[/bold] — Template '{name}' applied\n\n"
            f"  Campaigns:  {total_campaigns}\n"
            f"  Ad Groups:  {total_ad_groups}\n"
            f"  Keywords:   {total_keywords}\n"
            f"  Output:     {output_path}",
            title="[bold cyan]Template Applied[/bold cyan]",
            border_style="cyan",
        )
    )


@template_app.command("delete")
def delete_cmd(
    name: str = typer.Argument(..., help="Template slug to delete."),
) -> None:
    """Delete a saved template by name."""
    try:
        delete_template(name)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}.[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Template '{name}' deleted.[/green]")
