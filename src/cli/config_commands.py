"""CLI commands for global configuration management."""

from __future__ import annotations

import typer
import yaml
from rich.console import Console
from rich.syntax import Syntax
from rich import print as rprint

from src.utils.config_manager import load_config, get_value, set_value, CONFIG_PATH

config_app = typer.Typer(name="config", help="Manage global configuration.")
console = Console()


def _parse_value(raw: str):
    """Parse a string value into the appropriate Python type.

    Attempts int, float, bool, null, then falls back to string.
    """
    # Null / None
    if raw.lower() in ("null", "none"):
        return None
    # Boolean
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    # Integer
    try:
        return int(raw)
    except ValueError:
        pass
    # Float
    try:
        return float(raw)
    except ValueError:
        pass
    # String fallback
    return raw


@config_app.command("show")
def show() -> None:
    """Display the current global configuration."""
    config = load_config()
    console.print(f"Config file: [bold]{CONFIG_PATH}[/bold]\n")
    yaml_text = yaml.dump(config, allow_unicode=True, default_flow_style=False)
    syntax = Syntax(yaml_text, "yaml", theme="monokai", word_wrap=True)
    console.print(syntax)


@config_app.command("set")
def set_cmd(
    key: str = typer.Argument(..., help="Config key in dot-notation (e.g., defaults.industry)"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a config value using dot-notation key."""
    parsed = _parse_value(value)
    try:
        set_value(key, parsed)
        rprint(f"[green]Set {key} = {parsed!r}[/green]")
    except Exception as exc:
        rprint(f"[red]Error setting {key}: {exc}[/red]")
        raise typer.Exit(1)


@config_app.command("edit")
def edit() -> None:
    """Open config.yaml in the default editor."""
    console.print(f"Config file: [bold]{CONFIG_PATH}[/bold]")
    try:
        typer.launch(str(CONFIG_PATH))
    except Exception:
        # Falls back to printing the path if no editor is available
        console.print("Could not open editor automatically. Edit the file above manually.")
