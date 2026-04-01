"""Global configuration management for SEM Master.

Manages ~/.sem-master/config.yaml with dot-notation access for operator-level settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".sem-master"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "version": "2.0",
    "active_client": None,
    "mcc_customer_id": None,
    "developer_token": None,
    "defaults": {
        "dry_run": False,
        "industry": None,
        "geo_targets": [{"name": "Sverige", "id": 2752}],
        "language_id": 1053,
        "ad_schedule": "07:00-21:00",
    },
    "api_keys": {
        "spyfu": None,
        "valueserp": None,
        "anthropic": None,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, adding missing keys from base."""
    result = dict(base)
    for key, base_val in base.items():
        if key not in override:
            result[key] = base_val
        elif isinstance(base_val, dict) and isinstance(override[key], dict):
            result[key] = _deep_merge(base_val, override[key])
        else:
            result[key] = override[key]
    # Include keys from override that are not in base
    for key in override:
        if key not in base:
            result[key] = override[key]
    return result


def ensure_config_dir() -> Path:
    """Create ~/.sem-master/ and required subdirectories if they don't exist.

    Returns:
        Path to the config directory (~/.sem-master/).
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "credentials").mkdir(exist_ok=True)
    (CONFIG_DIR / "templates").mkdir(exist_ok=True)
    return CONFIG_DIR


def load_config() -> dict:
    """Load config.yaml, creating it with defaults if missing.

    Deep-merges loaded config with DEFAULT_CONFIG so any missing keys
    are filled in from defaults (handles upgrades gracefully).

    Returns:
        Config dict with all default keys present.
    """
    ensure_config_dir()
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}

    # Deep-merge: defaults fill in any keys missing from the stored config
    merged = _deep_merge(DEFAULT_CONFIG, loaded)
    return merged


def save_config(config: dict) -> None:
    """Write config dict to ~/.sem-master/config.yaml.

    Args:
        config: The configuration dict to save.
    """
    ensure_config_dir()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def get_value(key: str) -> Any:
    """Get a config value by dot-notation key.

    Args:
        key: Dot-separated key path, e.g. "defaults.industry" or "active_client".

    Returns:
        The value at the given key path, or None if not found.
    """
    config = load_config()
    parts = key.split(".")
    current: Any = config
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def set_value(key: str, value: Any) -> None:
    """Set a config value by dot-notation key and persist to disk.

    Creates intermediate dicts as needed.

    Args:
        key: Dot-separated key path, e.g. "defaults.industry".
        value: The value to set.
    """
    config = load_config()
    parts = key.split(".")
    current = config
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value
    save_config(config)
