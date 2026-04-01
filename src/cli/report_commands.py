"""CLI command for the report stage.

Generates a strategy report (markdown + optional PDF) with analysis and
recommendations. In --dry-run mode a prominent DRY RUN warning is prepended
to both the markdown and PDF versions of the report.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.cli.stage_helpers import (
    resolve_client,
    require_prerequisites,
    complete_stage,
    mark_stage_started,
)
from src.models.client import ClientProfile
from src.models.campaign import CampaignPlan
from src.models.research import DigitalPresence
from src.generators.report_generator import generate_strategy_report

report_app = typer.Typer(
    name="report",
    help="Generate strategy report with analysis and recommendations.",
)

console = Console()

_DRY_RUN_BANNER = (
    "---\n"
    "**WARNING: DRY RUN** - This report was generated using synthetic data. "
    "Keyword volumes, CPC estimates, and competitor data are simulated and do not "
    "reflect actual market conditions. Re-run without --dry-run for real data.\n"
    "---\n\n"
)


@report_app.callback(invoke_without_command=True)
def report(
    client: Optional[str] = typer.Argument(
        None,
        help="Client slug (defaults to active client).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Generate report with DRY RUN warning using synthetic data.",
    ),
    pdf: bool = typer.Option(
        True,
        "--pdf/--no-pdf",
        help="Generate PDF version alongside the markdown report.",
    ),
) -> None:
    """Generate a strategy report with analysis and recommendations.

    Reads all available pipeline data (client profile, keyword research,
    campaign plan, competitors, digital presence) and produces a markdown
    strategy report. With --pdf (default) also generates a PDF version.

    When --dry-run is passed a prominent DRY RUN warning is prepended to
    both the markdown and PDF output (DRY-04 requirement).
    """
    name, client_dir = resolve_client(client)
    require_prerequisites(client_dir, "report")
    mark_stage_started(client_dir, "report")

    start_time = time.monotonic()

    # --- Load client profile ---
    profile_path = client_dir / "intake" / "client_profile.json"
    if not profile_path.exists():
        console.print(f"[red]client_profile.json not found at {profile_path}[/red]")
        raise typer.Exit(1)
    profile = ClientProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))

    # --- Load keyword data ---
    keyword_path = client_dir / "keywords" / "keyword_data.json"
    keyword_data: dict = {}
    if keyword_path.exists():
        with open(keyword_path, encoding="utf-8") as f:
            keyword_data = json.load(f)

    # --- Load campaign plan ---
    campaign_path = client_dir / "campaigns" / "campaign.json"
    if not campaign_path.exists():
        console.print(f"[red]campaign.json not found at {campaign_path}[/red]")
        raise typer.Exit(1)
    plan = CampaignPlan.model_validate_json(
        campaign_path.read_text(encoding="utf-8")
    )

    # --- Load optional competitors (empty default if not available) ---
    from src.models.competitor import CompetitorProfile
    competitors: list[CompetitorProfile] = []
    competitors_path = client_dir / "competitors" / "competitors.json"
    if competitors_path.exists():
        try:
            with open(competitors_path, encoding="utf-8") as f:
                comp_list = json.load(f)
            if isinstance(comp_list, list):
                competitors = [
                    CompetitorProfile.model_validate(c) for c in comp_list
                ]
        except Exception as e:
            console.print(f"[yellow]Could not load competitors.json: {e}. Proceeding without it.[/yellow]")

    # --- Load optional digital presence (empty default if not available) ---
    digital_presence = DigitalPresence()
    site_crawl_path = client_dir / "research" / "site_crawl.json"
    if site_crawl_path.exists():
        try:
            from src.models.research import SiteCrawl
            crawl_data = json.loads(site_crawl_path.read_text(encoding="utf-8"))
            site_crawl = SiteCrawl.model_validate(crawl_data)
            digital_presence = DigitalPresence(site_crawl=site_crawl)
        except Exception as e:
            console.print(f"[yellow]Could not load site_crawl.json: {e}. Proceeding without it.[/yellow]")

    reports_dir = client_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        # --- Generate markdown report ---
        report_md = generate_strategy_report(
            profile, digital_presence, competitors, plan, keyword_data
        )

        # DRY-04: prepend visible DRY RUN warning when in dry-run mode
        if dry_run:
            report_md = _DRY_RUN_BANNER + report_md

        # Write markdown
        md_path = reports_dir / "strategy_report.md"
        md_path.write_text(report_md, encoding="utf-8")
        console.print(f"Markdown report written to: {md_path}")

        # --- Generate PDF ---
        if pdf:
            from src.generators.pdf_generator import generate_pdf_report
            pdf_path = reports_dir / "strategy_report.pdf"
            title = f"{profile.business_name} - Google Ads Strategy Report"
            if dry_run:
                title = f"[DRY RUN] {title}"
            generate_pdf_report(report_md, str(pdf_path), title=title)
            console.print(f"PDF report written to: {pdf_path}")

    except typer.Exit:
        raise
    except Exception as e:
        from src.accounts.state import update_state
        update_state(client_dir, "report", "failed", metadata={"error": str(e)})
        console.print(f"[red]Report generation failed: {e}[/red]")
        raise typer.Exit(1)

    duration = time.monotonic() - start_time
    console.print(f"[green]Report generated at: {reports_dir}[/green]")
    complete_stage(client_dir, "report", console, duration_seconds=duration)
