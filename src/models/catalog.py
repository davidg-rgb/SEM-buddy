"""Generic Product model + campaign-build configuration.

`Product` is the bridge between a catalog row and Google Ads entities. It's
deliberately generic — the field names cover destinations, hotels, SKUs, etc.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class Product(BaseModel):
    """One catalog row, normalized for the campaign builder."""

    sku: str  # IATA code for destinations; product ID for ecom; room ID for hotels
    name: str
    short_name: str | None = None  # Optional 18-char-max friendly fallback for long names
    aliases: list[str] = Field(default_factory=list)  # alternative names harvested from duplicate-key source rows; used to broaden keyword match
    attributes: dict[str, Any] = Field(default_factory=dict)
    keywords: list[str] = Field(default_factory=list)
    url: HttpUrl | None = None  # post-template-expansion landing URL

    def get(self, attr: str, default: Any = None) -> Any:
        """Lookup helper: tries top-level fields first, then attributes."""
        if attr == "sku":
            return self.sku
        if attr == "name":
            return self.name
        if attr == "aliases":
            return self.aliases
        if attr == "url":
            return str(self.url) if self.url else None
        return self.attributes.get(attr, default)


class CampaignBuildConfig(BaseModel):
    """Per-build settings controlling how a catalog turns into campaigns."""

    structure_mode: Literal["service", "geo", "sku", "auto"] = "auto"
    partition_by_attribute: str | None = None
    campaign_name_template: str = "{business_name} - Catalog"
    ad_group_name_template: str = "{name} ({sku})"
    language: str = "sv"
    url_templates: dict[str, str] = Field(default_factory=dict)
    text_n_range: tuple[int, int] = (1, 5)
    keyword_templates: list[str] = Field(default_factory=list)
    keyword_match_types: list[Literal["BROAD", "PHRASE", "EXACT"]] = Field(
        default_factory=lambda: ["PHRASE"]
    )
    pattern_pack: str | None = None  # data/{lang}/ subdir name
    interpolation_fields: list[str] = Field(default_factory=list)
    bid_rules: list[dict] = Field(default_factory=list)
    promotion_enabled: bool = False
    promotion_attribute: str | None = None
    lead_form: dict | None = None


__all__ = ["Product", "CampaignBuildConfig"]
