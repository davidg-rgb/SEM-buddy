"""Multi-source review scraper: Trustpilot, Reco.se, Google Reviews."""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from src.models.research import Review

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
}


async def scrape_reviews(business_name: str, domain: str = "") -> list[Review]:
    """Scrape reviews from multiple sources and combine them."""
    tasks = [
        scrape_google_reviews(business_name),
    ]
    if domain:
        tasks.append(scrape_trustpilot(domain))
    tasks.append(scrape_reco(business_name))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_reviews: list[Review] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Review scraping error: %s", result)
            continue
        all_reviews.extend(result)

    return _deduplicate(all_reviews)


async def scrape_trustpilot(domain: str) -> list[Review]:
    """Scrape reviews from Trustpilot for a given domain."""
    url = f"https://www.trustpilot.com/review/{domain}"
    reviews: list[Review] = []

    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            if response.status_code == 404:
                logger.info("No Trustpilot page for %s", domain)
                return []
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        review_cards = soup.find_all("article", attrs={"data-service-review-card-paper": True})
        if not review_cards:
            review_cards = soup.find_all("div", class_=re.compile(r"review", re.I))

        for card in review_cards[:20]:
            text_el = card.find(attrs={"data-service-review-text-typography": True})
            text = text_el.get_text(strip=True) if text_el else ""
            if not text:
                p = card.find("p")
                text = p.get_text(strip=True) if p else ""

            rating_el = card.find("img", alt=re.compile(r"Rated \d"))
            rating = None
            if rating_el:
                match = re.search(r"Rated (\d)", rating_el.get("alt", ""))
                if match:
                    rating = float(match.group(1))

            author_el = card.find(attrs={"data-consumer-name-typography": True})
            author = author_el.get_text(strip=True) if author_el else ""

            if text:
                reviews.append(Review(
                    source="trustpilot",
                    text=text,
                    rating=rating,
                    author=author,
                ))

    except httpx.HTTPError as exc:
        logger.warning("Trustpilot HTTP error for %s: %s", domain, exc)
    except Exception as exc:
        logger.warning("Trustpilot error for %s: %s", domain, exc)

    return reviews


async def scrape_reco(business_name: str) -> list[Review]:
    """Scrape reviews from Reco.se (Swedish review platform)."""
    search_url = f"https://www.reco.se/search?q={business_name.replace(' ', '+')}"
    reviews: list[Review] = []

    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            search_response = await client.get(search_url)
            if search_response.status_code >= 400:
                return []

            soup = BeautifulSoup(search_response.text, "html.parser")
            first_link = soup.find("a", href=re.compile(r"/[a-z0-9\-]+$"))
            if not first_link:
                logger.info("No Reco.se page found for %s", business_name)
                return []

            profile_url = f"https://www.reco.se{first_link['href']}"
            profile_response = await client.get(profile_url)
            profile_response.raise_for_status()

        profile_soup = BeautifulSoup(profile_response.text, "html.parser")
        review_els = profile_soup.find_all("div", class_=re.compile(r"review", re.I))

        for el in review_els[:20]:
            text_el = el.find("p")
            text = text_el.get_text(strip=True) if text_el else ""
            rating = None
            rating_el = el.find(attrs={"class": re.compile(r"star|rating", re.I)})
            if rating_el:
                match = re.search(r"(\d(?:\.\d)?)", rating_el.get_text())
                if match:
                    rating = float(match.group(1))

            if text:
                reviews.append(Review(
                    source="reco",
                    text=text,
                    rating=rating,
                    author="",
                ))

    except httpx.HTTPError as exc:
        logger.warning("Reco.se HTTP error for %s: %s", business_name, exc)
    except Exception as exc:
        logger.warning("Reco.se error for %s: %s", business_name, exc)

    return reviews


async def scrape_google_reviews(business_name: str) -> list[Review]:
    """Scrape Google review snippets from search results."""
    query = f"{business_name} recensioner"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=sv"
    reviews: list[Review] = []

    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        review_blocks = soup.find_all("div", attrs={"data-attrid": re.compile(r"review", re.I)})
        for block in review_blocks[:10]:
            text = block.get_text(strip=True)
            if text and len(text) > 20:
                reviews.append(Review(
                    source="google",
                    text=text[:500],
                    rating=None,
                    author="",
                ))

        snippet_blocks = soup.find_all("span", class_=re.compile(r"review", re.I))
        for span in snippet_blocks[:10]:
            text = span.get_text(strip=True)
            if text and len(text) > 20:
                reviews.append(Review(
                    source="google",
                    text=text[:500],
                    rating=None,
                    author="",
                ))

    except httpx.HTTPError as exc:
        logger.warning("Google reviews HTTP error for %s: %s", business_name, exc)
    except Exception as exc:
        logger.warning("Google reviews error for %s: %s", business_name, exc)

    return reviews


def _deduplicate(reviews: list[Review]) -> list[Review]:
    """Remove duplicate reviews based on text similarity."""
    seen_texts: set[str] = set()
    unique: list[Review] = []
    for review in reviews:
        normalized = review.text.lower().strip()[:100]
        if normalized not in seen_texts:
            seen_texts.add(normalized)
            unique.append(review)
    return unique
