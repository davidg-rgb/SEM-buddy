"""Tests for SEO CLI command — dry-run mode (no network required)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli.app import create_app
from src.utils.config import CLIENTS_DIR

runner = CliRunner()


@pytest.fixture
def app():
    return create_app()


def _seo_dir(slug: str) -> Path:
    """Return the expected SEO output directory for a client slug."""
    return CLIENTS_DIR / slug / "seo"


@pytest.fixture(autouse=True)
def cleanup_test_clients():
    """Clean up test client directories after each test."""
    yield
    import shutil
    for slug in ("example", "rival1", "rival"):
        d = CLIENTS_DIR / slug
        if d.exists():
            shutil.rmtree(d)


class TestSeoCliDryRun:
    def test_single_page_dry_run(self, app):
        result = runner.invoke(app, ["seo", "run", "https://example.se", "--dry-run"])
        assert result.exit_code == 0
        seo_dir = _seo_dir("example")
        assert (seo_dir / "seo_report.md").exists()
        assert (seo_dir / "seo_analysis.json").exists()

    def test_site_mode_dry_run(self, app):
        result = runner.invoke(app, ["seo", "run", "https://example.se", "--dry-run", "--mode", "site"])
        assert result.exit_code == 0
        seo_dir = _seo_dir("example")
        assert (seo_dir / "seo_report.md").exists()
        json_data = json.loads((seo_dir / "seo_analysis.json").read_text(encoding="utf-8"))
        assert json_data["mode"] == "site"
        assert json_data["site_data"] is not None

    def test_competitors_dry_run(self, app):
        result = runner.invoke(app, [
            "seo", "run", "https://example.se", "--dry-run",
            "--competitors", "https://rival1.se,https://rival2.se",
        ])
        assert result.exit_code == 0
        seo_dir = _seo_dir("example")
        json_data = json.loads((seo_dir / "seo_analysis.json").read_text(encoding="utf-8"))
        assert json_data["competitor_analysis"] is not None
        assert len(json_data["competitor_analysis"]["competitors"]) == 2

    def test_json_output_valid(self, app):
        runner.invoke(app, ["seo", "run", "https://example.se", "--dry-run"])
        seo_dir = _seo_dir("example")
        json_data = json.loads((seo_dir / "seo_analysis.json").read_text(encoding="utf-8"))
        assert "scorecard" in json_data
        assert "overall_score" in json_data["scorecard"]
        assert 0 <= json_data["scorecard"]["overall_score"] <= 100
        assert "issues" in json_data["scorecard"]
        assert len(json_data["scorecard"]["issues"]) > 0

    def test_report_has_swedish_sections(self, app):
        runner.invoke(app, ["seo", "run", "https://example.se", "--dry-run"])
        seo_dir = _seo_dir("example")
        report = (seo_dir / "seo_report.md").read_text(encoding="utf-8")
        assert "Sammanfattning" in report
        assert "SEO-poäng" in report
        assert "Handlingsplan" in report

    def test_xlsx_output(self, app):
        result = runner.invoke(app, [
            "seo", "run", "https://example.se", "--dry-run", "--output", "xlsx",
        ])
        assert result.exit_code == 0
        seo_dir = _seo_dir("example")
        assert (seo_dir / "seo_report.xlsx").exists()

    def test_url_without_scheme(self, app):
        result = runner.invoke(app, ["seo", "run", "example.se", "--dry-run"])
        assert result.exit_code == 0

    def test_competitor_report_section(self, app):
        runner.invoke(app, [
            "seo", "run", "https://example.se", "--dry-run",
            "--competitors", "https://rival.se",
        ])
        seo_dir = _seo_dir("example")
        report = (seo_dir / "seo_report.md").read_text(encoding="utf-8")
        assert "Konkurrentjämförelse" in report

    def test_client_flag_overrides_slug(self, app):
        """--client flag should use the provided name, not derive from URL."""
        result = runner.invoke(app, [
            "seo", "run", "https://example.se", "--dry-run", "--client", "my-custom-client",
        ])
        assert result.exit_code == 0
        seo_dir = CLIENTS_DIR / "my-custom-client" / "seo"
        assert (seo_dir / "seo_report.md").exists()
        # Clean up
        import shutil
        shutil.rmtree(CLIENTS_DIR / "my-custom-client", ignore_errors=True)


class TestSeoCliRegistration:
    def test_seo_command_exists(self, app):
        result = runner.invoke(app, ["seo", "--help"])
        assert result.exit_code == 0
        assert "SEO-analys" in result.output or "seo" in result.output.lower()

    def test_seo_run_help(self, app):
        result = runner.invoke(app, ["seo", "run", "--help"])
        assert result.exit_code == 0
        assert "--mode" in result.output
        assert "--competitors" in result.output
        assert "--dry-run" in result.output
        assert "--skip-lighthouse" in result.output


class TestSeoPdfExport:
    def test_pdf_output(self, app):
        result = runner.invoke(app, [
            "seo", "run", "https://example.se", "--dry-run", "--output", "pdf",
        ])
        assert result.exit_code == 0
        seo_dir = _seo_dir("example")
        assert (seo_dir / "seo_report.pdf").exists()
        assert (seo_dir / "seo_report.pdf").stat().st_size > 0
