"""Research and digital presence models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CrawledPage(BaseModel):
    url: str
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    headings: list[str] = []
    body_text: str = ""


class SiteCrawl(BaseModel):
    pages: list[CrawledPage] = []
    total_pages: int = 0
    primary_language: str = "sv"


class Review(BaseModel):
    source: str
    rating: float
    text: str = ""
    review_date: date | None = None


class SocialProfile(BaseModel):
    platform: str
    url: str
    followers: int | None = None
    description: str = ""


class GoogleBusinessProfile(BaseModel):
    name: str
    address: str = ""
    phone: str = ""
    rating: float = 0.0
    review_count: int = 0
    categories: list[str] = []
    opening_hours: dict | None = None


class DigitalPresence(BaseModel):
    site_crawl: SiteCrawl | None = None
    google_business: GoogleBusinessProfile | None = None
    reviews: list[Review] = []
    social_profiles: list[SocialProfile] = []
    seo_data: dict | None = None  # SeoAnalysisResult dict when available
