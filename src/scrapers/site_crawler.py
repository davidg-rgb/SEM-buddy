"""Playwright-based full site crawler for extracting page content and structure."""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Page, Browser

from src.models.research import CrawledPage, SiteCrawl

logger = logging.getLogger(__name__)

PHONE_PATTERN_SE = re.compile(
    r"(?:\+46|0)\s*(?:\d[\s\-]*){7,10}"
)
CHAT_WIDGET_SELECTORS = [
    "[id*='chat']", "[class*='chat']", "[id*='livechat']",
    "[class*='livechat']", "[id*='intercom']", "[class*='zendesk']",
    "[id*='drift']", "[class*='hubspot-messages']", "[id*='tidio']",
]


async def _extract_page(page: Page, url: str) -> CrawledPage:
    """Extract structured content from a single page."""
    title = await page.title()
    meta_description = await page.evaluate(
        "document.querySelector('meta[name=\"description\"]')?.content || ''"
    )
    h1 = await page.evaluate(
        "document.querySelector('h1')?.innerText || ''"
    )
    headings = await page.evaluate("""
        () => Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
            .map(h => ({tag: h.tagName.toLowerCase(), text: h.innerText.trim()}))
    """)
    body_text = await page.evaluate(
        "document.body?.innerText || ''"
    )
    internal_links = await page.evaluate("""
        () => {
            const base = window.location.origin;
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(href => href.startsWith(base));
        }
    """)

    has_form = await page.evaluate("document.querySelectorAll('form').length > 0")
    phones = PHONE_PATTERN_SE.findall(body_text)
    has_chat = False
    for selector in CHAT_WIDGET_SELECTORS:
        try:
            if await page.query_selector(selector):
                has_chat = True
                break
        except Exception:
            pass

    return CrawledPage(
        url=url,
        title=title,
        meta_description=meta_description,
        h1=h1,
        headings=headings,
        body_text=body_text[:50000],
        internal_links=list(set(internal_links)),
        has_form=has_form,
        phones=phones,
        has_chat_widget=has_chat,
    )


async def crawl_site(url: str, max_pages: int = 50) -> SiteCrawl:
    """Crawl a website up to max_pages, extracting content from each page."""
    parsed = urlparse(url)
    base_domain = parsed.netloc
    visited: set[str] = set()
    to_visit: list[str] = [url]
    pages: list[CrawledPage] = []

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; SEMMasterBot/1.0)",
            locale="sv-SE",
        )
        page = await context.new_page()

        while to_visit and len(pages) < max_pages:
            current_url = to_visit.pop(0)
            normalized = current_url.rstrip("/")
            if normalized in visited:
                continue
            visited.add(normalized)

            try:
                logger.info("Crawling: %s", current_url)
                response = await page.goto(current_url, wait_until="domcontentloaded", timeout=15000)
                if not response or response.status >= 400:
                    logger.warning("Skipping %s (status %s)", current_url, response.status if response else "None")
                    continue

                crawled = await _extract_page(page, current_url)
                pages.append(crawled)

                for link in crawled.internal_links:
                    link_parsed = urlparse(link)
                    if link_parsed.netloc == base_domain and link.rstrip("/") not in visited:
                        to_visit.append(link)

            except Exception as exc:
                logger.warning("Error crawling %s: %s", current_url, exc)

            await asyncio.sleep(1.5)

        await browser.close()

    return SiteCrawl(
        domain=base_domain,
        start_url=url,
        pages=pages,
        total_pages_crawled=len(pages),
    )
