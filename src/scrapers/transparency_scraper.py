"""Google Ads Transparency Center scraper using Playwright."""

from __future__ import annotations

import asyncio
import logging

from playwright.async_api import async_playwright, Page

from src.models.competitor import TransparencyAd

logger = logging.getLogger(__name__)

TRANSPARENCY_URL = "https://adstransparency.google.com"


async def scrape_transparency(
    advertiser_name: str, domain: str = ""
) -> list[TransparencyAd]:
    """Scrape ads from Google Ads Transparency Center for an advertiser.

    Navigates to adstransparency.google.com, searches by advertiser name,
    and extracts ad creatives with metadata.
    """
    ads: list[TransparencyAd] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="sv-SE",
        )
        page = await context.new_page()

        try:
            await page.goto(TRANSPARENCY_URL, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)

            search_input = await page.query_selector("input[type='text'], input[type='search'], [role='searchbox']")
            if not search_input:
                logger.warning("Could not find search input on Transparency Center")
                await browser.close()
                return ads

            search_query = advertiser_name if not domain else f"{advertiser_name} {domain}"
            await search_input.fill(search_query)
            await page.keyboard.press("Enter")
            await asyncio.sleep(3)

            advertiser_link = await page.query_selector("a[href*='advertiser'], .advertiser-result, [data-advertiser]")
            if advertiser_link:
                await advertiser_link.click()
                await asyncio.sleep(3)

            ads = await _extract_ads(page)

            has_more = True
            page_count = 0
            while has_more and page_count < 5:
                next_btn = await page.query_selector(
                    "button[aria-label*='Next'], button[aria-label*='next'], .pagination-next"
                )
                if next_btn and await next_btn.is_enabled():
                    await next_btn.click()
                    await asyncio.sleep(2.5)
                    more_ads = await _extract_ads(page)
                    if not more_ads:
                        has_more = False
                    else:
                        ads.extend(more_ads)
                    page_count += 1
                else:
                    has_more = False

        except Exception as exc:
            logger.error("Error scraping Transparency Center for %s: %s", advertiser_name, exc)
        finally:
            await browser.close()

    logger.info("Found %d ads for %s", len(ads), advertiser_name)
    return ads


async def _extract_ads(page: Page) -> list[TransparencyAd]:
    """Extract ad data from the current page state."""
    ads: list[TransparencyAd] = []

    ad_cards = await page.query_selector_all(
        ".creative-card, [data-creative], .ad-card, [role='listitem']"
    )

    for card in ad_cards:
        try:
            text_el = await card.query_selector(
                ".ad-text, .creative-text, p, span"
            )
            ad_text = ""
            if text_el:
                ad_text = (await text_el.inner_text()).strip()

            ad_format = "text"
            img_el = await card.query_selector("img, video")
            if img_el:
                tag = await img_el.evaluate("el => el.tagName.toLowerCase()")
                ad_format = "image" if tag == "img" else "video"

            date_el = await card.query_selector(
                ".date-range, [data-date], time, .ad-date"
            )
            date_range = ""
            if date_el:
                date_range = (await date_el.inner_text()).strip()

            geo_el = await card.query_selector(
                ".geo-targeting, [data-region], .ad-region"
            )
            geo_targeting = ""
            if geo_el:
                geo_targeting = (await geo_el.inner_text()).strip()

            if ad_text or ad_format != "text":
                ads.append(TransparencyAd(
                    advertiser_name="",
                    ad_text=ad_text,
                    ad_format=ad_format,
                    date_range=date_range,
                    geo_targeting=geo_targeting,
                ))

        except Exception as exc:
            logger.debug("Error extracting ad card: %s", exc)
            continue

    return ads
