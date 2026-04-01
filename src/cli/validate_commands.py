"""CLI command for the validate stage.

Runs 11 pre-export validation checks on the campaign plan JSON and prints
a pass/fail report to the terminal.
"""

from __future__ import annotations

import importlib.util
import json
import sys
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
from src.utils.config import PROJECT_ROOT

validate_app = typer.Typer(
    name="validate",
    help="Run pre-export validation checks on campaign plan.",
)

console = Console()


def _load_validate_module():
    """Load scripts/validate_campaign.py via importlib to avoid sys.path pollution."""
    spec = importlib.util.spec_from_file_location(
        "validate_campaign",
        PROJECT_ROOT / "scripts" / "validate_campaign.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@validate_app.callback(invoke_without_command=True)
def validate(
    client: Optional[str] = typer.Argument(
        None,
        help="Client slug (defaults to active client).",
    ),
) -> None:
    """Run all 11 pre-export validation checks on the campaign plan.

    Loads campaign.json from clients/{name}/campaigns/, runs every check
    defined in scripts/validate_campaign.py, and prints a coloured pass/fail
    report. Exits with code 1 if any check fails.
    """
    name, client_dir = resolve_client(client)
    require_prerequisites(client_dir, "validate")
    mark_stage_started(client_dir, "validate")

    start_time = time.monotonic()

    # --- Load campaign plan as raw dict (validate_campaign expects a plain dict) ---
    campaign_path = client_dir / "campaigns" / "campaign.json"
    if not campaign_path.exists():
        console.print(f"[red]campaign.json not found at {campaign_path}[/red]")
        raise typer.Exit(1)

    with open(campaign_path, encoding="utf-8") as f:
        plan_dict = json.load(f)

    # --- Run validations ---
    try:
        validate_mod = _load_validate_module()
        run_all_validations = validate_mod.run_all_validations
        print_report = validate_mod.print_report
    except Exception as e:
        console.print(f"[red]Could not load validation module: {e}[/red]")
        raise typer.Exit(1)

    results = run_all_validations(plan_dict)
    all_passed = print_report(results)

    duration = time.monotonic() - start_time

    if all_passed:
        complete_stage(client_dir, "validate", console, duration_seconds=duration)
    else:
        from src.accounts.state import update_state
        update_state(client_dir, "validate", "failed", metadata={"duration_s": duration})
        console.print(
            "[yellow]Warning: validation checks failed. "
            "Fix the issues above before exporting.[/yellow]"
        )
        raise typer.Exit(1)
