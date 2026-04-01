"""CLI command for the keywords pipeline stage — generate and group keyword research."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.stage_helpers import resolve_client, require_prerequisites, complete_stage, mark_stage_started
from src.models.client import ClientProfile
from src.generators.keyword_generator import (
    generate_seed_keywords,
    expand_keywords_swedish,
    group_keywords,
    assign_match_types,
    generate_negative_keywords,
)
from src.apis.google_ads import get_ads_service

keywords_app = typer.Typer(name="keywords", help="Generate and group keyword research.")
console = Console()

_STAGE = "keywords"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@keywords_app.callback(invoke_without_command=True)
def run(
    client: Optional[str] = typer.Argument(None, help="Client slug (defaults to active client)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without live API calls"),
) -> None:
    """Generate, expand, group, and match-type keywords for the campaign."""
    import asyncio

    name, client_dir = resolve_client(client)
    require_prerequisites(client_dir, _STAGE)

    # Load client profile from intake
    profile_path = client_dir / "intake" / "client_profile.json"
    if not profile_path.exists():
        console.print(
            f"[red]Client profile not found at {profile_path}. Run 'sem intake {name}' first.[/red]"
        )
        raise typer.Exit(1)

    profile = ClientProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))

    # Load site crawl from research
    crawl_path = client_dir / "research" / "site_crawl.json"
    if not crawl_path.exists():
        console.print(
            f"[red]Site crawl not found at {crawl_path}. Run 'sem research {name}' first.[/red]"
        )
        raise typer.Exit(1)

    crawl_data = _load_json(crawl_path)

    # Extract site content from crawl headings
    site_content: list[str] = []
    for page in crawl_data.get("pages", []):
        headings = page.get("headings", [])
        if isinstance(headings, list):
            for h in headings:
                if isinstance(h, dict):
                    text = h.get("text", "")
                elif isinstance(h, str):
                    text = h
                else:
                    text = ""
                if text.strip():
                    site_content.append(text.strip())

    # Load competitor keywords if available
    competitor_keywords: list[str] = []
    competitors_path = client_dir / "competitors" / "competitors.json"
    if competitors_path.exists():
        try:
            competitors_data = _load_json(competitors_path)
            if isinstance(competitors_data, list):
                for comp in competitors_data:
                    competitor_keywords.extend(comp.get("top_keywords") or [])
        except Exception:
            pass  # competitors data is optional

    # Load account for customer_id
    from src.accounts.manager import get_account
    account = get_account(name)

    mark_stage_started(client_dir, _STAGE)
    start = time.monotonic()

    try:
        # 1. Generate seeds
        seeds = generate_seed_keywords(profile, site_content, competitor_keywords)
        console.print(f"[dim]Generated {len(seeds)} seed keywords[/dim]")

        # 2. Expand seeds with Swedish variants
        expanded = expand_keywords_swedish(seeds)
        console.print(f"[dim]Expanded to {len(expanded)} keyword variants[/dim]")

        # 3. Get search volume data from Google Ads API (or dry-run mock)
        service = get_ads_service(account.customer_id, dry_run=dry_run)
        volume_data: list[dict] = asyncio.run(
            service.get_search_volumes(expanded[:50])
        )

        # Build keyword dicts combining expanded list with volume data
        volume_map: dict[str, dict] = {item.get("keyword", ""): item for item in volume_data}
        keyword_dicts: list[dict] = []
        for kw_text in expanded:
            vol_entry = volume_map.get(kw_text, {})
            keyword_dicts.append(
                {
                    "text": kw_text,
                    "avg_monthly_searches": vol_entry.get("avg_monthly_searches", 0),
                    "competition": vol_entry.get("competition", "UNKNOWN"),
                    "avg_cpc_sek": vol_entry.get("avg_cpc_micros", 0) / 1_000_000
                    if vol_entry.get("avg_cpc_micros")
                    else 0.0,
                }
            )

        # 4. Group keywords by theme
        groups = group_keywords(keyword_dicts)

        # 5. Assign match types based on budget
        match_typed = assign_match_types(keyword_dicts, profile.monthly_budget_sek)

        # 6. Generate negative keywords
        target_texts = [kw["text"] for kw in keyword_dicts]
        negatives = generate_negative_keywords(target_texts, profile.industry)

        # 7. Write keyword data
        output_path = client_dir / "keywords" / "keyword_data.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        keyword_output = {
            "seeds": seeds,
            "expanded": expanded,
            "groups": {
                group_name: [kw for kw in group_kws]
                for group_name, group_kws in groups.items()
            },
            "negatives": negatives,
            "match_typed": match_typed,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(keyword_output, f, indent=2, ensure_ascii=False)

        # Print summary
        console.print(
            Panel(
                f"[bold]Seeds:[/bold]     {len(seeds)}\n"
                f"[bold]Expanded:[/bold]  {len(expanded)}\n"
                f"[bold]Groups:[/bold]    {len(groups)}\n"
                f"[bold]Negatives:[/bold] {len(negatives)}\n"
                f"[bold]Saved to:[/bold]  {output_path}",
                title=f"[bold cyan]Keywords — {name}[/bold cyan]",
                border_style="cyan",
            )
        )

    except Exception:
        from src.accounts.state import update_state
        update_state(client_dir, _STAGE, "failed")
        raise

    duration = time.monotonic() - start
    complete_stage(client_dir, _STAGE, console, duration_seconds=duration)
