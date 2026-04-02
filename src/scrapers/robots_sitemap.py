"""Fetch and parse robots.txt and sitemap.xml files."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from lxml import etree

from src.models.seo import RobotsTxtData, SitemapData

logger = logging.getLogger(__name__)

_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
_MAX_CHILD_SITEMAPS = 5


async def fetch_robots_txt(domain: str) -> RobotsTxtData:
    """Fetch and parse a domain's robots.txt file."""
    url = f"https://{domain}/robots.txt"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
    except Exception as exc:
        logger.warning("Could not fetch robots.txt for %s: %s", domain, exc)
        return RobotsTxtData(exists=False)

    if resp.status_code == 404:
        return RobotsTxtData(exists=False, allows_crawling=True)
    if resp.status_code >= 400:
        return RobotsTxtData(exists=False)

    raw = resp.text
    sitemap_urls: list[str] = []
    disallowed: list[str] = []
    allows_crawling = True
    in_wildcard_agent = False

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        lower = line.lower()
        if lower.startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            in_wildcard_agent = agent == "*"
        elif lower.startswith("sitemap:"):
            sitemap_urls.append(line.split(":", 1)[1].strip())
        elif in_wildcard_agent and lower.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path:
                disallowed.append(path)
                if path == "/":
                    allows_crawling = False

    return RobotsTxtData(
        exists=True,
        allows_crawling=allows_crawling,
        sitemap_urls=sitemap_urls,
        disallowed_paths=disallowed,
        raw_content=raw[:5000],
    )


async def fetch_sitemap(url: str) -> SitemapData:
    """Fetch and parse a sitemap XML file."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
    except Exception as exc:
        logger.warning("Could not fetch sitemap %s: %s", url, exc)
        return SitemapData(exists=False, url=url)

    if resp.status_code == 404:
        return SitemapData(exists=False, url=url)
    if resp.status_code >= 400:
        return SitemapData(exists=False, url=url)

    try:
        root = etree.fromstring(resp.content)
    except Exception as exc:
        logger.warning("Invalid XML in sitemap %s: %s", url, exc)
        return SitemapData(exists=False, url=url)

    # Check if sitemap index
    if root.tag == f"{{{_SITEMAP_NS}}}sitemapindex" or "sitemapindex" in root.tag:
        child_urls = []
        for sm in root.findall(f"{{{_SITEMAP_NS}}}sitemap"):
            loc = sm.find(f"{{{_SITEMAP_NS}}}loc")
            if loc is not None and loc.text:
                child_urls.append(loc.text.strip())

        # Fetch child sitemaps (limited)
        all_page_urls: list[str] = []
        for child_url in child_urls[:_MAX_CHILD_SITEMAPS]:
            child_data = await fetch_sitemap(child_url)
            all_page_urls.extend(child_data.urls)

        return SitemapData(
            exists=True,
            url=url,
            page_count=len(all_page_urls),
            urls=all_page_urls,
        )

    # Regular sitemap
    page_urls: list[str] = []
    last_mod = None
    for url_elem in root.findall(f"{{{_SITEMAP_NS}}}url"):
        loc = url_elem.find(f"{{{_SITEMAP_NS}}}loc")
        if loc is not None and loc.text:
            page_urls.append(loc.text.strip())
        lastmod = url_elem.find(f"{{{_SITEMAP_NS}}}lastmod")
        if lastmod is not None and lastmod.text and not last_mod:
            last_mod = lastmod.text.strip()

    return SitemapData(
        exists=True,
        url=url,
        page_count=len(page_urls),
        urls=page_urls,
        last_modified=last_mod,
    )


async def discover_sitemaps(domain: str, robots_data: RobotsTxtData) -> list[SitemapData]:
    """Discover all sitemaps: robots.txt first, then common paths."""
    seen_urls: set[str] = set()
    results: list[SitemapData] = []

    # From robots.txt
    for sm_url in robots_data.sitemap_urls:
        if sm_url not in seen_urls:
            seen_urls.add(sm_url)
            data = await fetch_sitemap(sm_url)
            results.append(data)

    # Try common paths if nothing from robots.txt
    if not results or not any(r.exists for r in results):
        common_paths = [
            f"https://{domain}/sitemap.xml",
            f"https://{domain}/sitemap_index.xml",
        ]
        for path in common_paths:
            if path not in seen_urls:
                seen_urls.add(path)
                data = await fetch_sitemap(path)
                if data.exists:
                    results.append(data)
                    break

    return results
