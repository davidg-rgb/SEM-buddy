"""Unit tests for src/accounts/manager.py — CRUD and active client management.

CLIENTS_DIR is redirected to tmp_path for every test so no real client
directories are created or modified.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.models.account import ManagedAccount


# ---------------------------------------------------------------------------
# Fixture: redirect CLIENTS_DIR and config_manager to isolated tmp_path
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_clients_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect all CLIENTS_DIR references to a fresh tmp dir for each test."""
    import src.accounts.manager as mgr_mod
    import src.utils.config as config_mod

    monkeypatch.setattr(mgr_mod, "CLIENTS_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "CLIENTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def mock_config(monkeypatch: pytest.MonkeyPatch):
    """Replace config_manager with a simple in-memory dict-backed mock."""
    import src.accounts.manager as mgr_mod

    store: dict = {}
    mock_cfg = MagicMock()
    mock_cfg.get_value.side_effect = lambda key: store.get(key)
    mock_cfg.set_value.side_effect = lambda key, val: store.__setitem__(key, val)
    monkeypatch.setattr(mgr_mod, "config_manager", mock_cfg)
    return mock_cfg, store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateAccount:
    def test_create_account_basic(self, tmp_path: Path):
        from src.accounts.manager import create_account

        account = create_account("acme", "123-456-7890", industry="bygg_renovering", budget_sek=25000)

        assert isinstance(account, ManagedAccount)
        assert account.name == "acme"
        assert account.customer_id == "123-456-7890"
        assert account.industry == "bygg_renovering"
        assert account.monthly_budget_sek == 25000

    def test_create_account_creates_subdirectories(self, tmp_path: Path):
        from src.accounts.manager import create_account

        create_account("acme", "123-456-7890")

        expected_subdirs = ["intake", "research", "competitors", "keywords", "campaigns", "exports", "reports", "audits"]
        client_dir = tmp_path / "acme"
        for subdir in expected_subdirs:
            assert (client_dir / subdir).is_dir(), f"Missing subdirectory: {subdir}"

    def test_create_account_writes_account_yaml(self, tmp_path: Path):
        from src.accounts.manager import create_account

        create_account("acme", "123-456-7890")

        assert (tmp_path / "acme" / "account.yaml").exists()

    def test_create_account_writes_workflow_state(self, tmp_path: Path):
        from src.accounts.manager import create_account

        create_account("acme", "123-456-7890")

        assert (tmp_path / "acme" / "workflow_state.json").exists()

    def test_create_account_duplicate_raises_value_error(self, tmp_path: Path):
        from src.accounts.manager import create_account

        create_account("acme", "123-456-7890")
        with pytest.raises(ValueError, match="already exists"):
            create_account("acme", "999-888-7777")

    def test_create_account_invalid_name_raises_validation_error(self):
        from src.accounts.manager import create_account

        with pytest.raises(ValidationError):
            create_account("Acme Corp", "123-456-7890")

    def test_create_account_invalid_customer_id_raises_validation_error(self):
        from src.accounts.manager import create_account

        with pytest.raises(ValidationError):
            create_account("acme", "12345")

    def test_create_account_display_name_derived_from_name(self, tmp_path: Path):
        from src.accounts.manager import create_account

        account = create_account("my-client", "123-456-7890")

        assert account.display_name == "My Client"


class TestListAccounts:
    def test_list_accounts_returns_all(self, tmp_path: Path):
        from src.accounts.manager import create_account, list_accounts

        create_account("alpha", "111-111-1111")
        create_account("beta", "222-222-2222")
        create_account("gamma", "333-333-3333")

        accounts = list_accounts()

        assert len(accounts) == 3
        assert [a.name for a in accounts] == ["alpha", "beta", "gamma"]

    def test_list_accounts_empty_dir(self, tmp_path: Path):
        from src.accounts.manager import list_accounts

        # tmp_path is empty (no clients created)
        accounts = list_accounts()
        assert accounts == []

    def test_list_accounts_skips_archived(self, tmp_path: Path):
        from src.accounts.manager import create_account, list_accounts

        create_account("active", "111-111-1111")
        # Manually create an _archived directory with a file inside
        archived = tmp_path / "_archived" / "old-client"
        archived.mkdir(parents=True)

        accounts = list_accounts()

        assert len(accounts) == 1
        assert accounts[0].name == "active"

    def test_list_accounts_skips_dirs_without_account_yaml(self, tmp_path: Path):
        from src.accounts.manager import create_account, list_accounts

        create_account("valid", "111-111-1111")
        # Create a directory without account.yaml
        (tmp_path / "no-yaml").mkdir()

        accounts = list_accounts()

        assert len(accounts) == 1


class TestGetAccount:
    def test_get_account_returns_correct_model(self, tmp_path: Path):
        from src.accounts.manager import create_account, get_account

        created = create_account("acme", "123-456-7890")
        fetched = get_account("acme")

        assert fetched.name == created.name
        assert fetched.customer_id == created.customer_id

    def test_get_account_not_found_raises_file_not_found(self):
        from src.accounts.manager import get_account

        with pytest.raises(FileNotFoundError, match="not found"):
            get_account("nonexistent")


class TestRemoveAccount:
    def test_remove_account_archive_true(self, tmp_path: Path):
        from src.accounts.manager import create_account, remove_account

        create_account("acme", "123-456-7890")
        remove_account("acme", archive=True)

        assert not (tmp_path / "acme").exists()
        assert (tmp_path / "_archived" / "acme").exists()

    def test_remove_account_permanent(self, tmp_path: Path):
        from src.accounts.manager import create_account, remove_account

        create_account("acme", "123-456-7890")
        remove_account("acme", archive=False)

        assert not (tmp_path / "acme").exists()
        assert not (tmp_path / "_archived" / "acme").exists()

    def test_remove_nonexistent_raises_file_not_found(self):
        from src.accounts.manager import remove_account

        with pytest.raises(FileNotFoundError):
            remove_account("ghost")


class TestActiveClient:
    def test_set_and_get_active_client(self, tmp_path: Path, mock_config):
        from src.accounts.manager import create_account, set_active_client, get_active_client

        _, store = mock_config
        create_account("acme", "123-456-7890")
        set_active_client("acme")

        assert store.get("active_client") == "acme"
        assert get_active_client() == "acme"

    def test_remove_active_client_clears_active(self, tmp_path: Path, mock_config):
        from src.accounts.manager import create_account, set_active_client, get_active_client, remove_account

        _, store = mock_config
        create_account("acme", "123-456-7890")
        set_active_client("acme")
        remove_account("acme", archive=False)

        # After removal, active_client should be cleared (None)
        assert get_active_client() is None
