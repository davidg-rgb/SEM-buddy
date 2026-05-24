"""CLI: `sem case run` + `sem case push` + `sem catalog clean|accept-fixes|validate`."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table
from rich.console import Console

from src.cases.runner import run_accept_fixes, run_case, run_clean
from src.catalog import load_catalog_from_yaml
from src.catalog.validators import CatalogSchema, issues_to_markdown, validate_catalog
from src.utils.config import CLIENTS_DIR


case_app = typer.Typer(name="case", help="Run the full catalog → CSV pipeline for a client.")
catalog_app = typer.Typer(name="catalog", help="Inspect, validate, and clean catalog data.")
console = Console()


@case_app.command("run")
def case_run(
    slug: str = typer.Argument(..., help="Client slug (folder under clients/)"),
    max_products: int = typer.Option(
        None, "--max-products",
        help="Truncate to first N catalog rows (useful for iteration).",
    ),
    no_validate: bool = typer.Option(
        False, "--no-validate", help="Skip the validation step (still runs cleaning if accepted)."
    ),
) -> None:
    """Run the full case pipeline for a client.

    Walks: load catalog → apply accepted cleaning → validate → build campaigns
    → export to clients/<slug>/exports/catalog/.
    """
    try:
        result = run_case(slug, validate=not no_validate, max_products=max_products)
    except FileNotFoundError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        rprint(f"[red]Case run failed: {exc}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Case run: {slug}", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Products", str(result.products_count))
    table.add_row("Campaigns", str(result.campaign_count))
    table.add_row("Ad groups", str(result.ad_group_count))
    table.add_row("Promotions", str(result.promotions_count))
    table.add_row("Lead forms", str(result.lead_forms_count))
    table.add_row("Bid schedules", str(result.bid_schedules_count))
    table.add_row("Cleaning applied", "yes" if result.cleaning_applied else "no")
    table.add_row("Validation", result.validation_summary)
    table.add_row("Export dir", str(result.export_dir))
    console.print(table)
    rprint("[green]Done.[/green]")


@case_app.command("push")
def case_push(
    slug: str = typer.Argument(..., help="Client slug (folder under clients/)"),
    limit: int = typer.Option(
        None,
        "--limit",
        help="Push only the first N ad groups (smoke test). Omit for full push.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Walk the plan + report what would be pushed, but make no API calls.",
    ),
    name_suffix: str = typer.Option(
        "",
        "--name-suffix",
        help="String to append to every entity name (useful for re-runs). "
        "Default: empty (or a timestamp if --auto-suffix is set).",
    ),
    auto_suffix: bool = typer.Option(
        False,
        "--auto-suffix",
        help="Append a ISO-timestamp suffix to all entity names so re-runs do not collide.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
    skip_lead_forms: bool = typer.Option(
        False,
        "--skip-lead-forms",
        help=(
            "Don't push lead-form assets. Google requires a one-time ToS "
            "acceptance in the Ads UI before the API can create lead forms; "
            "set this flag after a clean push to avoid the partial-failure "
            "warning."
        ),
    ),
    bid_strategy: str = typer.Option(
        "",
        "--bid-strategy",
        help=(
            "Override the case.yaml's selected bid strategy. Use "
            "'MAXIMIZE_CLICKS' (or 'clicks') on a fresh test account that "
            "lacks conversion tracking — TARGET_ROAS / "
            "MAXIMIZE_CONVERSION_VALUE require a configured conversion "
            "action or Google rejects the campaign with "
            "CONVERSION_TRACKING_NOT_ENABLED. The operator flips to the "
            "intended smart-bidding strategy in the UI once conversion "
            "tracking is wired up."
        ),
    ),
    resume: str = typer.Option(
        "",
        "--resume",
        help=(
            "Resume an existing partial campaign by ID (numeric, no "
            "'customers/...' prefix). Skips budget/campaign/criteria "
            "creation, queries live state, and pushes ONLY entities that "
            "don't already exist. Pair with --name-suffix matching the "
            "original push's suffix so plan entity names line up with "
            "the live ones (e.g. ' [2026-05-21 17:18:46]')."
        ),
    ),
) -> None:
    """Push a built case to the LIVE Google Ads account.

    Runs the case (load + clean + build), then mutates entities via the Google
    Ads API. The customer ID is read from `clients/<slug>/account.yaml`. All
    campaigns are created in PAUSED state so the operator can review before
    going live.
    """
    from src.accounts.manager import get_account
    from src.apis.campaign_pusher import CampaignPusher

    try:
        account = get_account(slug)
    except FileNotFoundError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    # Build the plan in-memory (mirrors `sem case run`, but doesn't write CSVs)
    from src.cases.config import load_case_config
    from src.cases.runner import _load_client_profile, _maybe_clean_catalog, _resolve_case_path
    from src.generators.campaign_builder import (
        build_campaigns_from_catalog,
        catalog_row_to_product,
    )
    from src.catalog import load_catalog_from_yaml as _load_catalog

    try:
        case_path = _resolve_case_path(slug)
        case = load_case_config(case_path)
        client = _load_client_profile(slug, case)
        catalog = _load_catalog((case_path.parent / case.catalog).resolve())
        catalog, _ = _maybe_clean_catalog(slug, catalog)
        products = [catalog_row_to_product(row) for row in catalog]
        if limit is not None:
            products = products[:limit]

        plan = build_campaigns_from_catalog(
            client, products, case.to_build_config(),
            lead_form_config=(
                case.extensions.lead_form.model_dump() if case.extensions.lead_form else None
            ),
            promotion_start_date=case.extensions.promotions.start_date,
            promotion_end_date=case.extensions.promotions.end_date,
            promotion_occasion=case.extensions.promotions.occasion,
            money_currency=case.extensions.promotions.money_currency,
        )
    except Exception as exc:
        rprint(f"[red]Plan build failed: {exc}[/red]")
        raise typer.Exit(1)

    # Confirmation
    total_ag = sum(len(c.ad_groups) for c in plan.campaigns)
    total_kw = sum(len(ag.keywords) for c in plan.campaigns for ag in c.ad_groups)
    total_ads = sum(len(ag.ads) for c in plan.campaigns for ag in c.ad_groups)
    preview = Table(title=f"Push preview: {slug} -> {account.customer_id}")
    preview.add_column("Entity")
    preview.add_column("Count", justify="right")
    preview.add_row("Campaigns", str(len(plan.campaigns)))
    preview.add_row("Ad groups", str(total_ag))
    preview.add_row("Keywords", str(total_kw))
    preview.add_row("RSAs", str(total_ads))
    preview.add_row("Promotions", str(len(plan.promotions)))
    preview.add_row("Lead forms", str(len(plan.lead_forms)))
    preview.add_row("Sitelinks", str(len(plan.sitelinks)))
    preview.add_row("Callouts", str(len(plan.callouts)))
    if dry_run:
        preview.add_row("[yellow]Mode[/yellow]", "[yellow]DRY RUN — no API calls[/yellow]")
    console.print(preview)

    if not dry_run and not yes:
        typer.confirm(
            f"\nPush {total_ag} ad groups and {total_kw} keywords to live account "
            f"{account.customer_id}?",
            abort=True,
        )

    suffix = name_suffix
    if auto_suffix and not suffix:
        suffix = " [" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "]"

    # Normalise the --bid-strategy override: empty → None, 'clicks' → 'MAXIMIZE_CLICKS'.
    bid_override: str | None = None
    if bid_strategy:
        bs = bid_strategy.strip().upper().replace("-", "_")
        if bs in ("CLICKS", "MAXIMIZE_CLICKS"):
            bid_override = "MAXIMIZE_CLICKS"
        elif bs in ("MANUAL_CPC", "CPC"):
            bid_override = "MANUAL_CPC"
        else:
            bid_override = bs

    # Resume mode: parse the campaign id (accept either '23869105844' or
    # the full 'customers/.../campaigns/23869105844' resource name).
    resume_id: str | None = None
    if resume:
        resume_id = resume.strip().split("/")[-1] if "/" in resume else resume.strip()
        if not resume_id.isdigit():
            rprint(f"[red]Invalid --resume value: {resume!r}. Expected a numeric campaign id.[/red]")
            raise typer.Exit(1)

    pusher = CampaignPusher(
        customer_id=account.customer_id,
        dry_run=dry_run,
        name_suffix=suffix,
        skip_lead_forms=skip_lead_forms,
        bid_strategy_override=bid_override,
        resume_campaign_id=resume_id,
    )
    try:
        report = pusher.push(plan)
    except Exception as exc:
        rprint(f"[red]Push failed: {exc}[/red]")
        raise typer.Exit(1)

    # Result table
    result = Table(title=f"Push result: {slug}")
    result.add_column("Entity")
    result.add_column("Created", justify="right")
    result.add_column("First resource name", overflow="fold")
    sections = [
        ("Budgets", report.budgets),
        ("Campaigns", report.campaigns),
        ("Campaign criteria", report.campaign_criteria),
        ("Ad groups", report.ad_groups),
        ("Keywords", report.keywords),
        ("RSAs", report.ads),
        ("Assets", report.assets),
        ("Asset links", report.asset_links),
    ]
    for label, items in sections:
        first = items[0].resource_name if items else "—"
        result.add_row(label, str(len(items)), first)
    console.print(result)
    if pusher.warnings:
        rprint("\n[yellow]Warnings:[/yellow]")
        for w in pusher.warnings:
            rprint(f"  - {w}")
    rprint(f"[green]Done in {report.elapsed_seconds:.1f}s.[/green]")
    rprint(
        f"\n[bold]Review the campaign in Google Ads UI[/bold] "
        f"(account {account.customer_id}). Campaigns are created PAUSED — flip to "
        f"ENABLED when ready."
    )


@case_app.command("apply-bids")
def case_apply_bids(
    slug: str = typer.Argument(..., help="Client slug (folder under clients/)"),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Report which ad-group cpc_bid_micros WOULD change; make no API calls.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
    name_suffix: str = typer.Option(
        "",
        "--name-suffix",
        help=(
            "Pass the same suffix that was used on the original `sem case push` "
            "so the ad-group name lookup hits the live entities."
        ),
    ),
    campaign_id: str = typer.Option(
        "",
        "--campaign-id",
        help=(
            "Identify the live campaign by ID instead of name. Required if the "
            "campaign was RENAMED after the push (e.g. a machine suffix stripped "
            "for client presentation). Ad groups are still matched by --name-suffix."
        ),
    ),
    base_cpc_sek: float = typer.Option(
        5.0,
        "--base-cpc-sek",
        help=(
            "Base manual CPC (in SEK) that the bid_modifier multiplies. Default 5.00 SEK. "
            "Each live ad group's cpc_bid_micros becomes base × modifier × 1e6."
        ),
    ),
) -> None:
    """Re-apply today's bid-rules plan to an already-pushed live campaign.

    Computes `apply_rules(today=date.today())` for each product in the case,
    then UPDATEs each existing ad group's `cpc_bid_micros` in place. Use this
    when a `during:` seasonality window flips and you want the live campaign
    to reflect the new modifiers WITHOUT re-pushing the entire structure.

    Typical operator workflow:

        # initial push (PAUSED)
        sem case push etraveli --auto-suffix --skip-lead-forms --yes

        # daily cron (or on-window-flip)
        sem case apply-bids etraveli --name-suffix "[<same suffix>]" --yes
    """
    from src.accounts.manager import get_account
    from src.apis.campaign_pusher import CampaignPusher
    from src.cases.config import load_case_config
    from src.cases.runner import _load_client_profile, _maybe_clean_catalog, _resolve_case_path
    from src.generators.campaign_builder import (
        build_campaigns_from_catalog,
        catalog_row_to_product,
    )
    from src.catalog import load_catalog_from_yaml as _load_catalog

    try:
        account = get_account(slug)
    except FileNotFoundError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    try:
        case_path = _resolve_case_path(slug)
        case = load_case_config(case_path)
        client = _load_client_profile(slug, case)
        catalog = _load_catalog((case_path.parent / case.catalog).resolve())
        catalog, _ = _maybe_clean_catalog(slug, catalog)
        products = [catalog_row_to_product(row) for row in catalog]
        plan = build_campaigns_from_catalog(
            client, products, case.to_build_config(),
            lead_form_config=(
                case.extensions.lead_form.model_dump() if case.extensions.lead_form else None
            ),
            promotion_start_date=case.extensions.promotions.start_date,
            promotion_end_date=case.extensions.promotions.end_date,
            promotion_occasion=case.extensions.promotions.occasion,
            money_currency=case.extensions.promotions.money_currency,
        )
    except Exception as exc:
        rprint(f"[red]Plan build failed: {exc}[/red]")
        raise typer.Exit(1)

    preview = Table(title=f"Bid apply preview: {slug} -> {account.customer_id}")
    preview.add_column("Modifier", justify="right")
    preview.add_column("Ad groups", justify="right")
    preview.add_column("Cpc micros", justify="right")
    from collections import Counter
    bands = Counter(
        round(ag.bid_modifier, 2)
        for c in plan.campaigns for ag in c.ad_groups
    )
    base_micros = int(base_cpc_sek * 1_000_000)
    for modifier, count in sorted(bands.items()):
        preview.add_row(
            f"{modifier:.2f}×", str(count), f"{int(base_micros * modifier):,}",
        )
    if dry_run:
        preview.add_row("[yellow]Mode[/yellow]", "[yellow]DRY RUN[/yellow]", "")
    console.print(preview)

    if not dry_run and not yes:
        total_ag = sum(len(c.ad_groups) for c in plan.campaigns)
        typer.confirm(
            f"\nUpdate cpc_bid_micros on {total_ag} ad groups in live account "
            f"{account.customer_id}?",
            abort=True,
        )

    pusher = CampaignPusher(
        customer_id=account.customer_id,
        dry_run=dry_run,
        name_suffix=name_suffix,
    )
    try:
        report = pusher.apply_bids(
            plan, base_cpc_micros=base_micros,
            campaign_id=(campaign_id or None),
        )
    except Exception as exc:
        rprint(f"[red]apply_bids failed: {exc}[/red]")
        raise typer.Exit(1)

    result = Table(title=f"apply_bids result: {slug}", show_header=False)
    result.add_column("Field", style="bold")
    result.add_column("Value")
    result.add_row("Intended updates", str(len(report.intended_updates)))
    result.add_row("Applied", str(len(report.applied)))
    result.add_row("Skipped (no live match)", str(len(report.skipped)))
    result.add_row("Elapsed", f"{report.elapsed_seconds:.1f}s")
    result.add_row("Mode", "DRY RUN" if report.dry_run else "LIVE")
    console.print(result)
    if report.skipped and not dry_run:
        rprint(
            f"\n[yellow]{len(report.skipped)} ad groups had no live counterpart by name.[/yellow]"
            " Confirm `--name-suffix` matches the push that created them."
        )
    rprint("[green]Done.[/green]")


@catalog_app.command("clean")
def catalog_clean(
    slug: str = typer.Argument(..., help="Client slug"),
) -> None:
    """Generate a cleaning proposal for a client's catalog.

    Writes `clients/<slug>/catalog/cleaning_log.json` + `cleaning_diff.md`.
    Review the .md, then run `sem catalog accept-fixes` to apply.
    """
    try:
        json_path, md_path = run_clean(slug)
    except FileNotFoundError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)
    rprint(f"[green]Proposal written.[/green]")
    rprint(f"  • [bold]Review:[/bold] {md_path}")
    rprint(f"  • [dim]Raw JSON: {json_path}[/dim]")
    rprint("Run [bold]sem catalog accept-fixes " + slug + "[/bold] to apply these diffs.")


@catalog_app.command("accept-fixes")
def catalog_accept_fixes(
    slug: str = typer.Argument(..., help="Client slug"),
) -> None:
    """Promote the latest cleaning proposal to the accepted file.

    Future `sem case run` invocations will automatically apply these diffs.
    """
    try:
        accepted = run_accept_fixes(slug)
    except FileNotFoundError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)
    rprint(f"[green]Accepted proposal: {accepted}[/green]")


@catalog_app.command("validate")
def catalog_validate(
    slug: str = typer.Argument(..., help="Client slug"),
    iata: bool = typer.Option(False, "--iata", help="Enforce IATA 3-letter primary key pattern."),
) -> None:
    """Validate a client's catalog and print a structured report."""
    from src.cases.config import load_case_config

    case_path = CLIENTS_DIR / slug / "case.yaml"
    if not case_path.exists():
        rprint(f"[red]Error: case.yaml not found at {case_path}[/red]")
        raise typer.Exit(1)
    case = load_case_config(case_path)
    catalog_path = (case_path.parent / case.catalog).resolve()
    catalog = load_catalog_from_yaml(catalog_path)

    schema = CatalogSchema()
    if iata:
        schema = CatalogSchema(primary_key_pattern=r"^[A-Z]{3}$")
    report = validate_catalog(catalog, schema)
    rprint(f"[bold]{report.summary()}[/bold]")

    if not report.issues:
        rprint("[green]No issues found.[/green]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Row")
    table.add_column("Severity")
    table.add_column("Code")
    table.add_column("Message", overflow="fold")
    for issue in report.issues[:50]:
        sev_color = {"error": "red", "warning": "yellow"}.get(issue.severity, "dim")
        table.add_row(
            issue.row_key,
            f"[{sev_color}]{issue.severity}[/{sev_color}]",
            issue.code,
            issue.message,
        )
    console.print(table)
    if len(report.issues) > 50:
        rprint(f"[dim](Showing 50 of {len(report.issues)} issues)[/dim]")
    if report.has_errors:
        raise typer.Exit(1)
