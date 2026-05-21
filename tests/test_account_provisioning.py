"""Tests for C12 (create_customer_client) + C13 (invite_admin) — both mocked."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.apis.google_ads import (
    _format_customer_id,
    _normalize_customer_id,
    create_customer_client,
    invite_admin,
)


def test_normalize_strips_hyphens() -> None:
    assert _normalize_customer_id("123-456-7890") == "1234567890"
    assert _normalize_customer_id(" 4691807001 ") == "4691807001"


def test_format_inserts_hyphens() -> None:
    assert _format_customer_id("4691807001") == "469-180-7001"
    assert _format_customer_id(4691807001) == "469-180-7001"
    # Non-conforming → passes through
    assert _format_customer_id("abc") == "abc"


def _make_mock_client_for_create():
    """Build a mock google_ads_client where create_customer_client returns a
    new customer resource path."""
    client = MagicMock()
    customer_service = MagicMock()
    response = SimpleNamespace(resource_name="customers/9999999999")
    customer_service.create_customer_client.return_value = response
    client.get_service.return_value = customer_service
    # client.get_type returns a fresh Customer-like object
    client.get_type.return_value = SimpleNamespace(
        descriptive_name="", currency_code="", time_zone=""
    )
    return client, customer_service


def test_create_customer_client_returns_formatted_id() -> None:
    client, customer_service = _make_mock_client_for_create()
    with patch("src.auth.google_ads_auth.get_google_ads_client", return_value=client):
        new_id = create_customer_client(
            mcc_id="123-456-7890",
            descriptive_name="Etraveligroup Test account",
            currency_code="USD",
            time_zone="America/New_York",
        )
    assert new_id == "999-999-9999"
    # Verify the request payload (customer_service.create_customer_client called
    # with customer_id=manager and a Customer object)
    args, kwargs = customer_service.create_customer_client.call_args
    assert kwargs["customer_id"] == "1234567890"
    cc = kwargs["customer_client"]
    assert cc.descriptive_name == "Etraveligroup Test account"
    assert cc.currency_code == "USD"
    assert cc.time_zone == "America/New_York"


def test_create_customer_client_wraps_api_errors() -> None:
    client = MagicMock()
    client.get_service.return_value.create_customer_client.side_effect = RuntimeError(
        "Network down"
    )
    client.get_type.return_value = SimpleNamespace(
        descriptive_name="", currency_code="", time_zone=""
    )
    with patch("src.auth.google_ads_auth.get_google_ads_client", return_value=client):
        with pytest.raises(Exception) as exc_info:
            create_customer_client(
                mcc_id="123-456-7890",
                descriptive_name="X",
            )
    # Should wrap into a GoogleAdsApiError or a network-style ApiError
    assert "Network down" in str(exc_info.value)


def _make_mock_client_for_invite():
    """Mock for invite_admin path."""
    client = MagicMock()
    inv_service = MagicMock()
    result = SimpleNamespace(
        result=SimpleNamespace(
            resource_name="customers/1234567890/customerUserAccessInvitations/abc"
        )
    )
    inv_service.mutate_customer_user_access_invitation.return_value = result
    client.get_service.return_value = inv_service
    # Operation object has a `create` field we mutate
    op = SimpleNamespace(create=SimpleNamespace(email_address="", access_role=None))
    client.get_type.side_effect = lambda name: (
        op if name == "CustomerUserAccessInvitationOperation"
        else SimpleNamespace(AccessRole=SimpleNamespace(ADMIN="ADMIN_ENUM", STANDARD="STD_ENUM", READ_ONLY="RO_ENUM", EMAIL_ONLY="EO_ENUM"))
    )
    return client, inv_service, op


def test_invite_admin_sets_request_fields() -> None:
    client, inv_service, op = _make_mock_client_for_invite()
    with patch("src.auth.google_ads_auth.get_google_ads_client", return_value=client):
        resource = invite_admin(
            customer_id="123-456-7890",
            email="klaus.thorup@etraveligroup.com",
            access_role="ADMIN",
        )
    assert resource.endswith("/abc")
    assert op.create.email_address == "klaus.thorup@etraveligroup.com"
    assert op.create.access_role == "ADMIN_ENUM"
    # Customer id passed without hyphens
    args, kwargs = inv_service.mutate_customer_user_access_invitation.call_args
    assert kwargs["customer_id"] == "1234567890"


def test_invite_admin_rejects_invalid_role() -> None:
    with pytest.raises(ValueError, match="Invalid access_role"):
        invite_admin("123-456-7890", "x@y.com", access_role="OWNER")


def test_invite_admin_multiple_emails_in_sequence() -> None:
    client, inv_service, op = _make_mock_client_for_invite()
    with patch("src.auth.google_ads_auth.get_google_ads_client", return_value=client):
        invite_admin("123-456-7890", "a@x.com")
        invite_admin("123-456-7890", "b@x.com", access_role="STANDARD")
    # Two calls
    assert inv_service.mutate_customer_user_access_invitation.call_count == 2


def test_invite_admin_wraps_api_errors() -> None:
    client = MagicMock()
    client.get_service.return_value.mutate_customer_user_access_invitation.side_effect = RuntimeError(
        "Already invited"
    )
    op = SimpleNamespace(create=SimpleNamespace(email_address="", access_role=None))
    client.get_type.side_effect = lambda name: (
        op if name == "CustomerUserAccessInvitationOperation"
        else SimpleNamespace(AccessRole=SimpleNamespace(ADMIN="ADMIN_ENUM"))
    )
    with patch("src.auth.google_ads_auth.get_google_ads_client", return_value=client):
        with pytest.raises(Exception) as exc_info:
            invite_admin("123-456-7890", "dup@x.com", access_role="ADMIN")
    assert "Already invited" in str(exc_info.value)
