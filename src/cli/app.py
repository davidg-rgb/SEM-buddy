"""SEM Master CLI — Google Ads campaign automation for Swedish clients."""

from __future__ import annotations

import typer
import rich

__version__ = "2.0.0"


def version_callback(value: bool) -> None:
    """Print version string and exit when --version is passed."""
    if value:
        rich.print(f"[bold]SEM Master[/bold] v{__version__}")
        raise typer.Exit()


def create_app() -> typer.Typer:
    """Build and return the Typer app with all registered command groups.

    Returns:
        Configured Typer instance ready to run.
    """
    app = typer.Typer(
        name="sem",
        help="Google Ads campaign automation for Swedish/Nordic clients.",
        rich_markup_mode="rich",
        no_args_is_help=True,
    )

    @app.callback()
    def main_callback(
        version: bool = typer.Option(
            False,
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ) -> None:
        """SEM Master — automated Google Ads campaigns for Swedish clients."""
        pass

    # Lazy imports inside create_app to avoid circular imports and keep startup fast
    from src.cli.config_commands import config_app
    from src.cli.accounts_commands import accounts_app
    from src.cli.auth_commands import auth_app

    # Stage command groups (pipeline stages 1-8)
    from src.cli.intake_commands import intake_app
    from src.cli.research_commands import research_app
    from src.cli.competitors_commands import competitors_app
    from src.cli.keywords_commands import keywords_app
    from src.cli.campaign_commands import campaign_app
    from src.cli.validate_commands import validate_app
    from src.cli.export_commands import export_app
    from src.cli.report_commands import report_app

    # Pipeline orchestrator
    from src.cli.pipeline_commands import pipeline_app

    # Template system
    from src.cli.template_commands import template_app

    # Audit system
    from src.cli.audit_commands import audit_app

    # SEO analysis
    from src.cli.seo_commands import seo_app

    app.add_typer(config_app, name="config", help="View and modify global configuration.")
    app.add_typer(accounts_app, name="accounts", help="Manage client accounts.")
    app.add_typer(auth_app, name="auth", help="OAuth authentication and token management.")

    app.add_typer(intake_app, name="intake", help="Client onboarding — collect business information.")
    app.add_typer(research_app, name="research", help="Scrape and analyze client digital presence.")
    app.add_typer(competitors_app, name="competitors", help="Analyze competitor ad strategies.")
    app.add_typer(keywords_app, name="keywords", help="Generate and group keyword research.")
    app.add_typer(campaign_app, name="campaign", help="Build campaign structure with ad copy.")
    app.add_typer(validate_app, name="validate", help="Run pre-export validation checks.")
    app.add_typer(export_app, name="export", help="Export campaign to Google Ads Editor CSV.")
    app.add_typer(report_app, name="report", help="Generate strategy report.")

    app.add_typer(pipeline_app, name="pipeline", help="Run full or partial pipeline.")
    app.add_typer(template_app, name="templates", help="Save and reuse campaign templates.")
    app.add_typer(audit_app, name="audit", help="Compare live campaigns against recommendations.")
    app.add_typer(seo_app, name="seo", help="SEO-analys — on-page och teknisk SEO.")

    return app


def main() -> None:
    """Entry point invoked by the `sem` shell command."""
    app = create_app()
    app()
