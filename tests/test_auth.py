"""Unit tests for the auth package (oauth, credentials, token_refresh, google_ads_auth).

All external dependencies (keyring, Google auth library, InstalledAppFlow) are mocked
so these tests run without real credentials or network access.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from google.oauth2.credentials import Credentials

from src.auth import AuthError, StorageError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_credentials(
    token: str = "test-token",
    refresh_token: str = "test-refresh",
    client_id: str = "test-id.apps.googleusercontent.com",
    client_secret: str = "test-secret",
    token_uri: str = "https://oauth2.googleapis.com/token",
    expiry: datetime | None = None,
) -> Credentials:
    """Return a real google.oauth2.credentials.Credentials populated with test values."""
    return Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        expiry=expiry,
    )


# ===========================================================================
# 1. OAuth tests
# ===========================================================================

class TestGetOAuthScopes:
    def test_get_oauth_scopes_returns_list_with_adwords_scope(self):
        from src.auth.oauth import get_oauth_scopes

        scopes = get_oauth_scopes()

        assert isinstance(scopes, list)
        assert len(scopes) >= 1
        assert "https://www.googleapis.com/auth/adwords" in scopes


class TestRunOAuthFlow:
    def test_run_oauth_flow_file_not_found(self, tmp_path: Path):
        from src.auth.oauth import run_oauth_flow

        missing = tmp_path / "no_such_file.json"
        with pytest.raises(FileNotFoundError, match="client_secret.json" if False else ""):
            run_oauth_flow(missing)

    def test_run_oauth_flow_success(self, tmp_path: Path):
        from src.auth.oauth import run_oauth_flow

        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text("{}")

        mock_creds = _make_credentials()
        mock_flow = MagicMock()
        mock_flow.credentials = mock_creds

        with patch(
            "src.auth.oauth.InstalledAppFlow.from_client_secrets_file",
            return_value=mock_flow,
        ) as mock_factory:
            result = run_oauth_flow(secret_file, port=8080)

        mock_factory.assert_called_once()
        mock_flow.run_local_server.assert_called_once_with(
            port=8080,
            open_browser=True,
            success_message=pytest.approx("Authentication complete. You may close this tab.", abs=0),
        )
        assert result is mock_creds

    def test_run_oauth_flow_success_returns_credentials(self, tmp_path: Path):
        """Verify the function returns flow.credentials, not the flow itself."""
        from src.auth.oauth import run_oauth_flow

        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text("{}")

        mock_creds = _make_credentials()
        mock_flow = MagicMock()
        mock_flow.credentials = mock_creds

        with patch("src.auth.oauth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
            result = run_oauth_flow(secret_file)

        assert result is mock_creds

    def test_run_oauth_flow_port_retry(self, tmp_path: Path):
        """First two attempts raise OSError; third succeeds on port+2."""
        from src.auth.oauth import run_oauth_flow

        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text("{}")

        mock_creds = _make_credentials()
        mock_flow = MagicMock()
        mock_flow.credentials = mock_creds

        port_errors: list[int] = []

        def run_local_server_side_effect(port: int, **kwargs) -> None:
            port_errors.append(port)
            if port in (8080, 8081):
                raise OSError(f"Port {port} in use")
            # 8082 succeeds (returns None)

        mock_flow.run_local_server.side_effect = run_local_server_side_effect

        with patch("src.auth.oauth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
            result = run_oauth_flow(secret_file, port=8080)

        assert port_errors == [8080, 8081, 8082]
        assert result is mock_creds

    def test_run_oauth_flow_all_ports_fail(self, tmp_path: Path):
        """All 3 port attempts raise OSError — AuthError must be raised."""
        from src.auth.oauth import run_oauth_flow

        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text("{}")

        mock_flow = MagicMock()
        mock_flow.run_local_server.side_effect = OSError("Port in use")

        with patch("src.auth.oauth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
            with pytest.raises(AuthError, match="port"):
                run_oauth_flow(secret_file, port=8080)

    def test_run_oauth_flow_user_denial(self, tmp_path: Path):
        """Generic Exception from run_local_server wraps into AuthError."""
        from src.auth.oauth import run_oauth_flow

        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text("{}")

        mock_flow = MagicMock()
        mock_flow.run_local_server.side_effect = Exception("access_denied")

        with patch("src.auth.oauth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
            with pytest.raises(AuthError, match="OAuth authentication failed"):
                run_oauth_flow(secret_file, port=8080)


# ===========================================================================
# 2. Credentials tests
# ===========================================================================

class TestCredentials:
    """Tests for store_tokens / load_tokens / clear_tokens.

    All keyring calls are monkeypatched; TOKEN_FILE and KEY_FILE are redirected
    to tmp_path so no real disk writes occur outside tmp.
    """

    @pytest.fixture(autouse=True)
    def _patch_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Redirect TOKEN_FILE and KEY_FILE to tmp_path for every test."""
        import src.auth.credentials as creds_mod

        monkeypatch.setattr(creds_mod, "TOKEN_FILE", tmp_path / "tokens.enc")
        monkeypatch.setattr(creds_mod, "KEY_FILE", tmp_path / ".keyfile")

    def test_store_and_load_tokens_keyring(self, monkeypatch: pytest.MonkeyPatch):
        import src.auth.credentials as creds_mod

        stored: dict[tuple, str] = {}

        def fake_set_password(service, username, password):
            stored[(service, username)] = password

        def fake_get_password(service, username):
            return stored.get((service, username))

        def fake_delete_password(service, username):
            stored.pop((service, username), None)

        monkeypatch.setattr(creds_mod.keyring, "set_password", fake_set_password)
        monkeypatch.setattr(creds_mod.keyring, "get_password", fake_get_password)
        monkeypatch.setattr(creds_mod.keyring, "delete_password", fake_delete_password)

        original = _make_credentials()
        creds_mod.store_tokens(original)
        loaded = creds_mod.load_tokens()

        assert loaded is not None
        assert loaded.token == "test-token"
        assert loaded.refresh_token == "test-refresh"
        assert loaded.client_id == "test-id.apps.googleusercontent.com"
        assert loaded.client_secret == "test-secret"

    def test_store_tokens_keyring_fallback_to_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """When keyring.set_password raises, tokens must be written to TOKEN_FILE."""
        import src.auth.credentials as creds_mod

        monkeypatch.setattr(creds_mod.keyring, "set_password", MagicMock(side_effect=Exception("no keyring")))
        # get_password for the Fernet key also fails so the key falls through to file
        monkeypatch.setattr(creds_mod.keyring, "get_password", MagicMock(return_value=None))
        monkeypatch.setattr(creds_mod.keyring, "delete_password", MagicMock())

        original = _make_credentials()
        creds_mod.store_tokens(original)

        token_file: Path = creds_mod.TOKEN_FILE  # type: ignore[assignment]
        assert token_file.exists(), "TOKEN_FILE should be created on keyring failure"

    def test_load_tokens_returns_none_when_empty(self, monkeypatch: pytest.MonkeyPatch):
        """No keyring data and no token file — load_tokens returns None."""
        import src.auth.credentials as creds_mod

        monkeypatch.setattr(creds_mod.keyring, "get_password", MagicMock(return_value=None))

        result = creds_mod.load_tokens()
        assert result is None

    def test_clear_tokens(self, monkeypatch: pytest.MonkeyPatch):
        """After clear_tokens, load_tokens returns None."""
        import src.auth.credentials as creds_mod

        stored: dict[tuple, str] = {}

        def fake_set_password(service, username, password):
            stored[(service, username)] = password

        def fake_get_password(service, username):
            return stored.get((service, username))

        def fake_delete_password(service, username):
            stored.pop((service, username), None)

        monkeypatch.setattr(creds_mod.keyring, "set_password", fake_set_password)
        monkeypatch.setattr(creds_mod.keyring, "get_password", fake_get_password)
        monkeypatch.setattr(creds_mod.keyring, "delete_password", fake_delete_password)

        creds_mod.store_tokens(_make_credentials())
        creds_mod.clear_tokens()
        result = creds_mod.load_tokens()

        assert result is None

    def test_credentials_roundtrip_with_expiry(self, monkeypatch: pytest.MonkeyPatch):
        """Expiry is preserved (timezone-aware UTC) across store / load cycle."""
        import src.auth.credentials as creds_mod

        stored: dict[tuple, str] = {}

        monkeypatch.setattr(
            creds_mod.keyring,
            "set_password",
            lambda s, u, p: stored.__setitem__((s, u), p),
        )
        monkeypatch.setattr(
            creds_mod.keyring,
            "get_password",
            lambda s, u: stored.get((s, u)),
        )
        monkeypatch.setattr(creds_mod.keyring, "delete_password", MagicMock())

        expiry = datetime(2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc)
        original = _make_credentials(expiry=expiry)
        creds_mod.store_tokens(original)
        loaded = creds_mod.load_tokens()

        assert loaded is not None
        assert loaded.expiry is not None
        # google.oauth2.credentials.Credentials.expiry is naive UTC by convention —
        # its .expired check compares against _helpers.utcnow() which is naive.
        assert loaded.expiry.tzinfo is None
        naive_expiry = expiry.astimezone(timezone.utc).replace(tzinfo=None)
        assert loaded.expiry.replace(microsecond=0) == naive_expiry.replace(microsecond=0)


# ===========================================================================
# 3. Token refresh tests
# ===========================================================================

class TestEnsureValidToken:
    def test_ensure_valid_token_already_valid(self):
        from src.auth.token_refresh import ensure_valid_token

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.valid = True
        mock_creds.expired = False

        result = ensure_valid_token(mock_creds)

        assert result is mock_creds
        mock_creds.refresh.assert_not_called()

    def test_ensure_valid_token_refreshes_expired(self, monkeypatch: pytest.MonkeyPatch):
        """Expired creds with refresh_token trigger a refresh and store_tokens call."""
        import src.auth.token_refresh as tr_mod
        from src.auth.token_refresh import ensure_valid_token

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "valid-refresh-token"

        store_spy = MagicMock()
        monkeypatch.setattr(tr_mod, "store_tokens", store_spy)

        with patch("src.auth.token_refresh.google.auth.transport.requests.Request"):
            result = ensure_valid_token(mock_creds)

        mock_creds.refresh.assert_called_once()
        store_spy.assert_called_once_with(mock_creds)
        assert result is mock_creds

    def test_ensure_valid_token_no_refresh_token(self):
        """No refresh_token raises AuthError before any network call."""
        from src.auth.token_refresh import ensure_valid_token

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = False
        mock_creds.refresh_token = None

        with pytest.raises(AuthError, match="No refresh token"):
            ensure_valid_token(mock_creds)

    def test_ensure_valid_token_refresh_error(self, monkeypatch: pytest.MonkeyPatch):
        """google.auth.exceptions.RefreshError becomes AuthError."""
        import src.auth.token_refresh as tr_mod
        import google.auth.exceptions
        from src.auth.token_refresh import ensure_valid_token

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "some-token"
        mock_creds.refresh.side_effect = google.auth.exceptions.RefreshError("revoked")

        monkeypatch.setattr(tr_mod, "store_tokens", MagicMock())

        with patch("src.auth.token_refresh.google.auth.transport.requests.Request"):
            with pytest.raises(AuthError, match="Token refresh failed"):
                ensure_valid_token(mock_creds)


class TestCheckExpiry:
    def test_check_expiry_with_future_expiry(self):
        from src.auth.token_refresh import check_expiry

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_creds = MagicMock(spec=Credentials)
        mock_creds.expiry = future
        mock_creds.expired = False

        result = check_expiry(mock_creds)

        assert result["valid"] is True
        assert result["minutes_remaining"] is not None
        assert result["minutes_remaining"] > 0
        assert result["expires_at"] is not None

    def test_check_expiry_with_no_expiry(self):
        from src.auth.token_refresh import check_expiry

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.expiry = None
        mock_creds.valid = True

        result = check_expiry(mock_creds)

        assert result["expires_at"] is None
        assert result["minutes_remaining"] is None


# ===========================================================================
# 4. Google Ads auth tests
# ===========================================================================

class TestBuildGoogleAdsConfig:
    def test_build_google_ads_config_basic(self):
        from src.auth.google_ads_auth import build_google_ads_config

        creds = _make_credentials()
        config = build_google_ads_config(creds, developer_token="dev-tok-123")

        assert config["developer_token"] == "dev-tok-123"
        assert config["client_id"] == "test-id.apps.googleusercontent.com"
        assert config["client_secret"] == "test-secret"
        assert config["refresh_token"] == "test-refresh"
        assert config["use_proto_plus"] is True
        assert "login_customer_id" not in config

    def test_build_google_ads_config_strips_hyphens(self):
        from src.auth.google_ads_auth import build_google_ads_config

        creds = _make_credentials()
        config = build_google_ads_config(creds, "dev", login_customer_id="123-456-7890")

        assert config["login_customer_id"] == "1234567890"

    def test_build_google_ads_config_no_login_id(self):
        from src.auth.google_ads_auth import build_google_ads_config

        creds = _make_credentials()
        config = build_google_ads_config(creds, "dev", login_customer_id=None)

        assert "login_customer_id" not in config


class TestGetGoogleAdsClient:
    def test_get_google_ads_client_no_tokens(self, monkeypatch: pytest.MonkeyPatch):
        """load_tokens() returning None must raise AuthError."""
        import src.auth.google_ads_auth as gaa_mod

        monkeypatch.setattr(gaa_mod, "load_tokens", MagicMock(return_value=None))

        with pytest.raises(AuthError, match="Not authenticated"):
            gaa_mod.get_google_ads_client()

    def test_get_google_ads_client_no_developer_token(self, monkeypatch: pytest.MonkeyPatch):
        """Valid tokens but no developer_token in config raises AuthError."""
        import src.auth.google_ads_auth as gaa_mod

        mock_creds = _make_credentials()
        monkeypatch.setattr(gaa_mod, "load_tokens", MagicMock(return_value=mock_creds))
        monkeypatch.setattr(gaa_mod, "ensure_valid_token", MagicMock(return_value=mock_creds))

        mock_cfg = MagicMock()
        mock_cfg.get_value.return_value = None
        monkeypatch.setattr(gaa_mod, "config_manager", mock_cfg)

        with pytest.raises(AuthError, match="developer token"):
            gaa_mod.get_google_ads_client()
