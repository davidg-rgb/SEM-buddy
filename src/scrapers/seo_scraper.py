"""Playwright-based SEO data extraction for on-page and technical analysis."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, Browser, Response

from src.models.seo import (
    ImageAudit,
    LinkInfo,
    MetaTag,
    PageSeoData,
    SchemaMarkup,
    SiteSeoData,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core extraction — runs inside an already-navigated Playwright page
# ---------------------------------------------------------------------------


async def extract_page_seo(page: Page, url: str) -> PageSeoData:
    """Extract all SEO-relevant data from a rendered Playwright page."""

    title = await page.title()

    # Meta description
    meta_description = await page.evaluate(
        "document.querySelector('meta[name=\"description\"]')?.content || ''"
    )

    # Canonical
    canonical_url = await page.evaluate(
        "document.querySelector('link[rel=\"canonical\"]')?.href || null"
    )

    # Hreflang
    hreflang_tags = await page.evaluate("""
        () => Array.from(document.querySelectorAll('link[rel="alternate"][hreflang]'))
            .map(l => ({ lang: l.getAttribute('hreflang'), url: l.href }))
    """)

    # Robots meta
    robots_meta = await page.evaluate(
        "document.querySelector('meta[name=\"robots\"]')?.content || ''"
    )

    # Headings
    headings = await page.evaluate("""
        () => Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
            .map(h => ({ tag: h.tagName.toLowerCase(), text: h.innerText?.trim() || '' }))
    """)

    h1_list = [h for h in headings if h.get("tag") == "h1"]
    h1_text = h1_list[0].get("text", "") if h1_list else ""
    h1_count = len(h1_list)

    # Body text
    body_text = await page.evaluate("document.body?.innerText || ''")
    body_text = body_text[:50000]
    word_count = len(body_text.split()) if body_text.strip() else 0

    # Images
    raw_images = await page.evaluate("""
        () => Array.from(document.querySelectorAll('img')).map(img => ({
            src: img.src || '',
            alt: img.alt || '',
            has_alt: img.hasAttribute('alt') && img.alt.trim() !== '',
            width: img.naturalWidth || img.width || null,
            height: img.naturalHeight || img.height || null,
            is_lazy_loaded: img.loading === 'lazy' || img.hasAttribute('data-src')
        }))
    """)
    images = [ImageAudit(**img) for img in raw_images]
    images_without_alt = sum(1 for img in images if not img.has_alt)

    # Links
    raw_links = await page.evaluate("""
        () => {
            const origin = window.location.origin;
            return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                url: a.href,
                anchor_text: a.innerText?.trim() || '',
                is_external: !a.href.startsWith(origin) && a.href.startsWith('http'),
                is_nofollow: (a.rel || '').includes('nofollow')
            }));
        }
    """)
    internal_links = [LinkInfo(**lnk) for lnk in raw_links if not lnk.get("is_external")]
    external_links = [LinkInfo(**lnk) for lnk in raw_links if lnk.get("is_external")]

    # Schema markup (JSON-LD)
    raw_schemas = await page.evaluate("""
        () => {
            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
            return Array.from(scripts).map(s => {
                try { return JSON.parse(s.textContent); }
                catch { return null; }
            }).filter(Boolean);
        }
    """)
    schema_markup = []
    for schema in raw_schemas:
        schema_type = schema.get("@type", "Unknown") if isinstance(schema, dict) else "Unknown"
        schema_markup.append(SchemaMarkup(
            schema_type=schema_type,
            format="json-ld",
            raw_data=schema if isinstance(schema, dict) else {},
        ))

    # Open Graph + Twitter Card
    og_tw = await page.evaluate("""
        () => {
            const og = Array.from(document.querySelectorAll('meta[property^="og:"]'))
                .map(m => ({ name: m.getAttribute('property'), content: m.content || '' }));
            const tw = Array.from(document.querySelectorAll('meta[name^="twitter:"]'))
                .map(m => ({ name: m.name, content: m.content || '' }));
            return { og, tw };
        }
    """)
    open_graph = [MetaTag(**m) for m in og_tw.get("og", [])]
    twitter_card = [MetaTag(**m) for m in og_tw.get("tw", [])]

    # All other meta tags
    raw_meta = await page.evaluate("""
        () => Array.from(document.querySelectorAll('meta')).map(m => ({
            name: m.getAttribute('name') || m.getAttribute('property')
                  || m.getAttribute('http-equiv') || '',
            content: m.getAttribute('content') || ''
        })).filter(m => m.name)
    """)
    meta_tags = [MetaTag(**m) for m in raw_meta]

    # Render-blocking resources
    render_blocking = await page.evaluate("""
        () => {
            const blocking = [];
            document.querySelectorAll(
                'link[rel="stylesheet"]:not([media="print"]):not([media="none"])'
            ).forEach(l => { if (l.href) blocking.push(l.href); });
            document.querySelectorAll(
                'script:not([defer]):not([async]):not([type="module"])'
                + ':not([type="application/ld+json"])'
            ).forEach(s => { if (s.src) blocking.push(s.src); });
            return blocking;
        }
    """)

    # Heading hierarchy validation
    heading_hierarchy_valid = _validate_heading_hierarchy(headings)

    # Canonical self-reference check
    is_self_canonical = True
    if canonical_url:
        is_self_canonical = canonical_url.rstrip("/") == url.rstrip("/")

    return PageSeoData(
        url=url,
        title=title,
        title_length=len(title),
        meta_description=meta_description,
        meta_description_length=len(meta_description),
        canonical_url=canonical_url,
        is_self_canonical=is_self_canonical,
        hreflang_tags=hreflang_tags,
        robots_meta=robots_meta,
        h1=h1_text,
        h1_count=h1_count,
        headings=headings,
        heading_hierarchy_valid=heading_hierarchy_valid,
        body_text=body_text,
        word_count=word_count,
        images=images,
        images_without_alt=images_without_alt,
        internal_links=internal_links,
        external_links=external_links,
        schema_markup=schema_markup,
        open_graph=open_graph,
        twitter_card=twitter_card,
        meta_tags=meta_tags,
        render_blocking_resources=render_blocking,
    )


def _validate_heading_hierarchy(headings: list[dict]) -> bool:
    """Check heading hierarchy: must have exactly 1 H1, no skipped levels."""
    if not headings:
        return False
    tags = [h.get("tag", "") for h in headings]
    if tags.count("h1") != 1:
        return False
    # Check for skipped levels (e.g., h1 -> h3 without h2)
    level_map = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
    prev_level = 0
    for tag in tags:
        level = level_map.get(tag, 0)
        if level == 0:
            continue
        if level > prev_level + 1 and prev_level > 0:
            return False
        prev_level = level
    return True


# ---------------------------------------------------------------------------
# HTTP details extraction
# ---------------------------------------------------------------------------


def _extract_http_details(response: Response | None, url: str) -> dict:
    """Extract HTTP-level details from a Playwright Response."""
    if not response:
        return {
            "status_code": 0,
            "redirect_chain": [],
            "content_type": "",
            "http_headers": {},
        }

    headers = {}
    try:
        all_headers = response.headers
        for key in ("cache-control", "x-robots-tag", "content-type", "server"):
            if key in all_headers:
                headers[key] = all_headers[key]
    except Exception:
        pass

    redirect_chain = []
    req = response.request
    while req.redirected_from:
        redirect_chain.insert(0, req.redirected_from.url)
        req = req.redirected_from

    return {
        "status_code": response.status,
        "redirect_chain": redirect_chain,
        "content_type": headers.get("content-type", ""),
        "http_headers": headers,
    }


# ---------------------------------------------------------------------------
# Single-page analysis entry point
# ---------------------------------------------------------------------------


async def crawl_seo_single(url: str) -> PageSeoData:
    """Launch browser, scrape one page for SEO data, close browser."""
    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; SEMMasterBot/1.0)",
            locale="sv-SE",
        )
        page = await context.new_page()

        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        except Exception as exc:
            await browser.close()
            raise ConnectionError(f"Could not load {url}: {exc}") from exc

        http = _extract_http_details(response, url)
        seo_data = await extract_page_seo(page, url)

        # Merge HTTP details
        seo_data.status_code = http["status_code"]
        seo_data.redirect_chain = http["redirect_chain"]
        seo_data.content_type = http["content_type"]
        seo_data.http_headers = http["http_headers"]

        await browser.close()

    return seo_data


# ---------------------------------------------------------------------------
# Site crawl
# ---------------------------------------------------------------------------


async def crawl_seo_site(url: str, max_pages: int = 30) -> SiteSeoData:
    """Crawl a website BFS, collecting SEO data from each page."""
    parsed = urlparse(url)
    base_domain = parsed.netloc
    visited: set[str] = set()
    to_visit: list[str] = [url]
    pages: list[PageSeoData] = []

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
                logger.info("SEO crawling: %s", current_url)
                response = await page.goto(
                    current_url, wait_until="domcontentloaded", timeout=15000
                )
                if not response or response.status >= 400:
                    logger.warning(
                        "Skipping %s (status %s)",
                        current_url,
                        response.status if response else "None",
                    )
                    # First page failure raises ConnectionError
                    if not pages:
                        await browser.close()
                        raise ConnectionError(
                            f"Could not load starting page {current_url} "
                            f"(status {response.status if response else 'None'})"
                        )
                    continue

                http = _extract_http_details(response, current_url)
                seo_data = await extract_page_seo(page, current_url)
                seo_data.status_code = http["status_code"]
                seo_data.redirect_chain = http["redirect_chain"]
                seo_data.content_type = http["content_type"]
                seo_data.http_headers = http["http_headers"]
                pages.append(seo_data)

                # Queue internal links
                for link in seo_data.internal_links:
                    link_parsed = urlparse(link.url)
                    if link_parsed.netloc == base_domain and link.url.rstrip("/") not in visited:
                        to_visit.append(link.url)

            except ConnectionError:
                raise  # Re-raise first-page errors
            except Exception as exc:
                logger.warning("Error SEO-crawling %s: %s", current_url, exc)
                # First page failure raises ConnectionError
                if not pages:
                    await browser.close()
                    raise ConnectionError(f"Could not load {current_url}: {exc}") from exc

            await asyncio.sleep(1.5)

        await browser.close()

    # Compute orphan pages
    all_linked: set[str] = set()
    for p in pages:
        for link in p.internal_links:
            all_linked.add(link.url.rstrip("/"))
    orphan_pages = [
        p.url for p in pages
        if p.url.rstrip("/") not in all_linked and p.url != url
    ]

    total_internal = sum(len(p.internal_links) for p in pages)
    total_external = sum(len(p.external_links) for p in pages)

    return SiteSeoData(
        domain=base_domain,
        crawl_date=datetime.now(),
        pages=pages,
        total_pages_crawled=len(pages),
        total_internal_links=total_internal,
        total_external_links=total_external,
        orphan_pages=orphan_pages,
    )


# ---------------------------------------------------------------------------
# Synthetic data generators for --dry-run mode
# ---------------------------------------------------------------------------


def generate_synthetic_page_data(url: str) -> PageSeoData:
    """Generate realistic synthetic SEO data for dry-run mode."""
    return PageSeoData(
        url=url,
        status_code=200,
        title="Tandvård Stockholm — Kvalificerad Tandläkare",
        title_length=47,
        meta_description="Vi erbjuder professionell tandvård i Stockholm.",
        meta_description_length=49,
        canonical_url=url,
        is_self_canonical=True,
        hreflang_tags=[],
        robots_meta="",
        h1="Välkommen till vår tandläkarmottagning",
        h1_count=1,
        headings=[
            {"tag": "h1", "text": "Välkommen till vår tandläkarmottagning"},
            {"tag": "h2", "text": "Våra tjänster"},
            {"tag": "h3", "text": "Tandblekning"},
            {"tag": "h3", "text": "Tandimplantat"},
            {"tag": "h2", "text": "Kontakta oss"},
        ],
        heading_hierarchy_valid=True,
        body_text=(
            "Välkommen till vår tandläkarmottagning i Stockholm. Vi har över 20 års "
            "erfarenhet av kvalificerad tandvård. Vårt team av specialister erbjuder "
            "allt från allmän tandvård till avancerade behandlingar som implantat och "
            "tandblekning. Boka tid idag för en kostnadsfri konsultation. "
            "Vi finns centralt i Stockholm med goda kommunikationer. "
            "Ring oss på 08-123 456 78 eller fyll i kontaktformuläret. "
        ) * 3,
        word_count=180,
        images=[
            ImageAudit(src=f"{url}/hero.jpg", alt="Tandläkarmottagning Stockholm", has_alt=True,
                       width=1200, height=600),
            ImageAudit(src=f"{url}/team.jpg", alt="", has_alt=False, width=800, height=400),
            ImageAudit(src=f"{url}/clinic.jpg", alt="Vår klinik", has_alt=True,
                       width=600, height=400),
        ],
        images_without_alt=1,
        internal_links=[
            LinkInfo(url=f"{url}/tjanster", anchor_text="Våra tjänster"),
            LinkInfo(url=f"{url}/om-oss", anchor_text="Om oss"),
            LinkInfo(url=f"{url}/kontakt", anchor_text="Kontakta oss"),
            LinkInfo(url=f"{url}/priser", anchor_text="Priser"),
        ],
        external_links=[
            LinkInfo(url="https://www.1177.se/tandvard", anchor_text="1177 Tandvård",
                     is_external=True),
        ],
        schema_markup=[],
        open_graph=[
            MetaTag(name="og:title", content="Tandvård Stockholm"),
            MetaTag(name="og:description", content="Professionell tandvård i Stockholm"),
        ],
        twitter_card=[],
        meta_tags=[
            MetaTag(name="viewport", content="width=device-width, initial-scale=1"),
        ],
        render_blocking_resources=[
            f"{url}/styles.css",
            f"{url}/vendor.js",
        ],
    )


def generate_synthetic_site_data(url: str) -> SiteSeoData:
    """Generate synthetic site-level SEO data for dry-run mode."""
    parsed = urlparse(url)
    domain = parsed.netloc or "example.se"

    homepage = generate_synthetic_page_data(url)

    services_page = PageSeoData(
        url=f"{url}/tjanster",
        status_code=200,
        title="Våra Tjänster — Tandvård Stockholm",
        title_length=38,
        meta_description="",
        meta_description_length=0,
        h1="Våra tjänster",
        h1_count=1,
        headings=[
            {"tag": "h1", "text": "Våra tjänster"},
            {"tag": "h2", "text": "Allmän tandvård"},
            {"tag": "h2", "text": "Estetisk tandvård"},
        ],
        heading_hierarchy_valid=True,
        body_text="Vi erbjuder ett brett utbud av tandvårdstjänster. " * 10,
        word_count=90,
        images=[
            ImageAudit(src=f"{url}/service1.jpg", alt="", has_alt=False),
            ImageAudit(src=f"{url}/service2.jpg", alt="", has_alt=False),
        ],
        images_without_alt=2,
        internal_links=[
            LinkInfo(url=url, anchor_text="Hem"),
            LinkInfo(url=f"{url}/kontakt", anchor_text="Kontakt"),
        ],
        external_links=[],
    )

    contact_page = PageSeoData(
        url=f"{url}/kontakt",
        status_code=200,
        title="Kontakta Oss",
        title_length=12,
        meta_description="Kontakta vår tandläkarmottagning i Stockholm för bokning.",
        meta_description_length=56,
        h1="Kontakta oss",
        h1_count=1,
        headings=[{"tag": "h1", "text": "Kontakta oss"}],
        heading_hierarchy_valid=True,
        body_text="Ring oss på 08-123 456 78. " * 5,
        word_count=35,
        internal_links=[LinkInfo(url=url, anchor_text="Tillbaka till startsidan")],
        external_links=[],
    )

    about_page = PageSeoData(
        url=f"{url}/om-oss",
        status_code=200,
        title="Tandvård Stockholm",
        title_length=19,
        meta_description="Lär känna vårt team av tandläkare i Stockholm.",
        meta_description_length=47,
        h1="Om oss",
        h1_count=1,
        headings=[
            {"tag": "h1", "text": "Om oss"},
            {"tag": "h2", "text": "Vårt team"},
            {"tag": "h2", "text": "Vår historia"},
        ],
        heading_hierarchy_valid=True,
        body_text="Vi har erbjudit tandvård sedan 1998. Vårt team består av fem tandläkare. " * 15,
        word_count=195,
        internal_links=[
            LinkInfo(url=url, anchor_text="Hem"),
            LinkInfo(url=f"{url}/tjanster", anchor_text="Tjänster"),
        ],
        external_links=[],
    )

    # Orphan: priser page not linked from others
    prices_page = PageSeoData(
        url=f"{url}/priser",
        status_code=200,
        title="Priser",
        title_length=6,
        meta_description="",
        meta_description_length=0,
        h1="Priser",
        h1_count=1,
        headings=[{"tag": "h1", "text": "Priser"}],
        heading_hierarchy_valid=True,
        body_text="Konsultation: 500 kr. Undersökning: 800 kr. " * 5,
        word_count=50,
        internal_links=[LinkInfo(url=url, anchor_text="Hem")],
        external_links=[],
    )

    from src.models.seo import RobotsTxtData, SitemapData

    return SiteSeoData(
        domain=domain,
        crawl_date=datetime.now(),
        pages=[homepage, services_page, contact_page, about_page, prices_page],
        robots_txt=RobotsTxtData(
            exists=True,
            allows_crawling=True,
            sitemap_urls=[f"https://{domain}/sitemap.xml"],
            disallowed_paths=["/admin/", "/tmp/"],
            raw_content=f"User-agent: *\nDisallow: /admin/\nDisallow: /tmp/\nSitemap: https://{domain}/sitemap.xml",
        ),
        sitemaps=[
            SitemapData(
                exists=True,
                url=f"https://{domain}/sitemap.xml",
                page_count=5,
                urls=[url, f"{url}/tjanster", f"{url}/kontakt", f"{url}/om-oss", f"{url}/priser"],
            )
        ],
        total_pages_crawled=5,
        total_internal_links=10,
        total_external_links=1,
        orphan_pages=[f"{url}/priser"],
    )
