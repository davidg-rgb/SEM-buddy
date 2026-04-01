"""Managed account model for SEM Master multi-client management."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class ManagedAccount(BaseModel):
    """Represents a client Google Ads account managed under the MCC umbrella."""

    name: str  # kebab-case, unique, used as directory name
    customer_id: str  # format XXX-XXX-XXXX
    display_name: str  # human-readable business name
    industry: Optional[str] = None  # key from industry_keywords.json
    monthly_budget_sek: Optional[int] = None  # positive integer
    brand_voice: Optional[str] = None
    website_url: Optional[str] = None
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = None  # type: ignore[assignment]
    updated_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: object) -> None:
        now = datetime.now()
        if self.created_at is None:
            object.__setattr__(self, "created_at", now)
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", now)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                f"Account name '{v}' must be kebab-case (lowercase letters, digits, hyphens only)"
            )
        return v

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v: str) -> str:
        if not re.match(r"^\d{3}-\d{3}-\d{4}$", v):
            raise ValueError(
                f"Customer ID '{v}' must be in XXX-XXX-XXXX format (e.g., 123-456-7890)"
            )
        return v

    @field_validator("monthly_budget_sek")
    @classmethod
    def validate_budget(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("monthly_budget_sek must be a positive integer")
        return v
