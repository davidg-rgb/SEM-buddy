"""Per-client account configuration (account.yaml in client directory)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from src.models.account import ManagedAccount


def write_account_config(client_dir: Path, account: ManagedAccount) -> None:
    """Write account.yaml to client directory.

    Args:
        client_dir: Path to the client's directory (e.g., clients/my-client/).
        account: ManagedAccount model to serialize.
    """
    data = account.model_dump()
    # Convert datetime objects to ISO strings for YAML serialization
    for field in ("created_at", "updated_at"):
        if isinstance(data.get(field), datetime):
            data[field] = data[field].isoformat()

    config_path = client_dir / "account.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def read_account_config(client_dir: Path) -> ManagedAccount:
    """Read account.yaml and return ManagedAccount model.

    Args:
        client_dir: Path to the client's directory.

    Returns:
        ManagedAccount model parsed from account.yaml.

    Raises:
        FileNotFoundError: If account.yaml does not exist in client_dir.
    """
    config_path = client_dir / "account.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"account.yaml not found in {client_dir}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Parse ISO strings back to datetime objects
    for field in ("created_at", "updated_at"):
        if isinstance(data.get(field), str):
            data[field] = datetime.fromisoformat(data[field])

    return ManagedAccount(**data)


def update_account_config(client_dir: Path, updates: dict) -> None:
    """Merge updates into existing account.yaml and refresh updated_at timestamp.

    Args:
        client_dir: Path to the client's directory.
        updates: Dict of fields to update on the account.

    Raises:
        FileNotFoundError: If account.yaml does not exist in client_dir.
    """
    account = read_account_config(client_dir)
    # Apply updates to a dict copy, then rebuild the model
    data = account.model_dump()
    data.update(updates)
    data["updated_at"] = datetime.now()

    updated_account = ManagedAccount(**data)
    write_account_config(client_dir, updated_account)
