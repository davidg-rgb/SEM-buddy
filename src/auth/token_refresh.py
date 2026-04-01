"""Token validation and automatic refresh for SEM Master.

Checks whether OAuth credentials are still valid and refreshes them
automatically when they have expired, then re-persists the updated tokens.
"""

from __future__ import annotations

from datetime import datetime, timezone

import google.auth.exceptions
import google.auth.transport.requests
from google.oauth2.credentials import Credentials

from src.auth import AuthError, NotAuthenticatedError, TokenExpiredError
from src.auth.credentials import store_tokens


def ensure_valid_token(credentials: Credentials) -> Credentials:
    """Return valid credentials, refreshing them if expired.

    If the credentials are still valid (not expired), returns them as-is.
    If expired and a refresh_token is available, performs a token refresh
    and re-persists the updated credentials via store_tokens().

    Args:
        credentials: Current OAuth Credentials to validate/refresh.

    Returns:
        Valid (possibly refreshed) Credentials object.

    Raises:
        AuthError: If the token cannot be refreshed (no refresh token,
            server-side revocation, or network failure).
    """
    if credentials.valid and not credentials.expired:
        return credentials

    if credentials.refresh_token is None:
        raise NotAuthenticatedError(
            "No refresh token available.",
            hint="Re-authenticate with 'sem auth login'.",
        )

    if credentials.expired:
        try:
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            # Persist the refreshed tokens so the next call won't need to refresh
            store_tokens(credentials)
            return credentials
        except google.auth.exceptions.RefreshError as e:
            raise TokenExpiredError(
                f"Token refresh failed: {e}",
                hint="Re-authenticate with 'sem auth login'.",
            ) from e
        except Exception as e:
            raise TokenExpiredError(
                f"Network error during token refresh: {e}",
                hint="Check network connection, then 'sem auth login'.",
            ) from e

    # credentials.valid is False but not expired — edge case (e.g., revoked)
    raise TokenExpiredError(
        "Credentials are invalid or revoked.",
        hint="Re-authenticate with 'sem auth login'.",
    )


def check_expiry(credentials: Credentials) -> dict:
    """Return a summary of the credential's expiry status.

    Args:
        credentials: OAuth Credentials to inspect.

    Returns:
        Dict with keys:
            - valid (bool): True if credentials are not expired.
            - expires_at (datetime | None): UTC expiry datetime, or None if unknown.
            - minutes_remaining (int | None): Minutes until expiry, or None if unknown.
              Clamped to 0 — never negative.
    """
    if credentials.expiry is not None:
        expires_at = credentials.expiry
        # Ensure timezone-aware for correct timedelta calculation
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        delta = (expires_at - datetime.now(timezone.utc)).total_seconds()
        minutes_remaining = max(0, int(delta / 60))
        valid = not credentials.expired
        return {
            "valid": valid,
            "expires_at": expires_at,
            "minutes_remaining": minutes_remaining,
        }

    # No expiry information available
    return {
        "valid": credentials.valid,
        "expires_at": None,
        "minutes_remaining": None,
    }
