"""SEO analysis data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# --- Enums ---


class IssueSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueCategory(str, Enum):
    TECHNICAL = "technical"
    CONTENT = "content"
    ON_PAGE = "on_page"
    LINKS = "links"
    SCHEMA = "schema"


# --- Per-Page Scraping Models ---


class MetaTag(BaseModel):
    name: str
    content: str


class SchemaMarkup(BaseModel):
    schema_type: str
    format: Literal["json-ld", "microdata", "rdfa"]
    raw_data: dict = {}


class ImageAudit(BaseModel):
    src: str
    alt: str = ""
    has_alt: bool = False
    width: int | None = None
    height: int | None = None
    is_lazy_loaded: bool = False


class LinkInfo(BaseModel):
    url: str
    anchor_text: str = ""
    is_external: bool = False
    is_nofollow: bool = False
    status_code: int | None = None


class PageSeoData(BaseModel):
    """Full SEO data for a single page."""

    url: str
    status_code: int = 200
    redirect_chain: list[str] = []
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    meta_description_length: int = 0
    canonical_url: str | None = None
    is_self_canonical: bool = True
    hreflang_tags: list[dict[str, str]] = []
    robots_meta: str = ""
    h1: str = ""
    h1_count: int = 0
    headings: list[dict[str, str]] = []
    heading_hierarchy_valid: bool = True
    body_text: str = ""
    word_count: int = 0
    images: list[ImageAudit] = []
    images_without_alt: int = 0
    internal_links: list[LinkInfo] = []
    external_links: list[LinkInfo] = []
    schema_markup: list[SchemaMarkup] = []
    open_graph: list[MetaTag] = []
    twitter_card: list[MetaTag] = []
    meta_tags: list[MetaTag] = []
    render_blocking_resources: list[str] = []
    page_load_time_ms: float | None = None
    content_type: str = ""
    http_headers: dict[str, str] = {}


# --- Site-Level Models ---


class RobotsTxtData(BaseModel):
    exists: bool = False
    allows_crawling: bool = True
    sitemap_urls: list[str] = []
    disallowed_paths: list[str] = []
    raw_content: str = ""


class SitemapData(BaseModel):
    exists: bool = False
    url: str = ""
    page_count: int = 0
    urls: list[str] = []
    last_modified: str | None = None


class SiteSeoData(BaseModel):
    """Aggregate SEO data for a full site crawl."""

    domain: str
    crawl_date: datetime
    pages: list[PageSeoData] = []
    robots_txt: RobotsTxtData = Field(default_factory=RobotsTxtData)
    sitemaps: list[SitemapData] = []
    total_pages_crawled: int = 0
    total_internal_links: int = 0
    total_external_links: int = 0
    orphan_pages: list[str] = []


# --- Lighthouse / Performance ---


class CoreWebVitals(BaseModel):
    lcp_ms: float | None = None
    fid_ms: float | None = None
    cls: float | None = None
    fcp_ms: float | None = None
    ttfb_ms: float | None = None
    si_ms: float | None = None
    tbt_ms: float | None = None


class LighthouseResult(BaseModel):
    url: str = ""
    performance_score: float | None = None
    accessibility_score: float | None = None
    best_practices_score: float | None = None
    seo_score: float | None = None
    core_web_vitals: CoreWebVitals = Field(default_factory=CoreWebVitals)
    opportunities: list[dict] = []
    diagnostics: list[dict] = []


# --- Issues & Scoring ---


class SeoIssue(BaseModel):
    """A single actionable SEO issue."""

    category: IssueCategory
    severity: IssueSeverity
    title: str
    description: str
    affected_urls: list[str] = []
    fix_suggestion: str
    impact_estimate: str
    effort: Literal["low", "medium", "high"] = "low"


class CategoryScore(BaseModel):
    category: IssueCategory
    score: float
    max_score: float = 100.0
    issues_found: int = 0
    label: str = ""


class SeoScorecard(BaseModel):
    """Overall SEO scorecard for a page or site."""

    overall_score: float
    category_scores: list[CategoryScore] = []
    issues: list[SeoIssue] = []
    summary_sv: str = ""


# --- Competitor Comparison ---


class CompetitorSeoProfile(BaseModel):
    url: str
    domain: str
    scorecard: SeoScorecard = Field(
        default_factory=lambda: SeoScorecard(overall_score=0)
    )
    page_data: PageSeoData | None = None
    lighthouse: LighthouseResult | None = None


class SeoGap(BaseModel):
    """A specific area where competitor outperforms client."""

    area: str
    client_value: str
    competitor_value: str
    competitor_domain: str
    recommendation: str


class SeoCompetitorAnalysis(BaseModel):
    client_url: str
    client_scorecard: SeoScorecard
    competitors: list[CompetitorSeoProfile] = []
    gaps: list[SeoGap] = []
    advantages: list[str] = []


# --- Top-Level Result ---


class SeoAnalysisResult(BaseModel):
    """Complete SEO analysis output."""

    mode: Literal["single", "site"]
    analyzed_at: datetime
    site_data: SiteSeoData | None = None
    page_data: PageSeoData | None = None
    lighthouse: LighthouseResult | None = None
    scorecard: SeoScorecard
    competitor_analysis: SeoCompetitorAnalysis | None = None
