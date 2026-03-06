"""Campaign and ad models with Swedish ad character validation."""

from __future__ import annotations

from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Literal

from .client import GeoTarget


class AdHeadline(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_length(cls, v: str) -> str:
        if len(v) > 30:
            raise ValueError(f"Headline must be max 30 chars, got {len(v)}: '{v}'")
        return v

    @property
    def char_count(self) -> int:
        return len(self.text)


class AdDescription(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_length(cls, v: str) -> str:
        if len(v) > 90:
            raise ValueError(f"Description must be max 90 chars, got {len(v)}: '{v}'")
        return v

    @property
    def char_count(self) -> int:
        return len(self.text)


class ResponsiveSearchAd(BaseModel):
    headlines: list[AdHeadline] = Field(min_length=3, max_length=15)
    descriptions: list[AdDescription] = Field(min_length=2, max_length=4)
    final_url: HttpUrl
    path1: str = Field(default="", max_length=15)
    path2: str = Field(default="", max_length=15)


class Keyword(BaseModel):
    text: str
    match_type: Literal["BROAD", "PHRASE", "EXACT"] = "BROAD"
    monthly_searches: int | None = None
    avg_cpc_sek: float | None = None
    competition: Literal["LOW", "MEDIUM", "HIGH"] | None = None


class AdGroup(BaseModel):
    name: str
    theme: str
    keywords: list[Keyword] = []
    negative_keywords: list[str] = []
    ads: list[ResponsiveSearchAd] = []


class Campaign(BaseModel):
    name: str
    campaign_type: Literal["SEARCH", "DISPLAY", "PMAX"] = "SEARCH"
    status: str = "PAUSED"
    budget_sek_daily: float
    bid_strategy: str = "MAXIMIZE_CLICKS"
    geo_targets: list[GeoTarget] = []
    language_codes: list[str] = Field(default=["sv"])
    ad_schedule: dict | None = None
    ad_groups: list[AdGroup] = []


class Sitelink(BaseModel):
    text: str = Field(max_length=25)
    desc1: str = Field(default="", max_length=35)
    desc2: str = Field(default="", max_length=35)
    final_url: HttpUrl


class Callout(BaseModel):
    text: str = Field(max_length=25)


class StructuredSnippet(BaseModel):
    header: str
    values: list[str]


class CallExtension(BaseModel):
    phone_number: str
    country_code: str = "SE"


class CampaignPlan(BaseModel):
    campaigns: list[Campaign] = []
    sitelinks: list[Sitelink] = []
    callouts: list[Callout] = []
    snippets: list[StructuredSnippet] = []
    call_extensions: list[CallExtension] = []
