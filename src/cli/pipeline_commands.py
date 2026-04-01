"""Pipeline orchestrator commands — run all 8 stages end-to-end or partially.

Provides `sem pipeline run` and `sem pipeline status` commands.
Invokes each stage's Typer app via CliRunner so each stage's argument parsing,
prerequisite checks, and state updates run exactly as they would when called
individually.
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.accounts.state import PIPELINE_STAGES, get_pipeline_state
from src.cli.stage_helpers import resolve_client

pipeline_app = typer.Typer(
    name="pipeline",
    help="Run full or partial pipeline for a client.",
)

console = Console()

# Stages that do NOT accept a --dry-run flag
_STAGES_WITHOUT_DRY_RUN = {"validate"}


@pipeline_app.command("run")
def run(
    client: Optional[str] = typer.Argument(
        None,
        help="Client slug (defaults to active client).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run without API calls, use synthetic data for all stages.",
    ),
    from_stage: Optional[str] = typer.Option(
        None,
        "--from",
        help="Start pipeline from this stage (inclusive).",
    ),
    to_stage: Optional[str] = typer.Option(
        None,
        "--to",
        help="Stop pipeline after this stage (inclusive).",
    ),
) -> None:
    """Run the full pipeline or a partial slice for a client.

    All 8 stages are run in order: intake, research, competitors, keywords,
    campaign, validate, export, report.  Use --from/--to to run only a subset.
    Use --dry-run for end-to-end demo mode that skips external API calls.
    """
    # Validate --from / --to values
    if from_stage is not None and from_stage not in PIPELINE_STAGES:
        raise typer.BadParameter(
            f"'{from_stage}' is not a valid stage. "
            f"Valid stages: {', '.join(PIPELINE_STAGES)}",
            param_hint="--from",
        )
    if to_stage is not None and to_stage not in PIPELINE_STAGES:
        raise typer.BadParameter(
            f"'{to_stage}' is not a valid stage. "
            f"Valid stages: {', '.join(PIPELINE_STAGES)}",
            param_hint="--to",
        )

    name, client_dir = resolve_client(client)

    start_idx = PIPELINE_STAGES.index(from_stage) if from_stage else 0
    end_idx = PIPELINE_STAGES.index(to_stage) if to_stage else len(PIPELINE_STAGES) - 1

    if start_idx > end_idx:
        console.print(
            f"[red]--from stage '{from_stage}' comes after --to stage '{to_stage}'.[/red]"
        )
        raise typer.Exit(1)

    stages_to_run = PIPELINE_STAGES[start_idx : end_idx + 1]

    console.print(
        Panel(
            f"[bold]Client:[/bold]  {name}\n"
            f"[bold]Stages:[/bold]  {', '.join(stages_to_run)}\n"
            f"[bold]Dry-run:[/bold] {'yes' if dry_run else 'no'}",
            title="[bold cyan]Pipeline Run[/bold cyan]",
            border_style="cyan",
        )
    )

    # Lazy imports to avoid circular imports at module load time
    from src.cli.intake_commands import intake_app
    from src.cli.research_commands import research_app
    from src.cli.competitors_commands import competitors_app
    from src.cli.keywords_commands import keywords_app
    from src.cli.campaign_commands import campaign_app
    from src.cli.validate_commands import validate_app
    from src.cli.export_commands import export_app
    from src.cli.report_commands import report_app

    from typer.testing import CliRunner

    stage_apps = {
        "intake": intake_app,
        "research": research_app,
        "competitors": competitors_app,
        "keywords": keywords_app,
        "campaign": campaign_app,
        "validate": validate_app,
        "export": export_app,
        "report": report_app,
    }

    runner = CliRunner()
    total = len(stages_to_run)

    for i, stage in enumerate(stages_to_run, start=1):
        console.print(f"\n[bold cyan]Stage {i}/{total}: {stage}[/bold cyan]")

        # Build CLI args for this stage
        args: list[str] = [name]
        if dry_run and stage not in _STAGES_WITHOUT_DRY_RUN:
            args.append("--dry-run")

        result = runner.invoke(stage_apps[stage], args)

        # Always print stage output so the user sees progress
        if result.output:
            console.print(result.output, end="")

        if result.exit_code != 0:
            console.print(f"\n[red]Pipeline stopped at '{stage}' (exit code {result.exit_code}).[/red]")
            if result.exception:
                import traceback
                tb = "".join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__))
                console.print(f"[dim]{tb}[/dim]")
            raise typer.Exit(1)

        console.print(f"[green]  {stage} complete[/green]")

    console.print(
        f"\n[bold green]Pipeline complete for '{name}'.[/bold green]"
    )
    console.print(
        f"[dim]Output at: clients/{name}/exports/ and clients/{name}/reports/[/dim]"
    )


@pipeline_app.command("status")
def status(
    client: Optional[str] = typer.Argument(
        None,
        help="Client slug (defaults to active client).",
    ),
) -> None:
    """Show completion status for all 8 pipeline stages."""
    name, client_dir = resolve_client(client)

    try:
        state = get_pipeline_state(client_dir)
    except FileNotFoundError:
        console.print(
            f"[yellow]No workflow state found for '{name}'. "
            "Run 'sem intake {name}' to start the pipeline.[/yellow]"
        )
        raise typer.Exit(1)

    stages_state = state.get("stages", {})

    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Stage", style="bold", min_width=12)
    table.add_column("Status", min_width=12)
    table.add_column("Updated At", style="dim")

    _STATUS_STYLE = {
        "completed": "green",
        "in_progress": "yellow",
        "failed": "red",
        "pending": "dim",
    }

    for stage in PIPELINE_STAGES:
        entry = stages_state.get(stage, {})
        stage_status = entry.get("status", "pending")
        updated_at = entry.get("updated_at") or "—"
        style = _STATUS_STYLE.get(stage_status, "dim")
        table.add_row(stage, f"[{style}]{stage_status}[/{style}]", updated_at)

    console.print(
        Panel(
            table,
            title=f"[bold cyan]Pipeline Status — {name}[/bold cyan]",
            border_style="cyan",
        )
    )
