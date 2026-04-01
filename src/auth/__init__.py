"""Authentication package for SEM Master.

Provides OAuth 2.0 desktop flow, secure token storage (keyring + Fernet fallback),
and automatic token refresh for Google Ads API access.
"""

__all__ = ["AuthError", "StorageError"]


class AuthError(Exception):
    """Raised when authentication fails or tokens cannot be refreshed."""
    pass


class StorageError(Exception):
    """Raised when token storage or retrieval fails."""
    pass
