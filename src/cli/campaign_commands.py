"""CLI command for the campaign build stage.

Builds complete Google Ads campaign structure (ad groups, keywords, ad copy)
from the keyword research data produced by the keywords stage.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.stage_helpers import (
    resolve_client,
    require_prerequisites,
    complete_stage,
    mark_stage_started,
)
from src.models.client import ClientProfile
from src.models.research import DigitalPresence
from src.models.campaign import CampaignPlan
from src.generators.campaign_builder import build_campaigns

campaign_app = typer.Typer(
    name="campaign",
    help="Build campaign structure with ad groups, keywords, and ad copy.",
)

console = Console()


@campaign_app.callback(invoke_without_command=True)
def campaign(
    client: Optional[str] = typer.Argument(
        None,
        help="Client slug (defaults to active client).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run without external API calls using synthetic data.",
    ),
) -> None:
    """Build Google Ads campaign structure from keyword research data.

    Reads the client profile and keyword groups produced by the keywords stage,
    builds the full campaign / ad group / keyword hierarchy with ad copy and
    extensions, then writes campaign.json to clients/{name}/campaigns/.
    """
    name, client_dir = resolve_client(client)
    require_prerequisites(client_dir, "campaign")
    mark_stage_started(client_dir, "campaign")

    start_time = time.monotonic()

    # --- Load client profile ---
    profile_path = client_dir / "intake" / "client_profile.json"
    if not profile_path.exists():
        console.print(f"[red]client_profile.json not found at {profile_path}[/red]")
        raise typer.Exit(1)
    profile = ClientProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))

    # --- Load keyword data ---
    keyword_path = client_dir / "keywords" / "keyword_data.json"
    if not keyword_path.exists():
        console.print(f"[red]keyword_data.json not found at {keyword_path}[/red]")
        raise typer.Exit(1)
    with open(keyword_path, encoding="utf-8") as f:
        keyword_data = json.load(f)

    keyword_groups: dict = keyword_data.get("groups", {})

    # --- Load optional digital presence ---
    digital_presence: DigitalPresence | None = None
    site_crawl_path = client_dir / "research" / "site_crawl.json"
    if site_crawl_path.exists():
        try:
            from src.models.research import SiteCrawl
            crawl_data = json.loads(site_crawl_path.read_text(encoding="utf-8"))
            site_crawl = SiteCrawl.model_validate(crawl_data)
            digital_presence = DigitalPresence(site_crawl=site_crawl)
        except Exception as e:
            console.print(f"[yellow]Could not load site_crawl.json: {e}. Proceeding without it.[/yellow]")

    # --- Build campaign plan ---
    try:
        plan: CampaignPlan = build_campaigns(profile, keyword_groups, digital_presence)
    except Exception as e:
        from src.accounts.state import update_state
        update_state(client_dir, "campaign", "failed", metadata={"error": str(e)})
        console.print(f"[red]Campaign build failed: {e}[/red]")
        raise typer.Exit(1)

    # --- Write campaign.json ---
    campaigns_dir = client_dir / "campaigns"
    campaigns_dir.mkdir(parents=True, exist_ok=True)
    output_path = campaigns_dir / "campaign.json"
    output_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    # --- Summary ---
    total_campaigns = len(plan.campaigns)
    total_ad_groups = sum(len(c.ad_groups) for c in plan.campaigns)
    total_keywords = sum(
        len(ag.keywords)
        for c in plan.campaigns
        for ag in c.ad_groups
    )

    duration = time.monotonic() - start_time

    console.print(
        Panel(
            f"[bold]{profile.business_name}[/bold] — Campaign Plan\n\n"
            f"  Campaigns:  {total_campaigns}\n"
            f"  Ad Groups:  {total_ad_groups}\n"
            f"  Keywords:   {total_keywords}\n"
            f"  Output:     {output_path}",
            title="[bold cyan]Campaign Build Complete[/bold cyan]",
            border_style="cyan",
        )
    )

    complete_stage(client_dir, "campaign", console, duration_seconds=duration)
