"""Google Business Profile scraper using httpx."""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

from src.models.research import GoogleBusinessProfile

logger = logging.getLogger(__name__)

GOOGLE_MAPS_SEARCH_URL = "https://www.google.com/maps/search/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
}


async def scrape_gbp(
    business_name: str, location: str = ""
) -> GoogleBusinessProfile | None:
    """Scrape Google Business Profile data for a business.

    Searches Google Maps for the business and extracts available profile info.
    Returns None if no profile is found.
    """
    query = f"{business_name} {location}".strip()
    search_url = f"{GOOGLE_MAPS_SEARCH_URL}{query.replace(' ', '+')}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
            response = await client.get(search_url)
            response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup, business_name)
        if not name:
            logger.info("No GBP found for: %s", query)
            return None

        return GoogleBusinessProfile(
            name=name,
            address=_extract_meta(soup, "address"),
            phone=_extract_phone(html),
            rating=_extract_rating(html),
            review_count=_extract_review_count(html),
            categories=_extract_categories(soup),
            opening_hours=_extract_hours(soup),
        )

    except httpx.HTTPError as exc:
        logger.error("HTTP error scraping GBP for %s: %s", query, exc)
        return None
    except Exception as exc:
        logger.error("Error scraping GBP for %s: %s", query, exc)
        return None


def _extract_name(soup: BeautifulSoup, fallback: str) -> str | None:
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text()
        if "Google Maps" in title and "-" in title:
            return title.split("-")[0].strip()
    return fallback


def _extract_meta(soup: BeautifulSoup, field: str) -> str:
    meta = soup.find("meta", attrs={"name": field})
    if meta and meta.get("content"):
        return meta["content"]
    return ""


def _extract_phone(html: str) -> str:
    pattern = re.compile(r"(?:\+46|0)\s*(?:\d[\s\-]*){7,10}")
    match = pattern.search(html)
    return match.group(0).strip() if match else ""


def _extract_rating(html: str) -> float | None:
    match = re.search(r'"ratingValue":\s*"?([\d.]+)"?', html)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def _extract_review_count(html: str) -> int | None:
    match = re.search(r'"reviewCount":\s*"?(\d+)"?', html)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def _extract_categories(soup: BeautifulSoup) -> list[str]:
    categories = []
    for el in soup.find_all(attrs={"data-category": True}):
        categories.append(el["data-category"])
    return categories


def _extract_hours(soup: BeautifulSoup) -> dict[str, str]:
    hours: dict[str, str] = {}
    table = soup.find("table", class_=re.compile(r"hour", re.I))
    if table:
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                day = cells[0].get_text(strip=True)
                time_range = cells[1].get_text(strip=True)
                hours[day] = time_range
    return hours
