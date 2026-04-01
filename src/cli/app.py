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

    app.add_typer(config_app, name="config", help="View and modify global configuration.")
    app.add_typer(accounts_app, name="accounts", help="Manage client accounts.")
    app.add_typer(auth_app, name="auth", help="OAuth authentication and token management.")

    return app


def main() -> None:
    """Entry point invoked by the `sem` shell command."""
    app = create_app()
    app()
