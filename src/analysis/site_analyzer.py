"""Site analysis: landing page quality, conversion elements, SEO basics."""

from __future__ import annotations

import logging
import re

from src.models.research import CrawledPage, SiteCrawl

logger = logging.getLogger(__name__)


def analyze_site(site_crawl: SiteCrawl) -> dict:
    """Assess site quality for SEM campaign purposes.

    Returns dict with: landing_page_quality, conversion_elements,
    mobile_indicators, content_gaps, seo_basics.
    """
    pages = site_crawl.pages
    if not pages:
        return {
            "landing_page_quality": {},
            "conversion_elements": [],
            "mobile_indicators": {},
            "content_gaps": [],
            "seo_basics": {},
        }

    homepage = pages[0]
    page_scores = [score_landing_page(p) for p in pages]
    avg_score = _average_scores(page_scores)

    return {
        "landing_page_quality": {
            "homepage_score": score_landing_page(homepage),
            "average_score": avg_score,
            "page_count": len(pages),
            "pages_with_forms": sum(1 for p in pages if p.has_form),
            "pages_with_phone": sum(1 for p in pages if p.phones),
            "pages_with_chat": sum(1 for p in pages if p.has_chat_widget),
        },
        "conversion_elements": find_conversion_points(pages),
        "mobile_indicators": _check_mobile_indicators(pages),
        "content_gaps": _find_content_gaps(pages),
        "seo_basics": _assess_seo(pages),
    }


def score_landing_page(page: CrawledPage) -> dict:
    """Score a single page for landing page quality.

    Returns dict with boolean/numeric scores for key quality factors.
    """
    body_len = len(page.body_text) if page.body_text else 0
    has_cta = bool(re.search(
        r"kontakta|boka|offert|ring|beställ|köp|prova|kom igång|anmäl",
        page.body_text.lower()
    )) if page.body_text else False

    return {
        "url": page.url,
        "has_h1": bool(page.h1),
        "has_cta": has_cta,
        "has_form": page.has_form,
        "has_phone": bool(page.phones),
        "content_length": body_len,
        "content_sufficient": body_len >= 300,
        "meta_present": bool(page.meta_description),
        "meta_length_ok": 50 <= len(page.meta_description or "") <= 160,
        "title_present": bool(page.title),
        "heading_structure": _check_heading_structure(page.headings),
    }


def find_conversion_points(pages: list[CrawledPage]) -> list[dict]:
    """Find all conversion-related elements across the site."""
    conversion_points: list[dict] = []

    for page in pages:
        points: list[str] = []

        if page.has_form:
            points.append("form")
        if page.phones:
            points.append(f"phone: {', '.join(page.phones[:3])}")
        if page.has_chat_widget:
            points.append("chat_widget")

        body_lower = page.body_text.lower() if page.body_text else ""
        if re.search(r"mailto:", body_lower):
            points.append("email_link")
        if re.search(r"offert|quote|pris", body_lower):
            points.append("quote_request")
        if re.search(r"boka|book|appointment|tid", body_lower):
            points.append("booking")

        if points:
            conversion_points.append({
                "url": page.url,
                "title": page.title,
                "elements": points,
            })

    return conversion_points


def _check_heading_structure(headings: list[dict]) -> bool:
    """Check if headings follow a logical structure."""
    if not headings:
        return False
    tags = [h.get("tag", "") for h in headings]
    if "h1" not in tags:
        return False
    if tags.count("h1") > 1:
        return False
    return True


def _average_scores(scores: list[dict]) -> dict:
    """Calculate average boolean scores across all pages."""
    if not scores:
        return {}
    bool_keys = ["has_h1", "has_cta", "has_form", "has_phone", "meta_present", "content_sufficient"]
    avg: dict = {}
    for key in bool_keys:
        values = [s.get(key, False) for s in scores]
        avg[f"pct_{key}"] = round(sum(1 for v in values if v) / len(values) * 100, 1)
    content_lengths = [s.get("content_length", 0) for s in scores]
    avg["avg_content_length"] = round(sum(content_lengths) / len(content_lengths)) if content_lengths else 0
    return avg


def _check_mobile_indicators(pages: list[CrawledPage]) -> dict:
    """Check for mobile-friendly indicators in crawled content."""
    has_viewport = False
    has_responsive_hints = False

    for page in pages:
        text = page.body_text.lower() if page.body_text else ""
        if "viewport" in text:
            has_viewport = True
        if any(term in text for term in ["responsive", "mobil", "mobile"]):
            has_responsive_hints = True

    return {
        "viewport_meta_detected": has_viewport,
        "responsive_hints": has_responsive_hints,
        "note": "Full mobile audit requires browser rendering check",
    }


def _find_content_gaps(pages: list[CrawledPage]) -> list[str]:
    """Identify common content gaps for SEM landing pages."""
    gaps: list[str] = []
    all_text = " ".join(p.body_text.lower() for p in pages if p.body_text)

    checks = [
        ("pricing/cost info", ["pris", "kostnad", "kostar", "offert"]),
        ("testimonials/reviews", ["omdöme", "recension", "kund säger", "kundröster"]),
        ("FAQ section", ["faq", "vanliga frågor", "frågor och svar"]),
        ("trust signals", ["certifierad", "garanti", "försäkring", "auktoriserad"]),
        ("about/team page", ["om oss", "vårt team", "vår historia"]),
        ("service area info", ["område", "leverans", "var vi finns"]),
        ("contact information", ["kontakt", "adress", "telefon"]),
    ]

    for label, terms in checks:
        if not any(term in all_text for term in terms):
            gaps.append(f"Missing: {label}")

    has_any_form = any(p.has_form for p in pages)
    if not has_any_form:
        gaps.append("Missing: contact/lead form")

    has_any_phone = any(p.phones for p in pages)
    if not has_any_phone:
        gaps.append("Missing: visible phone number")

    return gaps


def _assess_seo(pages: list[CrawledPage]) -> dict:
    """Basic SEO assessment for the site."""
    total = len(pages)
    if total == 0:
        return {}

    missing_title = sum(1 for p in pages if not p.title)
    missing_meta = sum(1 for p in pages if not p.meta_description)
    missing_h1 = sum(1 for p in pages if not p.h1)
    duplicate_titles = total - len(set(p.title for p in pages if p.title))

    return {
        "total_pages": total,
        "missing_title": missing_title,
        "missing_meta_description": missing_meta,
        "missing_h1": missing_h1,
        "duplicate_titles": duplicate_titles,
        "avg_title_length": round(
            sum(len(p.title or "") for p in pages) / total, 1
        ),
        "avg_meta_length": round(
            sum(len(p.meta_description or "") for p in pages) / total, 1
        ),
    }
