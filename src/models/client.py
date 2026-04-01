"""Client profile models for SEM Master."""

from __future__ import annotations

from pydantic import BaseModel, HttpUrl, Field
from typing import Literal


class TargetAudience(BaseModel):
    age_range: tuple[int, int] = (25, 65)
    gender: Literal["all", "male", "female"] = "all"
    locations: list[str] = []
    b2b_or_b2c: Literal["b2b", "b2c", "both"] = "b2c"


class GeoTarget(BaseModel):
    name: str
    google_geo_id: int | None = None
    radius_km: float | None = None


class CampaignGoal(BaseModel):
    goal_type: str
    priority: int = 1
    target_cpa_sek: float | None = None


class ClientProfile(BaseModel):
    business_name: str
    website_url: HttpUrl
    industry: str
    products_services: list[str] = []
    target_audience: TargetAudience = TargetAudience()
    geographic_targets: list[GeoTarget] = []
    monthly_budget_sek: int = 10000
    campaign_goals: list[CampaignGoal] = []
    brand_voice: str = ""
    known_competitors: list[str] = []
    depth_level: Literal[1, 2, 3, 4] = 2
    language: str = "sv"
    google_ads_customer_id: str | None = None  # format XXX-XXX-XXXX
