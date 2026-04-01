"""API error hierarchy for SEM Master.

All API-related exceptions inherit from ApiError which provides
message and hint attributes for actionable error display.
"""

from __future__ import annotations


class ApiError(Exception):
    """Base class for all API errors."""

    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)


class GoogleAdsApiError(ApiError):
    """Google Ads API returned an error.

    Wraps google.ads.googleads.errors.GoogleAdsFailure when available.
    """

    def __init__(self, message: str, hint: str = "", failure=None):
        self.failure = failure
        super().__init__(message, hint)


class QuotaExceededError(ApiError):
    """API rate limit or quota exceeded."""

    def __init__(
        self,
        message: str = "Google Ads API quota exceeded.",
        hint: str = (
            "Wait and retry, or check your API quota at console.cloud.google.com."
        ),
    ):
        super().__init__(message, hint)


class SpyFuApiError(ApiError):
    """SpyFu API error."""


class ValueSerpApiError(ApiError):
    """ValueSERP API error."""
