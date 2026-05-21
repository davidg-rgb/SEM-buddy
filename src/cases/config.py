"""`case.yaml` schema + loader.

A `CaseConfig` captures everything needed to take a single client from
catalog → Google Ads CSVs in one command. The case orchestrator (`runner.py`)
consumes it directly.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl

from src.models.catalog import CampaignBuildConfig


class StructureConfig(BaseModel):
    mode: Literal["service", "geo", "sku", "auto"] = "sku"
    partition_by_attribute: str | None = None
    campaign_name_template: str = "{business_name} - Catalog"
    ad_group_name_template: str = "{name} ({sku})"


class UrlTemplatesConfig(BaseModel):
    primary: str
    text_n_range: tuple[int, int] = (1, 5)


class AdCopyConfig(BaseModel):
    pattern_pack: str | None = None  # data/<pack>/
    interpolation_fields: list[str] = Field(default_factory=list)


class PromotionsConfig(BaseModel):
    enabled: bool = False
    use_attribute: str | None = "discount_pct"
    start_date: date | None = None
    end_date: date | None = None
    occasion: str | None = None
    money_currency: str = "SEK"


class LeadFormConfig(BaseModel):
    form_name: str
    headline: str
    description: str
    business_name: str = ""
    cta: str = "GET_QUOTE"
    privacy_url: HttpUrl
    fields: list[str]
    submit_headline: str = "Thanks!"
    submit_description: str = ""
    submit_url: HttpUrl | None = None
    asset_name: str = ""


class ExtensionsConfig(BaseModel):
    promotions: PromotionsConfig = Field(default_factory=PromotionsConfig)
    lead_form: LeadFormConfig | None = None


class AccountConfig(BaseModel):
    name: str | None = None
    admin_emails: list[str] = Field(default_factory=list)
    currency: str = "SEK"
    timezone: str = "Europe/Stockholm"


class CampaignGoalsConfig(BaseModel):
    """Bidding goal for the campaigns built from this case.

    Maps onto `ClientProfile.campaign_goals[0]` so the existing
    `_select_bid_strategy()` picks Target CPA / Target ROAS / Max Conv
    instead of the default Max Clicks.
    """

    goal_type: Literal[
        "conversions", "leads", "sales", "revenue", "roas",
        "traffic", "clicks", "awareness", "impressions",
    ] = "traffic"
    target_cpa_sek: float | None = None
    target_roas: float | None = None


class CaseConfig(BaseModel):
    """Top-level case.yaml schema."""

    schema_version: int = 1
    language: Literal["sv", "en"] = "en"
    catalog: str = "./catalog.yaml"  # relative path to catalog.yaml
    structure: StructureConfig = Field(default_factory=lambda: StructureConfig())
    url_templates: UrlTemplatesConfig | None = None
    keyword_templates: list[str] = Field(default_factory=list)
    keyword_match_types: list[Literal["BROAD", "PHRASE", "EXACT"]] = Field(
        default_factory=lambda: ["PHRASE"]
    )
    ad_copy: AdCopyConfig = Field(default_factory=AdCopyConfig)
    extensions: ExtensionsConfig = Field(default_factory=ExtensionsConfig)
    bid_rules: list[dict] = Field(default_factory=list)
    campaign_goals: CampaignGoalsConfig = Field(default_factory=CampaignGoalsConfig)
    account: AccountConfig = Field(default_factory=AccountConfig)
    monthly_budget_sek: int | None = None
    business_name: str | None = None  # override client's business_name if set
    website_url: HttpUrl | None = None
    industry: str | None = None

    def to_build_config(self) -> CampaignBuildConfig:
        """Project this case config onto the CampaignBuildConfig the builder uses."""
        return CampaignBuildConfig(
            structure_mode=self.structure.mode,
            partition_by_attribute=self.structure.partition_by_attribute,
            campaign_name_template=self.structure.campaign_name_template,
            ad_group_name_template=self.structure.ad_group_name_template,
            language=self.language,
            url_templates=(
                {"primary": self.url_templates.primary} if self.url_templates else {}
            ),
            text_n_range=self.url_templates.text_n_range if self.url_templates else (1, 5),
            keyword_templates=self.keyword_templates,
            keyword_match_types=list(self.keyword_match_types),
            pattern_pack=self.ad_copy.pattern_pack,
            interpolation_fields=self.ad_copy.interpolation_fields,
            bid_rules=self.bid_rules,
            promotion_enabled=self.extensions.promotions.enabled,
            promotion_attribute=self.extensions.promotions.use_attribute,
            lead_form=self.extensions.lead_form.model_dump() if self.extensions.lead_form else None,
        )


def load_case_config(yaml_path: str | Path) -> CaseConfig:
    """Read `case.yaml` and return a validated `CaseConfig`."""
    p = Path(yaml_path)
    if not p.exists():
        raise FileNotFoundError(f"case.yaml not found: {p}")
    with p.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"case.yaml must be a mapping, got {type(raw).__name__}")
    return CaseConfig.model_validate(raw)


__all__ = [
    "CaseConfig",
    "load_case_config",
    "StructureConfig",
    "UrlTemplatesConfig",
    "AdCopyConfig",
    "ExtensionsConfig",
    "PromotionsConfig",
    "LeadFormConfig",
    "AccountConfig",
]
