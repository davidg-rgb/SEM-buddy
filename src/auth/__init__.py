"""Authentication package for SEM Master.

Provides OAuth 2.0 desktop flow, secure token storage (keyring + Fernet fallback),
and automatic token refresh for Google Ads API access.
"""

__all__ = [
    "AuthError",
    "NotAuthenticatedError",
    "TokenExpiredError",
    "InsufficientScopeError",
    "AccountAccessDeniedError",
    "StorageError",
    "CredentialStorageError",
]


class AuthError(Exception):
    """Base authentication error with actionable hint."""

    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)


class NotAuthenticatedError(AuthError):
    """No tokens found — user has not authenticated."""

    def __init__(self, message: str = "Not authenticated.", hint: str = "Run 'sem auth login' first."):
        super().__init__(message, hint)


class TokenExpiredError(AuthError):
    """Token refresh failed or tokens have been revoked."""

    def __init__(self, message: str = "Token expired and refresh failed.", hint: str = "Re-authenticate with 'sem auth login'."):
        super().__init__(message, hint)


class InsufficientScopeError(AuthError):
    """Required OAuth scope is missing from the granted token."""

    def __init__(self, message: str = "Insufficient OAuth scope.", hint: str = "Re-authenticate with 'sem auth login --force'."):
        super().__init__(message, hint)


class AccountAccessDeniedError(AuthError):
    """Customer ID is not accessible under the MCC account."""

    def __init__(self, message: str = "Account access denied.", hint: str = "Verify the account is linked to your MCC."):
        super().__init__(message, hint)


class StorageError(Exception):
    """Base storage error with actionable hint."""

    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)


class CredentialStorageError(StorageError):
    """Cannot store or retrieve tokens from any backend."""

    def __init__(self, message: str = "Cannot store credentials.", hint: str = "Check keyring availability or file permissions."):
        super().__init__(message, hint)
