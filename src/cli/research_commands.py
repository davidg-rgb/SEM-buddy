"""CLI command for the research pipeline stage — scrape and analyze client digital presence."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.stage_helpers import resolve_client, require_prerequisites, complete_stage, mark_stage_started
from src.models.client import ClientProfile
from src.models.research import SiteCrawl, CrawledPage

research_app = typer.Typer(name="research", help="Scrape and analyze client digital presence.")
console = Console()

_STAGE = "research"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@research_app.callback(invoke_without_command=True)
def run(
    client: Optional[str] = typer.Argument(None, help="Client slug (defaults to active client)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without live scraping"),
) -> None:
    """Scrape the client's website and store site crawl data."""
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
            parsed = urlparse(str(profile.website_url))
            crawl_result = SiteCrawl(
                pages=[],
                total_pages=0,
                primary_language="sv",
            )
            console.print(
                f"[dim]Dry-run: created synthetic site crawl for '{parsed.netloc}'[/dim]"
            )
        else:
            from src.scrapers.site_crawler import crawl_site
            console.print(f"[dim]Crawling {profile.website_url} (up to 30 pages)...[/dim]")
            crawl_result = asyncio.run(crawl_site(str(profile.website_url), max_pages=30))

        # Write crawl result to clients/{name}/research/site_crawl.json
        output_path = client_dir / "research" / "site_crawl.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            crawl_result.model_dump_json(indent=2), encoding="utf-8"
        )

        domain = urlparse(str(profile.website_url)).netloc or str(profile.website_url)
        pages_crawled = crawl_result.total_pages or len(crawl_result.pages)

        console.print(
            Panel(
                f"[bold]Domain:[/bold]        {domain}\n"
                f"[bold]Pages crawled:[/bold]  {pages_crawled}\n"
                f"[bold]Saved to:[/bold]      {output_path}",
                title=f"[bold cyan]Research — {name}[/bold cyan]",
                border_style="cyan",
            )
        )

    except Exception:
        from src.accounts.state import update_state
        update_state(client_dir, _STAGE, "failed")
        raise

    duration = time.monotonic() - start
    complete_stage(client_dir, _STAGE, console, duration_seconds=duration)
