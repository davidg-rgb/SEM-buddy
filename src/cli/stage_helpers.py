"""Shared helpers for pipeline stage CLI commands.

Extracts the common pattern: resolve client, check prerequisites, update state.
Each stage command uses these helpers to stay small and focused.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.accounts.manager import get_account, get_active_client
from src.accounts.state import check_prerequisites, update_state
from src.utils.config import CLIENTS_DIR


def resolve_client(client_arg: Optional[str]) -> tuple[str, Path]:
    """Resolve a client name from a CLI argument or the active client setting.

    Args:
        client_arg: Client slug passed on the command line, or None.

    Returns:
        (name, client_dir) tuple where client_dir is the resolved Path.

    Raises:
        typer.Exit(1): If no client can be resolved or the client does not exist.
    """
    console = Console()

    name = client_arg or get_active_client()

    if not name:
        console.print(
            "[red]No client specified and no active client set. "
            "Use 'sem accounts switch <name>' or pass a client name.[/red]"
        )
        raise typer.Exit(1)

    try:
        get_account(name)
    except FileNotFoundError:
        console.print(f"[red]Client '{name}' not found. Use 'sem accounts list' to see available clients.[/red]")
        raise typer.Exit(1)

    return name, CLIENTS_DIR / name


def require_prerequisites(client_dir: Path, stage: str) -> None:
    """Assert that all prerequisite stages for *stage* are completed.

    Per PIPE-03: enforces stage prerequisites before executing a stage.

    Args:
        client_dir: Path to the client's directory.
        stage: The stage about to be run.

    Raises:
        typer.Exit(1): If any prerequisite stage is not yet completed.
    """
    console = Console()
    ok, missing = check_prerequisites(client_dir, stage)
    if not ok:
        console.print(
            f"[red]Cannot run '{stage}': prerequisite stages not completed: "
            f"{', '.join(missing)}[/red]"
        )
        raise typer.Exit(1)


def complete_stage(
    client_dir: Path,
    stage: str,
    console: Console,
    duration_seconds: float | None = None,
) -> None:
    """Mark a stage as completed in workflow_state.json and print a confirmation.

    Per PIPE-04: updates workflow_state.json after each stage completes.

    Args:
        client_dir: Path to the client's directory.
        stage: The stage that just finished.
        console: Rich Console for output.
        duration_seconds: Optional elapsed time to record in metadata.
    """
    metadata = {"duration_s": duration_seconds} if duration_seconds is not None else None
    update_state(client_dir, stage, "completed", metadata=metadata)
    console.print(f"[green]Stage '{stage}' completed.[/green]")


def mark_stage_started(client_dir: Path, stage: str) -> None:
    """Mark a stage as in-progress in workflow_state.json.

    Args:
        client_dir: Path to the client's directory.
        stage: The stage that is starting.
    """
    update_state(client_dir, stage, "in_progress")
