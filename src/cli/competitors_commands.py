"""CLI command for the competitors pipeline stage — analyze competitor ad strategies."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.stage_helpers import resolve_client, require_prerequisites, complete_stage, mark_stage_started
from src.models.client import ClientProfile

competitors_app = typer.Typer(name="competitors", help="Analyze competitor ad strategies.")
console = Console()

_STAGE = "competitors"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_dry_run_competitors(profile: ClientProfile) -> list[dict]:
    """Create synthetic competitor profiles for dry-run mode."""
    return [
        {
            "name": "Konkurrent AB",
            "domain": "konkurrent.se",
            "estimated_monthly_spend_sek": 20000,
            "top_keywords": [
                f"{profile.industry} Stockholm",
                f"bästa {profile.industry}",
                f"billig {profile.industry}",
            ],
            "ad_copy_patterns": [
                "Kontakta oss idag",
                "Fri konsultation",
                "Certifierade experter",
            ],
            "transparency_ads": [],
        },
        {
            "name": "Rival Företag",
            "domain": "rival-foretag.se",
            "estimated_monthly_spend_sek": 15000,
            "top_keywords": [
                f"{profile.industry} pris",
                f"professionell {profile.industry}",
            ],
            "ad_copy_patterns": [
                "Snabb leverans",
                "Garanti ingår",
            ],
            "transparency_ads": [],
        },
        {
            "name": "Ledande Partner",
            "domain": "ledandepartner.se",
            "estimated_monthly_spend_sek": 30000,
            "top_keywords": [
                f"{profile.industry} erfarenhet",
                f"auktoriserad {profile.industry}",
                f"{profile.industry} kvalitet",
            ],
            "ad_copy_patterns": [
                "30 års erfarenhet",
                "Nöjd-kund-garanti",
                "Boka gratis rådgivning",
            ],
            "transparency_ads": [],
        },
    ]


@competitors_app.callback(invoke_without_command=True)
def run(
    client: Optional[str] = typer.Argument(None, help="Client slug (defaults to active client)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without live API calls"),
) -> None:
    """Collect competitor intelligence and store structured competitor profiles."""
    name, client_dir = resolve_client(client)
    require_prerequisites(client_dir, _STAGE)

    # Load the client profile from intake
    profile_path = client_dir / "intake" / "client_profile.json"
    if not profile_path.exists():
        console.print(
            f"[red]Client profile not found at {profile_path}. Run 'sem intake {name}' first.[/red]"
        )
        raise typer.Exit(1)

    profile = ClientProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))

    mark_stage_started(client_dir, _STAGE)
    start = time.monotonic()

    try:
        if dry_run:
            competitors_data = _build_dry_run_competitors(profile)
            console.print(
                f"[dim]Dry-run: created {len(competitors_data)} synthetic competitor profiles[/dim]"
            )
        else:
            # Non-dry-run: structure data from known_competitors list
            # Real scraper integration is handled by sem-competitor-ads skill in a later phase
            competitors_data = []
            for competitor_name in profile.known_competitors:
                competitors_data.append(
                    {
                        "name": competitor_name,
                        "domain": competitor_name.lower().replace(" ", "") + ".se",
                        "estimated_monthly_spend_sek": None,
                        "top_keywords": [],
                        "ad_copy_patterns": [],
                        "transparency_ads": [],
                    }
                )
            if not competitors_data:
                console.print(
                    "[yellow]No known competitors listed in client profile. "
                    "Add competitors to the intake profile or use --dry-run for synthetic data.[/yellow]"
                )

        # Write to clients/{name}/competitors/competitors.json
        output_path = client_dir / "competitors" / "competitors.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(competitors_data, f, indent=2, ensure_ascii=False)

        # Print summary table
        table = Table(title=f"Competitors — {name}", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="bold")
        table.add_column("Domain")
        table.add_column("Est. Spend (SEK)", justify="right")
        table.add_column("Keywords", justify="right")

        for comp in competitors_data:
            spend = str(comp.get("estimated_monthly_spend_sek") or "—")
            kw_count = str(len(comp.get("top_keywords") or []))
            table.add_row(comp["name"], comp["domain"], spend, kw_count)

        console.print(table)
        console.print(f"[dim]Saved to: {output_path}[/dim]")

    except Exception:
        from src.accounts.state import update_state
        update_state(client_dir, _STAGE, "failed")
        raise

    duration = time.monotonic() - start
    complete_stage(client_dir, _STAGE, console, duration_seconds=duration)
