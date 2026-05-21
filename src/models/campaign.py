"""Campaign and ad models with character validators and catalog-driven extensions."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

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
    keywords: list[Keyword] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    ads: list[ResponsiveSearchAd] = Field(default_factory=list)
    # Catalog extensions ----------------------------------------------------
    bid_modifier: float = Field(
        default=1.0,
        description=(
            "Multiplier applied at the ad-group level. 1.0 = no change; "
            "Google Ads accepts values 0.1–10.0. Emitted as 'Bid modifier' "
            "to the Ad Groups CSV."
        ),
    )
    max_cpc_sek: float | None = Field(
        default=None,
        description="Optional explicit max CPC override (manual bidding only).",
    )
    target_cpa_micros: int | None = Field(
        default=None,
        description="Optional ad-group-level target CPA override (in micros).",
    )

    @field_validator("bid_modifier")
    @classmethod
    def _validate_bid_modifier(cls, v: float) -> float:
        if v < 0.1 or v > 10.0:
            raise ValueError(
                f"bid_modifier must be between 0.1 and 10.0 (Google Ads limit); got {v}"
            )
        return v


class Campaign(BaseModel):
    name: str
    campaign_type: Literal["SEARCH", "DISPLAY", "PMAX"] = "SEARCH"
    status: str = "PAUSED"
    budget_sek_daily: float
    bid_strategy: str = "MAXIMIZE_CLICKS"
    geo_targets: list[GeoTarget] = Field(default_factory=list)
    language_codes: list[str] = Field(default=["sv"])
    ad_schedule: dict | None = None
    ad_groups: list[AdGroup] = Field(default_factory=list)


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


# ---------------------------------------------------------------------------
# Promotion Extension (C5)
# ---------------------------------------------------------------------------


PromotionDiscountModifier = Literal["UP_TO", "NONE"]


class PromotionExtension(BaseModel):
    """One promotion extension — typically one per catalog row.

    Either `percent_off` OR `money_amount_off` must be set (mutually exclusive
    per Google Ads spec). Campaign-level if `ad_group_name` is None.
    """

    campaign_name: str
    ad_group_name: str | None = None
    discount_modifier: PromotionDiscountModifier = "UP_TO"
    percent_off: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Percent off (0–100). Mutually exclusive with money_amount_off.",
    )
    money_amount_off: float | None = Field(
        default=None,
        ge=0.0,
        description="Money amount off. Mutually exclusive with percent_off.",
    )
    money_currency: str = "SEK"
    promotion_code: str | None = None
    orders_over_amount: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    final_url: HttpUrl
    final_url_suffix: str | None = None
    tracking_template: str | None = None
    language: str = "en"
    occasion: str | None = None

    @model_validator(mode="after")
    def _exactly_one_discount(self) -> PromotionExtension:
        a = self.percent_off is not None
        b = self.money_amount_off is not None
        if a == b:
            raise ValueError(
                "Exactly one of percent_off or money_amount_off must be set "
                f"(got percent_off={self.percent_off}, money_amount_off={self.money_amount_off})"
            )
        return self

    @model_validator(mode="after")
    def _dates_ordered(self) -> PromotionExtension:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


# ---------------------------------------------------------------------------
# Lead Form Extension (C6)
# ---------------------------------------------------------------------------


# Google's actual lead form field whitelist is much larger; this covers the
# common ones a campaign builder cares about.
LeadFormField = Literal[
    "FULL_NAME",
    "FIRST_NAME",
    "LAST_NAME",
    "EMAIL",
    "PHONE_NUMBER",
    "POSTAL_CODE",
    "CITY",
    "REGION",
    "COUNTRY",
    "COMPANY_NAME",
    "JOB_TITLE",
    "WORK_EMAIL",
    "WORK_PHONE_NUMBER",
]


LeadFormCTA = Literal[
    "GET_QUOTE",
    "APPLY_NOW",
    "BOOK_NOW",
    "CONTACT_US",
    "DOWNLOAD",
    "LEARN_MORE",
    "SIGN_UP",
    "SUBSCRIBE",
    "GET_OFFER",
]


class LeadFormExtension(BaseModel):
    """One Lead Form asset per campaign."""

    campaign_name: str
    asset_name: str = Field(default="", max_length=80)
    form_name: str = Field(max_length=80)
    headline: str = Field(max_length=30)
    description: str = Field(max_length=200)
    cta_description: str = Field(
        default="",
        max_length=200,
        description=(
            "Short text shown next to the CTA button (Google Ads "
            "`call_to_action_description`). Defaults to a truncation of "
            "`description` when empty."
        ),
    )
    business_name: str = Field(max_length=25)
    cta: LeadFormCTA = "GET_QUOTE"
    privacy_url: HttpUrl
    fields: list[LeadFormField] = Field(min_length=1, max_length=10)
    submit_headline: str = Field(default="Tack!", max_length=30)
    submit_description: str = Field(default="", max_length=200)
    submit_url: HttpUrl | None = None  # optional post-submit redirect

    @model_validator(mode="after")
    def _default_asset_name(self) -> LeadFormExtension:
        if not self.asset_name:
            object.__setattr__(self, "asset_name", self.form_name)
        if not self.cta_description:
            # Use the headline as a short CTA description — Google requires
            # something here and the headline is already terse.
            object.__setattr__(self, "cta_description", self.headline[:25])
        return self


# ---------------------------------------------------------------------------
# Bid Schedule (C11)
# ---------------------------------------------------------------------------


class BidSchedule(BaseModel):
    """A time-windowed bid modifier (seasonality adjustment)."""

    campaign_name: str
    ad_group_name: str | None = None  # campaign-level if None
    start_date: date
    end_date: date
    modifier: float = Field(ge=0.1, le=10.0)
    reason: str = ""

    @model_validator(mode="after")
    def _dates_ordered(self) -> BidSchedule:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


# ---------------------------------------------------------------------------
# Top-level plan
# ---------------------------------------------------------------------------


class CampaignPlan(BaseModel):
    campaigns: list[Campaign] = Field(default_factory=list)
    sitelinks: list[Sitelink] = Field(default_factory=list)
    callouts: list[Callout] = Field(default_factory=list)
    snippets: list[StructuredSnippet] = Field(default_factory=list)
    call_extensions: list[CallExtension] = Field(default_factory=list)
    promotions: list[PromotionExtension] = Field(default_factory=list)
    lead_forms: list[LeadFormExtension] = Field(default_factory=list)
    bid_schedules: list[BidSchedule] = Field(default_factory=list)
