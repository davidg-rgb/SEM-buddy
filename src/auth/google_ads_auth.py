"""Google Ads API client factory for SEM Master.

Builds an authenticated GoogleAdsClient from stored OAuth tokens and
operator configuration (developer token, MCC customer ID).
"""

from __future__ import annotations

import logging
from typing import Optional

from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from src.auth import AuthError
from src.auth.credentials import load_tokens
from src.auth.token_refresh import ensure_valid_token
from src.utils import config_manager

logger = logging.getLogger(__name__)


def build_google_ads_config(
    credentials: Credentials,
    developer_token: str,
    login_customer_id: Optional[str] = None,
) -> dict:
    """Build a config dict compatible with GoogleAdsClient.load_from_dict().

    Args:
        credentials: Valid OAuth Credentials with client_id, client_secret,
            and refresh_token populated.
        developer_token: Google Ads API developer token from MCC account.
        login_customer_id: MCC customer ID used as the login customer.
            Hyphens are stripped automatically. Omitted if None.

    Returns:
        Dict with keys: developer_token, client_id, client_secret,
        refresh_token, use_proto_plus, and optionally login_customer_id.
    """
    config: dict = {
        "developer_token": developer_token,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "refresh_token": credentials.refresh_token,
        "use_proto_plus": True,
    }

    if login_customer_id is not None:
        # Strip hyphens — Google Ads API expects numeric IDs without separators
        config["login_customer_id"] = login_customer_id.replace("-", "")

    return config


def get_google_ads_client(customer_id: Optional[str] = None) -> GoogleAdsClient:
    """Create and return an authenticated GoogleAdsClient.

    Loads stored OAuth tokens, refreshes if expired, reads the developer
    token and MCC customer ID from config, then instantiates the client.

    Args:
        customer_id: Optional customer ID override. Currently unused in
            client construction but reserved for future per-request scoping.

    Returns:
        Authenticated GoogleAdsClient ready for API calls.

    Raises:
        AuthError: If no tokens are stored, the token cannot be refreshed,
            or the developer token is not configured.
    """
    credentials = load_tokens()
    if credentials is None:
        raise AuthError(
            "Not authenticated. Run 'sem auth login' first."
        )

    credentials = ensure_valid_token(credentials)

    developer_token = config_manager.get_value("developer_token")
    if developer_token is None:
        raise AuthError(
            "No developer token configured. "
            "Run 'sem config set developer_token YOUR_TOKEN'."
        )

    mcc_customer_id = config_manager.get_value("mcc_customer_id")

    config_dict = build_google_ads_config(credentials, developer_token, mcc_customer_id)

    logger.debug(
        "Building GoogleAdsClient (login_customer_id=%s)",
        config_dict.get("login_customer_id"),
    )

    return GoogleAdsClient.load_from_dict(config_dict)
