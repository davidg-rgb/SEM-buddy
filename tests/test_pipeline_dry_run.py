"""End-to-end dry-run pipeline test (INF-05).

Invokes the full pipeline via CliRunner with --dry-run so no external API calls
are made. All 8 stages (intake → report) must complete successfully.

CLIENTS_DIR is monkeypatched to a tmp_path so no data is written to the real
clients/ directory.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typer.testing import CliRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def patched_clients_dir(tmp_path, monkeypatch):
    """Redirect CLIENTS_DIR in all relevant modules to tmp_path."""
    monkeypatch.setattr("src.utils.config.CLIENTS_DIR", tmp_path)
    monkeypatch.setattr("src.cli.stage_helpers.CLIENTS_DIR", tmp_path)
    monkeypatch.setattr("src.accounts.manager.CLIENTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def test_client(patched_clients_dir):
    """Create a minimal test client account in the temp directory."""
    from src.accounts.manager import create_account

    create_account("dry-run-client", "123-456-7890", industry="vvs", budget_sek=15000)
    return "dry-run-client"


@pytest.fixture(scope="module")
def app():
    """Create the Typer app once for all tests in this module."""
    from src.cli.app import create_app

    return create_app()


# ---------------------------------------------------------------------------
# Individual stage dry-run tests
# ---------------------------------------------------------------------------


class TestStageDryRuns:
    """Verify that each stage command runs without error under --dry-run."""

    def _run_stages_up_to(self, client_name: str, stages: list[str]) -> None:
        """Run stages in sequence to satisfy prerequisites for the next stage."""
        runner = CliRunner()
        stage_map = {
            "intake": ("src.cli.intake_commands", "intake_app"),
            "research": ("src.cli.research_commands", "research_app"),
            "competitors": ("src.cli.competitors_commands", "competitors_app"),
            "keywords": ("src.cli.keywords_commands", "keywords_app"),
            "campaign": ("src.cli.campaign_commands", "campaign_app"),
            "validate": ("src.cli.validate_commands", "validate_app"),
            "export": ("src.cli.export_commands", "export_app"),
            "report": ("src.cli.report_commands", "report_app"),
        }
        for stage in stages:
            mod_path, attr = stage_map[stage]
            import importlib

            mod = importlib.import_module(mod_path)
            stage_app = getattr(mod, attr)
            args = ["--dry-run", client_name] if stage != "validate" else [client_name]
            result = runner.invoke(stage_app, args)
            assert result.exit_code == 0, (
                f"Stage '{stage}' failed with exit {result.exit_code}.\n"
                f"Output: {result.output[:500]}"
            )

    def test_intake_dry_run(self, test_client):
        runner = CliRunner()
        from src.cli.intake_commands import intake_app

        result = runner.invoke(intake_app, ["--dry-run", test_client])
        assert result.exit_code == 0, f"intake --dry-run failed: {result.output[:300]}"
        assert "Dry-run" in result.output or "dry" in result.output.lower()

    def test_research_dry_run(self, test_client):
        runner = CliRunner()
        self._run_stages_up_to(test_client, ["intake"])
        from src.cli.research_commands import research_app

        result = runner.invoke(research_app, ["--dry-run", test_client])
        assert result.exit_code == 0, f"research --dry-run failed: {result.output[:300]}"

    def test_competitors_dry_run(self, test_client):
        runner = CliRunner()
        self._run_stages_up_to(test_client, ["intake"])
        from src.cli.competitors_commands import competitors_app

        result = runner.invoke(competitors_app, ["--dry-run", test_client])
        assert result.exit_code == 0, f"competitors --dry-run failed: {result.output[:300]}"


# ---------------------------------------------------------------------------
# Full pipeline dry-run test
# ---------------------------------------------------------------------------


def test_pipeline_run_dry_run_e2e(test_client, app):
    """Invoke `sem pipeline run <client> --dry-run` end-to-end.

    All 8 stages must complete.  The output must contain a 'DRY RUN' or
    'Dry-run' indicator.  No Python tracebacks may appear in the output.
    """
    runner = CliRunner()
    result = runner.invoke(app, ["pipeline", "run", test_client, "--dry-run"])

    # Must complete successfully
    assert result.exit_code == 0, (
        f"pipeline run --dry-run exited {result.exit_code}.\n"
        f"Output (last 1000 chars): {result.output[-1000:]}"
    )

    # Must not contain Python tracebacks
    assert "Traceback" not in result.output, (
        f"Traceback found in output:\n{result.output[-1000:]}"
    )

    # Must contain dry-run indicator from the pipeline panel
    assert "Dry-run: yes" in result.output or "dry-run" in result.output.lower()

    # Must confirm pipeline completion
    assert "Pipeline complete" in result.output


def test_pipeline_status_command(test_client, app):
    """After a successful dry-run, `sem pipeline status` shows all stages completed."""
    runner = CliRunner()

    # Run full pipeline first
    run_result = runner.invoke(app, ["pipeline", "run", test_client, "--dry-run"])
    assert run_result.exit_code == 0

    # Now check status
    status_result = runner.invoke(app, ["pipeline", "status", test_client])
    assert status_result.exit_code == 0

    # All pipeline stages should appear in output
    from src.accounts.state import PIPELINE_STAGES

    for stage in PIPELINE_STAGES:
        assert stage in status_result.output, (
            f"Stage '{stage}' not found in pipeline status output"
        )
