"""Campaign template model for SEM Master.

Stores reusable campaign structures with client-specific data stripped out.
See ARCHITECTURE.md section 7.2 for the full specification.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CampaignTemplate(BaseModel):
    """A saved campaign structure with client-specific data stripped out."""

    name: str
    description: str = ""
    source_client: str
    source_industry: str = ""
    created_at: datetime
    campaign_structures: list[dict]
    ad_group_patterns: list[dict] = []
    extension_patterns: dict = {}
    budget_strategy: dict = {}
