"""Account CRUD operations and active client context management."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.account import ManagedAccount
from src.utils.config import CLIENTS_DIR
from src.utils import config_manager
from src.accounts.config import write_account_config, read_account_config
from src.accounts.state import initialize_state

# Subdirectories created for every new client
_CLIENT_SUBDIRS = [
    "intake",
    "research",
    "competitors",
    "keywords",
    "campaigns",
    "exports",
    "reports",
    "audits",
]

_ARCHIVED_DIR_NAME = "_archived"


def create_account(
    name: str,
    customer_id: str,
    industry: Optional[str] = None,
    budget_sek: Optional[int] = None,
    display_name: Optional[str] = None,
) -> ManagedAccount:
    """Register a new client and create directory structure.

    Args:
        name: Client slug (kebab-case). Used as directory name.
        customer_id: Google Ads Customer ID in XXX-XXX-XXXX format.
        industry: Industry key matching industry_keywords.json (optional).
        budget_sek: Monthly budget in SEK (positive integer, optional).
        display_name: Human-readable business name. Derived from name if omitted.

    Returns:
        ManagedAccount model for the newly created client.

    Raises:
        ValueError: If a client with the given name already exists.
        pydantic.ValidationError: If name or customer_id fail validation.
    """
    if display_name is None:
        display_name = name.replace("-", " ").title()

    # Build and validate the model (raises ValidationError on bad input)
    account = ManagedAccount(
        name=name,
        customer_id=customer_id,
        display_name=display_name,
        industry=industry,
        monthly_budget_sek=budget_sek,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    client_dir = CLIENTS_DIR / name
    if client_dir.exists():
        raise ValueError(f"Client '{name}' already exists")

    # Create directory tree
    client_dir.mkdir(parents=True, exist_ok=False)
    for subdir in _CLIENT_SUBDIRS:
        (client_dir / subdir).mkdir(exist_ok=True)

    # Write account.yaml and workflow_state.json
    write_account_config(client_dir, account)
    initialize_state(client_dir)

    return account


def list_accounts() -> list[ManagedAccount]:
    """List all registered client accounts sorted by name.

    Skips the _archived directory and any directory without account.yaml.

    Returns:
        List of ManagedAccount models, sorted alphabetically by name.
    """
    if not CLIENTS_DIR.exists():
        return []

    accounts: list[ManagedAccount] = []
    for entry in sorted(CLIENTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name == _ARCHIVED_DIR_NAME:
            continue
        try:
            account = read_account_config(entry)
            accounts.append(account)
        except FileNotFoundError:
            # Skip directories that don't have account.yaml
            continue

    return accounts


def get_account(name: str) -> ManagedAccount:
    """Get a single client account by name.

    Args:
        name: Client slug.

    Returns:
        ManagedAccount model.

    Raises:
        FileNotFoundError: If no client directory named {name} exists.
    """
    client_dir = CLIENTS_DIR / name
    if not client_dir.exists():
        raise FileNotFoundError(f"Client '{name}' not found")
    return read_account_config(client_dir)


def remove_account(name: str, archive: bool = True) -> None:
    """Remove or archive a client account.

    Args:
        name: Client slug to remove.
        archive: If True (default), move to clients/_archived/. If False, delete permanently.

    Raises:
        FileNotFoundError: If the client does not exist.
    """
    # Verify exists (raises FileNotFoundError if not)
    get_account(name)

    client_dir = CLIENTS_DIR / name

    if archive:
        archived_parent = CLIENTS_DIR / _ARCHIVED_DIR_NAME
        archived_parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(client_dir), str(archived_parent / name))
    else:
        shutil.rmtree(client_dir)

    # If removed client was the active one, clear active_client
    current_active = get_active_client()
    if current_active == name:
        config_manager.set_value("active_client", None)


def set_active_client(name: str) -> None:
    """Set the active client in global config.yaml.

    Args:
        name: Client slug to activate.

    Raises:
        FileNotFoundError: If the client does not exist.
    """
    # Verify client exists
    get_account(name)
    config_manager.set_value("active_client", name)


def get_active_client() -> Optional[str]:
    """Get the currently active client slug from global config.yaml.

    Returns:
        Client name string, or None if no active client is set.
    """
    return config_manager.get_value("active_client")
