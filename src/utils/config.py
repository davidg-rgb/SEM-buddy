"""Configuration and settings for SEM Master.

Loads API keys from .env file. OAuth credentials are handled by the auth module.
Global operator settings are managed by config_manager (config.yaml).
"""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic import BaseModel
from dotenv import load_dotenv

import os

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CLIENTS_DIR = PROJECT_ROOT / "clients"


class Settings(BaseModel):
    anthropic_api_key: str | None = None
    spyfu_api_key: str | None = None
    valueserp_api_key: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        spyfu_api_key=os.getenv("SPYFU_API_KEY"),
        valueserp_api_key=os.getenv("VALUESERP_API_KEY"),
    )
