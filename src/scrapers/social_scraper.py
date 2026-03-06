"""Social media profile scraper using httpx (no login required)."""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from src.models.research import SocialProfile

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
}


async def scrape_social_profiles(
    business_name: str, domain: str
) -> list[SocialProfile]:
    """Find and scrape social media profiles for a business."""
    tasks = [
        find_linkedin(business_name),
        find_facebook(business_name),
        find_instagram(business_name),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    profiles: list[SocialProfile] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Social scraping error: %s", result)
            continue
        if result is not None:
            profiles.append(result)

    return profiles


async def find_linkedin(business_name: str) -> SocialProfile | None:
    """Find LinkedIn company page via Google search."""
    query = f"site:linkedin.com/company {business_name}"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        link = soup.find("a", href=re.compile(r"linkedin\.com/company/"))
        if not link:
            return None

        href = link.get("href", "")
        match = re.search(r"(https?://[a-z]+\.linkedin\.com/company/[^&\"' ]+)", href)
        profile_url = match.group(1) if match else href

        description = ""
        snippet = link.find_parent("div")
        if snippet:
            desc_el = snippet.find("span") or snippet.find("div")
            if desc_el:
                description = desc_el.get_text(strip=True)[:300]

        return SocialProfile(
            platform="linkedin",
            url=profile_url,
            name=business_name,
            description=description,
            follower_count=None,
        )

    except Exception as exc:
        logger.warning("LinkedIn search error for %s: %s", business_name, exc)
        return None


async def find_facebook(business_name: str) -> SocialProfile | None:
    """Find Facebook page via Google search."""
    query = f"site:facebook.com {business_name}"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        link = soup.find("a", href=re.compile(r"facebook\.com/"))
        if not link:
            return None

        href = link.get("href", "")
        match = re.search(r"(https?://[a-z]+\.facebook\.com/[^&\"' ]+)", href)
        profile_url = match.group(1) if match else href

        description = ""
        snippet = link.find_parent("div")
        if snippet:
            desc_el = snippet.find("span") or snippet.find("div")
            if desc_el:
                description = desc_el.get_text(strip=True)[:300]

        follower_count = None
        follower_match = re.search(r"([\d,.\s]+)\s*(?:följare|followers|gillar|likes)", description, re.I)
        if follower_match:
            count_str = re.sub(r"[^\d]", "", follower_match.group(1))
            if count_str:
                follower_count = int(count_str)

        return SocialProfile(
            platform="facebook",
            url=profile_url,
            name=business_name,
            description=description,
            follower_count=follower_count,
        )

    except Exception as exc:
        logger.warning("Facebook search error for %s: %s", business_name, exc)
        return None


async def find_instagram(business_name: str) -> SocialProfile | None:
    """Find Instagram profile via Google search."""
    query = f"site:instagram.com {business_name}"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        link = soup.find("a", href=re.compile(r"instagram\.com/"))
        if not link:
            return None

        href = link.get("href", "")
        match = re.search(r"(https?://[a-z]+\.instagram\.com/[^&\"' ]+)", href)
        profile_url = match.group(1) if match else href

        description = ""
        snippet = link.find_parent("div")
        if snippet:
            desc_el = snippet.find("span") or snippet.find("div")
            if desc_el:
                description = desc_el.get_text(strip=True)[:300]

        follower_count = None
        follower_match = re.search(r"([\d,.\s]+)\s*(?:följare|followers)", description, re.I)
        if follower_match:
            count_str = re.sub(r"[^\d]", "", follower_match.group(1))
            if count_str:
                follower_count = int(count_str)

        return SocialProfile(
            platform="instagram",
            url=profile_url,
            name=business_name,
            description=description,
            follower_count=follower_count,
        )

    except Exception as exc:
        logger.warning("Instagram search error for %s: %s", business_name, exc)
        return None
