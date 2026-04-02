"""CLI command for SEO analysis — on-page and technical SEO audit."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

seo_app = typer.Typer(name="seo", help="SEO-analys — on-page och teknisk SEO.")
console = Console()


@seo_app.command("run")
def run(
    url: str = typer.Argument(..., help="URL att analysera"),
    mode: str = typer.Option("single", "--mode", "-m", help="single|site"),
    competitors: Optional[str] = typer.Option(None, "--competitors", "-c", help="Kommaseparerade konkurrent-URL:er"),
    client: Optional[str] = typer.Option(None, "--client", help="Klientnamn (sparar i klientkatalog)"),
    output: str = typer.Option("markdown", "--output", "-o", help="markdown|pdf|xlsx"),
    max_pages: int = typer.Option(30, "--max-pages", help="Max sidor vid site-crawl"),
    skip_lighthouse: bool = typer.Option(False, "--skip-lighthouse", help="Hoppa över Lighthouse-analys"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Använd syntetisk data"),
) -> None:
    """Kör SEO-analys på en URL eller hel webbplats."""
    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    if not parsed.netloc:
        console.print("[red]Ogiltig URL. Ange en fullständig URL (t.ex. https://example.se)[/red]")
        raise typer.Exit(1)

    # Determine output directory — always route to clients/{name}/seo/
    from src.utils.config import CLIENTS_DIR

    if client:
        client_slug = client
    else:
        # Derive client slug from domain: www.benalexis.net -> benalexis
        domain = parsed.netloc.lower()
        domain = domain.removeprefix("www.")
        client_slug = domain.split(".")[0]

    client_dir = CLIENTS_DIR / client_slug
    output_dir = client_dir / "seo"
    output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Klient: {client_slug} → {output_dir}[/dim]")

    start = time.monotonic()

    # --- 1. Scrape ---
    from src.scrapers.seo_scraper import (
        crawl_seo_single,
        crawl_seo_site,
        generate_synthetic_page_data,
        generate_synthetic_site_data,
    )
    from src.models.seo import SeoAnalysisResult

    site_data = None
    page_data = None

    if dry_run:
        console.print("[dim]Dry-run: använder syntetisk data[/dim]")
        if mode == "site":
            site_data = generate_synthetic_site_data(url)
            page_data = site_data.pages[0] if site_data.pages else None
        else:
            page_data = generate_synthetic_page_data(url)
    else:
        try:
            if mode == "site":
                console.print(f"[dim]Crawlar {url} (max {max_pages} sidor)...[/dim]")
                site_data = asyncio.run(crawl_seo_site(url, max_pages=max_pages))

                # Fetch robots.txt + sitemap
                from src.scrapers.robots_sitemap import fetch_robots_txt, discover_sitemaps
                domain = parsed.netloc
                robots = asyncio.run(fetch_robots_txt(domain))
                sitemaps = asyncio.run(discover_sitemaps(domain, robots))
                site_data.robots_txt = robots
                site_data.sitemaps = sitemaps

                page_data = site_data.pages[0] if site_data.pages else None
                console.print(f"[dim]Crawlade {len(site_data.pages)} sidor[/dim]")
            else:
                console.print(f"[dim]Analyserar {url}...[/dim]")
                page_data = asyncio.run(crawl_seo_single(url))
        except ConnectionError as exc:
            console.print(f"[red]Kunde inte nå {url}: {exc}[/red]")
            console.print("[dim]Tips: Använd --dry-run för att testa med syntetisk data[/dim]")
            raise typer.Exit(1)
        except Exception as exc:
            console.print(f"[red]Fel vid scraping: {exc}[/red]")
            raise typer.Exit(1)

    # --- 2. Lighthouse (optional) ---
    lighthouse = None
    if not skip_lighthouse and not dry_run:
        from src.scrapers.lighthouse_runner import lighthouse_available, run_lighthouse
        if lighthouse_available():
            console.print("[dim]Kör Lighthouse-analys...[/dim]")
            try:
                lighthouse = asyncio.run(run_lighthouse(url))
            except Exception as exc:
                console.print(f"[yellow]Lighthouse misslyckades: {exc}[/yellow]")
        else:
            console.print("[dim]Lighthouse CLI ej installerat — hoppar över prestandaanalys[/dim]")

    # --- 3. Analyze ---
    from src.analysis.seo_analyzer import analyze_page_seo, analyze_site_seo

    if mode == "site" and site_data:
        scorecard = analyze_site_seo(site_data, lighthouse)
    elif page_data:
        scorecard = analyze_page_seo(page_data, lighthouse)
    else:
        console.print("[red]Ingen data att analysera.[/red]")
        raise typer.Exit(1)

    # --- 4. Competitor comparison (optional) ---
    competitor_analysis = None
    if competitors:
        competitor_urls = [u.strip() for u in competitors.split(",") if u.strip()]
        if competitor_urls:
            if dry_run:
                from src.analysis.seo_competitor import generate_synthetic_competitor_data
                competitor_analysis = generate_synthetic_competitor_data(competitor_urls, scorecard)
                console.print(f"[dim]Dry-run: syntetisk konkurrentdata för {len(competitor_urls)} URL:er[/dim]")
            else:
                from src.analysis.seo_competitor import analyze_competitor_seo
                console.print(f"[dim]Analyserar {len(competitor_urls)} konkurrent(er)...[/dim]")
                try:
                    competitor_analysis = asyncio.run(
                        analyze_competitor_seo(url, competitor_urls, scorecard, page_data)
                    )
                except Exception as exc:
                    console.print(f"[yellow]Konkurrentanalys misslyckades: {exc}[/yellow]")

    # --- 5. Assemble result ---
    result = SeoAnalysisResult(
        mode=mode,
        analyzed_at=datetime.now(),
        site_data=site_data,
        page_data=page_data,
        lighthouse=lighthouse,
        scorecard=scorecard,
        competitor_analysis=competitor_analysis,
    )

    # --- 6. Save JSON ---
    json_path = output_dir / "seo_analysis.json"
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    # --- 7. Generate report ---
    from src.generators.seo_report_generator import (
        generate_seo_report,
        export_seo_pdf,
        export_seo_xlsx,
    )

    md_report = generate_seo_report(result)
    md_path = output_dir / "seo_report.md"
    md_path.write_text(md_report, encoding="utf-8")

    if output == "pdf":
        pdf_path = export_seo_pdf(result, str(output_dir / "seo_report.pdf"))
        console.print(f"[dim]PDF: {pdf_path}[/dim]")
    elif output == "xlsx":
        xlsx_path = export_seo_xlsx(result, str(output_dir / "seo_report.xlsx"))
        console.print(f"[dim]XLSX: {xlsx_path}[/dim]")

    duration = time.monotonic() - start

    # --- 8. Print summary ---
    _print_summary(result, output_dir, duration)


def _print_summary(result: SeoAnalysisResult, output_dir: Path, duration: float) -> None:
    """Print a Rich summary panel to the console."""
    sc = result.scorecard
    grade = _grade(sc.overall_score)

    high_count = sum(1 for i in sc.issues if i.severity.value == "high")
    medium_count = sum(1 for i in sc.issues if i.severity.value == "medium")
    low_count = sum(1 for i in sc.issues if i.severity.value == "low")

    # Score table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Kategori", style="bold")
    table.add_column("Poäng", justify="right")
    table.add_column("Betyg", justify="center")

    for cs in sc.category_scores:
        table.add_row(cs.label, f"{cs.score:.0f}", _grade(cs.score))

    table.add_section()
    table.add_row("Totalt", f"{sc.overall_score:.0f}", grade, style="bold")

    console.print()
    console.print(table)

    # Issue summary
    issue_line = f"Problem: [red]{high_count} kritiska[/red], [yellow]{medium_count} medel[/yellow], [dim]{low_count} låga[/dim]"
    mode_label = f"{'Webbplats' if result.mode == 'site' else 'Enskild sida'}"
    if result.site_data:
        mode_label += f" ({result.site_data.total_pages_crawled} sidor)"

    panel_text = (
        f"[bold]Betyg:[/bold]  {grade} ({sc.overall_score:.0f}/100)\n"
        f"[bold]Läge:[/bold]   {mode_label}\n"
        f"{issue_line}\n"
        f"[bold]Tid:[/bold]    {duration:.1f}s\n"
        f"[bold]Rapport:[/bold] {output_dir / 'seo_report.md'}"
    )

    console.print(Panel(panel_text, title="[bold cyan]SEO-analys klar[/bold cyan]", border_style="cyan"))


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    elif score >= 50:
        return "E"
    return "F"
