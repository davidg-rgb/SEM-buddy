"""Competitor analysis models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class TransparencyAd(BaseModel):
    advertiser_name: str
    ad_text: str
    ad_format: str = ""
    first_seen: date | None = None
    last_seen: date | None = None
    regions: list[str] = []


class CompetitorProfile(BaseModel):
    name: str
    domain: str
    transparency_ads: list[TransparencyAd] = []
    top_keywords: list[str] = []
    estimated_monthly_spend_sek: float | None = None
    ad_copy_patterns: list[str] = []
