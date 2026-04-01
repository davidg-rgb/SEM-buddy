"""OAuth 2.0 desktop flow handler for Google Ads API.

Manages the InstalledAppFlow authorization, browser-based consent,
and token exchange. Returns google.oauth2.credentials.Credentials.
"""

from __future__ import annotations

import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.auth import AuthError

logger = logging.getLogger(__name__)

_GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"


def get_oauth_scopes() -> list[str]:
    """Return the required OAuth 2.0 scopes for Google Ads API access.

    Returns:
        List containing the Google Ads API scope.
    """
    return [_GOOGLE_ADS_SCOPE]


def run_oauth_flow(
    client_secret_path: Path,
    scopes: list[str] | None = None,
    port: int = 8080,
) -> Credentials:
    """Run the OAuth 2.0 desktop (installed app) flow.

    Opens a browser window for the user to grant consent, then exchanges
    the authorization code for access and refresh tokens.

    Retries up to 3 times with incrementing ports if the port is in use.

    Args:
        client_secret_path: Path to the client_secret.json file downloaded
            from Google Cloud Console.
        scopes: OAuth scopes to request. Defaults to get_oauth_scopes().
        port: Local port for the redirect server. Defaults to 8080.

    Returns:
        google.oauth2.credentials.Credentials with access_token and refresh_token.

    Raises:
        FileNotFoundError: If client_secret_path does not exist.
        AuthError: If the user denies access or a network error occurs.
    """
    if not client_secret_path.exists():
        raise FileNotFoundError(
            f"OAuth client secret file not found: {client_secret_path}\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials."
        )

    if scopes is None:
        scopes = get_oauth_scopes()

    max_attempts = 3
    last_error: OSError | None = None

    for attempt in range(max_attempts):
        current_port = port + attempt
        try:
            logger.debug(
                "Starting OAuth flow (attempt %d/%d) on port %d",
                attempt + 1,
                max_attempts,
                current_port,
            )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_path),
                scopes=scopes,
            )
            flow.run_local_server(
                port=current_port,
                open_browser=True,
                success_message="Authentication complete. You may close this tab.",
            )
            logger.info("OAuth flow completed successfully on port %d", current_port)
            return flow.credentials
        except OSError as e:
            logger.warning(
                "Port %d in use (attempt %d/%d): %s",
                current_port,
                attempt + 1,
                max_attempts,
                e,
            )
            last_error = e
            continue
        except Exception as e:
            # Covers user denial, network errors, and other flow failures
            raise AuthError(
                f"OAuth authentication failed: {e}\n"
                "Ensure you have network access and that the client secret is valid."
            ) from e

    raise AuthError(
        f"Could not bind to any port in range {port}–{port + max_attempts - 1}. "
        f"Last error: {last_error}"
    )
