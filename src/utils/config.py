"""Configuration and settings for SEM Master."""

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
    google_ads_developer_token: str | None = None
    google_ads_client_id: str | None = None
    google_ads_client_secret: str | None = None
    google_ads_refresh_token: str | None = None
    serp_api_key: str | None = None
    spyfu_api_key: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        google_ads_developer_token=os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
        google_ads_client_id=os.getenv("GOOGLE_ADS_CLIENT_ID"),
        google_ads_client_secret=os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
        google_ads_refresh_token=os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
        serp_api_key=os.getenv("SERP_API_KEY"),
        spyfu_api_key=os.getenv("SPYFU_API_KEY"),
    )
