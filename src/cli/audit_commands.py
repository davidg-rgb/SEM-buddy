"""CLI command for the audit stage.

Fetches live Google Ads campaign data and compares it against the locally
generated campaign plan, producing a structured diff report in markdown.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.stage_helpers import resolve_client
from src.models.campaign import CampaignPlan
from src.accounts.manager import get_account

audit_app = typer.Typer(
    name="audit",
    help="Compare live Google Ads data against recommendations.",
)

console = Console()


@audit_app.callback(invoke_without_command=True)
def audit(
    client: Optional[str] = typer.Argument(
        None,
        help="Client slug (defaults to active client).",
    ),
    campaign_id: Optional[str] = typer.Option(
        None,
        "--campaign-id",
        help="Audit a specific campaign ID only.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Use synthetic data instead of the live API.",
    ),
) -> None:
    """Compare live Google Ads campaigns against the generated campaign plan.

    Fetches live data from the Google Ads API (or uses synthetic data in
    dry-run mode), compares it against clients/{name}/campaigns/campaign.json,
    and writes a structured markdown diff report to clients/{name}/audits/.
    """
    from src.audit.fetcher import fetch_live_campaigns_sync
    from src.audit.comparator import compare, format_audit_report
    from src.auth import AuthError
    from src.apis.errors import GoogleAdsApiError

    name, client_dir = resolve_client(client)

    # Resolve customer ID
    account = get_account(name)
    customer_id: Optional[str] = getattr(account, "customer_id", None)

    if not customer_id and not dry_run:
        console.print(
            f"[red]No Google Ads customer ID set for '{name}'. "
            "Use 'sem accounts add' with a valid customer ID.[/red]"
        )
        raise typer.Exit(1)

    # Use a placeholder ID for dry-run when no real customer ID exists
    effective_customer_id = customer_id or "000-000-0000"

    # Load recommended campaign plan
    plan_path = client_dir / "campaigns" / "campaign.json"
    if not plan_path.exists():
        console.print(
            f"[red]No campaign plan found. Run 'sem campaign {name}' first.[/red]"
        )
        raise typer.Exit(1)

    try:
        plan = CampaignPlan.model_validate_json(
            plan_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        console.print(f"[red]Failed to load campaign plan: {exc}[/red]")
        raise typer.Exit(1)

    # Fetch live data
    campaign_ids = [campaign_id] if campaign_id else None
    try:
        live_data = fetch_live_campaigns_sync(
            effective_customer_id,
            dry_run=dry_run,
            campaign_ids=campaign_ids,
        )
    except AuthError:
        console.print(
            "[red]Not authenticated with Google Ads. "
            "Run 'sem auth login' to authenticate.[/red]"
        )
        raise typer.Exit(1)
    except GoogleAdsApiError as exc:
        hint = getattr(exc, "hint", str(exc))
        console.print(f"[red]Google Ads API error: {hint}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Unexpected error fetching live data: {exc}[/red]")
        raise typer.Exit(1)

    # Compare
    diff = compare(live_data, plan)

    # Rich terminal summary
    missing = diff.get("missing_campaigns", [])
    extra = diff.get("extra_campaigns", [])
    keyword_gaps = diff.get("keyword_gaps", [])
    keyword_waste = diff.get("keyword_waste", [])
    ad_copy_diffs = diff.get("ad_copy_diffs", [])
    budget_diffs = diff.get("budget_diffs", [])
    bid_diffs = diff.get("bid_strategy_diffs", [])

    mode_label = "[yellow](dry-run)[/yellow]" if dry_run else "[green](live)[/green]"
    console.print(
        Panel(
            f"[bold]{name}[/bold] — Kampanjgranskning {mode_label}\n\n"
            f"  Saknade kampanjer:         {len(missing)}\n"
            f"  Extra kampanjer:           {len(extra)}\n"
            f"  Saknade sökord:            {len(keyword_gaps)}\n"
            f"  Potentiellt sökordssloseri: {len(keyword_waste)}\n"
            f"  Annonskopieringsskillnader: {len(ad_copy_diffs)}\n"
            f"  Budgetskillnader:          {len(budget_diffs)}\n"
            f"  Budstrategiskillnader:     {len(bid_diffs)}",
            title="[bold cyan]Audit — Sammanfattning[/bold cyan]",
            border_style="cyan",
        )
    )

    # Write full markdown report
    report_md = format_audit_report(diff, name)
    audits_dir = client_dir / "audits"
    audits_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_path = audits_dir / f"audit_{date_str}.md"
    output_path.write_text(report_md, encoding="utf-8")

    console.print(f"[green]Audit report saved to {output_path}[/green]")
