"""Tests for src/cli/app.py — CLI app creation, version, help, subcommand registration."""

from __future__ import annotations

import pytest
import typer

from typer.testing import CliRunner
from src.cli.app import create_app, __version__

runner = CliRunner()


@pytest.fixture(scope="module")
def app():
    """Create the Typer app once for the whole module."""
    return create_app()


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------


def test_create_app_returns_typer(app):
    """create_app() returns a typer.Typer instance."""
    assert isinstance(app, typer.Typer)


# ---------------------------------------------------------------------------
# --version flag
# ---------------------------------------------------------------------------


def test_version_flag(app):
    """--version prints the version string and exits with code 0."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output
    assert "2.0.0" in result.output


# ---------------------------------------------------------------------------
# --help flag
# ---------------------------------------------------------------------------


def test_help_flag(app):
    """--help prints the app description and exits with code 0."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Google Ads" in result.output or "campaign" in result.output.lower()


def test_subcommands_registered(app):
    """--help output contains all 14 registered command groups."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    expected_commands = [
        "config",
        "accounts",
        "auth",
        "intake",
        "research",
        "competitors",
        "keywords",
        "campaign",
        "validate",
        "export",
        "report",
        "pipeline",
        "templates",
        "audit",
    ]
    for cmd in expected_commands:
        assert cmd in result.output, f"Expected subcommand '{cmd}' in help output"


# ---------------------------------------------------------------------------
# No args
# ---------------------------------------------------------------------------


def test_no_args_shows_help(app):
    """Invoking with no arguments shows help text (no_args_is_help=True)."""
    result = runner.invoke(app, [])

    # Typer exits with 2 when showing help due to no args, but the output
    # must contain help text (indicating help was displayed, not an error).
    assert "Google Ads" in result.output or "config" in result.output
