"""Brand analysis: extract voice, USPs, services, and messaging from site content."""

from __future__ import annotations

import logging
import re
from collections import Counter

from src.models.client import ClientProfile
from src.models.research import CrawledPage, SiteCrawl

logger = logging.getLogger(__name__)

# Common Swedish business/marketing signal words
USP_SIGNALS = [
    "unik", "bäst", "ledande", "garanti", "gratis", "snabb", "billig",
    "professionell", "certifierad", "specialiserad", "prisvärd", "kvalitet",
    "erfarenhet", "trygg", "säker", "pålitlig", "expert", "skräddarsydd",
]

SERVICE_SIGNALS = [
    "tjänster", "service", "erbjuder", "vi hjälper", "våra tjänster",
    "vad vi gör", "lösningar", "produkter",
]

CTA_PATTERNS = [
    r"kontakta oss", r"boka", r"offert", r"ring oss", r"beställ",
    r"få en offert", r"läs mer", r"kom igång", r"prova gratis",
    r"hör av dig", r"anmäl dig",
]


def analyze_brand(client_profile: ClientProfile, site_crawl: SiteCrawl) -> dict:
    """Extract brand characteristics from client profile and crawled site.

    Returns dict with: brand_voice, key_messages, unique_selling_points,
    tone, target_audience_signals.
    """
    pages = site_crawl.pages
    all_text = " ".join(p.body_text for p in pages)

    return {
        "brand_voice": _detect_voice(all_text),
        "key_messages": _extract_key_messages(pages),
        "unique_selling_points": extract_usps(pages),
        "tone": _detect_tone(all_text),
        "target_audience_signals": _detect_audience(all_text),
        "services": identify_services(pages),
    }


def extract_usps(pages: list[CrawledPage]) -> list[str]:
    """Extract unique selling points from page content."""
    usps: list[str] = []
    seen: set[str] = set()

    for page in pages:
        text_lower = page.body_text.lower()
        for heading in page.headings:
            h_text = heading.get("text", "")
            h_lower = h_text.lower()
            for signal in USP_SIGNALS:
                if signal in h_lower and h_lower not in seen:
                    usps.append(h_text.strip())
                    seen.add(h_lower)
                    break

        sentences = re.split(r"[.!]\s+", page.body_text)
        for sentence in sentences:
            s_lower = sentence.lower().strip()
            if len(s_lower) < 10 or len(s_lower) > 200:
                continue
            usp_count = sum(1 for sig in USP_SIGNALS if sig in s_lower)
            if usp_count >= 2 and s_lower[:50] not in seen:
                usps.append(sentence.strip())
                seen.add(s_lower[:50])

    return usps[:15]


def identify_services(pages: list[CrawledPage]) -> list[str]:
    """Identify services offered based on page content and structure."""
    services: list[str] = []
    seen: set[str] = set()

    for page in pages:
        url_lower = page.url.lower()
        if any(s in url_lower for s in ["tjanst", "service", "erbjud", "produkt"]):
            if page.h1 and page.h1.lower() not in seen:
                services.append(page.h1)
                seen.add(page.h1.lower())

        for heading in page.headings:
            h_text = heading.get("text", "")
            h_lower = h_text.lower()
            if heading.get("tag") in ("h2", "h3"):
                text_lower = page.body_text.lower()
                for signal in SERVICE_SIGNALS:
                    if signal in text_lower:
                        nearby = text_lower.find(signal)
                        context = text_lower[max(0, nearby - 200):nearby + 200]
                        if h_lower in context and h_lower not in seen:
                            services.append(h_text.strip())
                            seen.add(h_lower)
                            break

    return services[:20]


def _detect_voice(text: str) -> str:
    """Detect brand voice style from text content."""
    text_lower = text.lower()
    formal_signals = ["ni", "ert", "er", "vänligen", "härmed"]
    informal_signals = ["du", "ditt", "din", "kolla", "lätt"]

    formal_count = sum(text_lower.count(f" {w} ") for w in formal_signals)
    informal_count = sum(text_lower.count(f" {w} ") for w in informal_signals)

    if formal_count > informal_count * 2:
        return "formal"
    elif informal_count > formal_count * 2:
        return "informal"
    return "neutral"


def _detect_tone(text: str) -> str:
    """Detect overall tone of the content."""
    text_lower = text.lower()
    professional = ["professionell", "erfarenhet", "kompetens", "kvalitet", "expertis"]
    friendly = ["välkommen", "hjälpa", "tillsammans", "enkel", "glad"]
    urgent = ["nu", "idag", "begränsad", "missa inte", "erbjudande"]

    scores = {
        "professional": sum(text_lower.count(w) for w in professional),
        "friendly": sum(text_lower.count(w) for w in friendly),
        "urgent": sum(text_lower.count(w) for w in urgent),
    }
    return max(scores, key=scores.get)  # type: ignore[arg-type]


def _extract_key_messages(pages: list[CrawledPage]) -> list[str]:
    """Extract key marketing messages from prominent page elements."""
    messages: list[str] = []
    seen: set[str] = set()

    for page in pages:
        if page.h1 and page.h1.lower() not in seen:
            messages.append(page.h1)
            seen.add(page.h1.lower())
        if page.meta_description and page.meta_description.lower() not in seen:
            messages.append(page.meta_description)
            seen.add(page.meta_description.lower())

    return messages[:10]


def _detect_audience(text: str) -> list[str]:
    """Detect target audience signals from content."""
    signals: list[str] = []
    text_lower = text.lower()

    b2b_terms = ["företag", "verksamhet", "organisation", "b2b", "affär"]
    b2c_terms = ["privat", "hemma", "familj", "b2c", "konsument"]

    b2b_score = sum(text_lower.count(t) for t in b2b_terms)
    b2c_score = sum(text_lower.count(t) for t in b2c_terms)

    if b2b_score > b2c_score:
        signals.append("B2B")
    elif b2c_score > b2b_score:
        signals.append("B2C")
    else:
        signals.append("B2B+B2C")

    location_pattern = re.compile(
        r"(?:stockholm|göteborg|malmö|uppsala|västerås|örebro|linköping|"
        r"helsingborg|norrköping|jönköping|umeå|lund|borås|hela sverige|"
        r"nationellt|lokalt)", re.I
    )
    locations = set(m.group(0).title() for m in location_pattern.finditer(text))
    if locations:
        signals.extend(sorted(locations))

    return signals
