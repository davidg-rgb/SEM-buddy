"""CLI command for the export stage.

Exports the campaign plan to Google Ads Editor CSV files and optionally
generates a keyword XLSX report.
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
from src.models.campaign import CampaignPlan
from src.generators.csv_exporter import export_campaign_plan
from src.generators.report_generator import export_keyword_xlsx

export_app = typer.Typer(
    name="export",
    help="Export campaign to Google Ads Editor CSV files.",
)

console = Console()


@export_app.callback(invoke_without_command=True)
def export(
    client: Optional[str] = typer.Argument(
        None,
        help="Client slug (defaults to active client).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run without external API calls (uses existing campaign.json as-is).",
    ),
    keywords_only: bool = typer.Option(
        False,
        "--keywords-only",
        help="Export only keyword XLSX, skip campaign CSV files.",
    ),
) -> None:
    """Export campaign plan to Google Ads Editor CSV files.

    Reads campaign.json from clients/{name}/campaigns/ and exports per-entity-type
    CSV files to clients/{name}/exports/. Also exports a keyword_report.xlsx
    alongside the CSV files.

    With --keywords-only only the keyword XLSX is generated.
    """
    name, client_dir = resolve_client(client)
    require_prerequisites(client_dir, "export")
    mark_stage_started(client_dir, "export")

    start_time = time.monotonic()

    # --- Load keyword data (needed for XLSX) ---
    keyword_path = client_dir / "keywords" / "keyword_data.json"
    keyword_data: dict = {}
    if keyword_path.exists():
        with open(keyword_path, encoding="utf-8") as f:
            keyword_data = json.load(f)

    output_dir = client_dir / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if keywords_only:
            xlsx_path = output_dir / "keyword_report.xlsx"
            export_keyword_xlsx(keyword_data, str(xlsx_path))
            console.print(f"[green]Keyword report exported to: {xlsx_path}[/green]")
        else:
            # --- Load campaign plan ---
            campaign_path = client_dir / "campaigns" / "campaign.json"
            if not campaign_path.exists():
                console.print(f"[red]campaign.json not found at {campaign_path}[/red]")
                raise typer.Exit(1)

            plan = CampaignPlan.model_validate_json(
                campaign_path.read_text(encoding="utf-8")
            )

            # Export CSV files
            export_campaign_plan(plan, str(output_dir))

            # Export keyword XLSX alongside the CSV files
            xlsx_path = output_dir / "keyword_report.xlsx"
            export_keyword_xlsx(keyword_data, str(xlsx_path))

            # Count exported CSV files
            csv_files = list(output_dir.glob("*.csv"))
            console.print(
                f"[green]Export complete. {len(csv_files)} CSV file(s) + "
                f"keyword XLSX at: {output_dir}[/green]"
            )

    except typer.Exit:
        raise
    except Exception as e:
        from src.accounts.state import update_state
        update_state(client_dir, "export", "failed", metadata={"error": str(e)})
        console.print(f"[red]Export failed: {e}[/red]")
        raise typer.Exit(1)

    duration = time.monotonic() - start_time
    complete_stage(client_dir, "export", console, duration_seconds=duration)
