"""Swedish RSA ad copy generator for Google Ads campaigns."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from src.models.campaign import AdHeadline, AdDescription, ResponsiveSearchAd
from src.models.client import ClientProfile
from src.utils.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

DATA_DIR = PROJECT_ROOT / "data" / "swedish"

# Swedish ad copy conventions
SWEDISH_AD_RULES = {
    "address_form": "du",  # Always use "du" (informal you), never "ni"
    "price_format": "1 299 kr",  # Space as thousand separator, "kr" suffix
    "phone_format": "070-123 45 67",  # Swedish phone format
    "currency": "SEK",
    "decimal_separator": ",",
    "thousand_separator": " ",
    "common_abbreviations": {
        "telefon": "tel",
        "information": "info",
        "professionell": "prof.",
        "kostnadsfri": "gratis",
    },
}

# Headline types and their priorities for RSA
HEADLINE_TYPES = ["brand", "service", "cta", "usp", "location", "price"]


def _load_json(filename: str) -> dict:
    """Load a JSON file from the Swedish data directory."""
    path = DATA_DIR / filename
    if not path.exists():
        logger.warning("Data file not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _apply_swedish_rules(text: str) -> str:
    """Enforce Swedish ad copy conventions.

    - Use 'du' form (not 'ni')
    - Swedish price format: '1 299 kr'
    - Proper compound words
    """
    # Replace "ni" addressing with "du" in common phrases
    replacements = {
        "Kontakta er": "Kontakta oss",
        "kontakta er": "kontakta oss",
        "Er ": "Din ",
        "Ert ": "Ditt ",
        "Era ": "Dina ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Format prices: convert "1299kr" or "1299 kr" to "1 299 kr"
    def format_price(match: re.Match) -> str:
        num_str = match.group(1).replace(" ", "")
        num = int(num_str)
        formatted = f"{num:,}".replace(",", " ")
        return f"{formatted} kr"

    text = re.sub(r"(\d[\d ]+)\s*kr\b", format_price, text)

    return text


def _fit_to_limit(text: str, max_chars: int) -> str:
    """Truncate or abbreviate text to fit character limit while keeping meaning."""
    if len(text) <= max_chars:
        return text

    # Try common abbreviations first
    abbreviated = text
    for long_form, short_form in SWEDISH_AD_RULES["common_abbreviations"].items():
        abbreviated = abbreviated.replace(long_form, short_form)
        abbreviated = abbreviated.replace(long_form.capitalize(), short_form.capitalize())
        if len(abbreviated) <= max_chars:
            return abbreviated

    # Remove filler words
    filler_words = [" och ", " samt ", " med ", " för ", " din ", " ditt "]
    trimmed = abbreviated
    for filler in filler_words:
        if len(trimmed) > max_chars:
            trimmed = trimmed.replace(filler, " & " if filler in (" och ", " samt ") else " ")

    if len(trimmed) <= max_chars:
        return trimmed

    # Last resort: truncate at word boundary
    if len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars].rsplit(" ", 1)[0]

    return trimmed


def _fill_pattern(
    pattern: str,
    client: ClientProfile,
    theme: str,
    keywords: list[str],
) -> str:
    """Fill a pattern template with client and keyword data."""
    primary_service = theme or (client.products_services[0] if client.products_services else "")
    primary_city = ""
    if client.geographic_targets:
        primary_city = client.geographic_targets[0].name

    replacements = {
        "{Företag}": client.business_name,
        "{företag}": client.business_name.lower(),
        "{Tjänst}": primary_service.capitalize(),
        "{tjänst}": primary_service.lower(),
        "{Stad}": primary_city,
        "{stad}": primary_city.lower(),
        "{Pris}": "499",
        "{Antal}": "100",
        "{antal}": "10",
        "{Telefon}": "",
        "{telefon}": "",
        "{CTA}": "Kontakta oss idag",
    }

    result = pattern
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    # Clean up any remaining empty placeholders
    result = re.sub(r"\s*-\s*$", "", result)
    result = re.sub(r"\s{2,}", " ", result).strip()

    return result


def generate_headlines(
    ad_group_theme: str,
    client: ClientProfile,
    keywords: list[str],
) -> list[AdHeadline]:
    """Generate up to 15 headlines (max 30 chars each) for an ad group.

    Mix of types: brand, service, CTA, USP, location, price.
    Loads patterns from data/swedish/ad_copy_patterns.json and
    CTAs from data/swedish/cta_phrases.json.
    """
    patterns_data = _load_json("ad_copy_patterns.json")
    cta_data = _load_json("cta_phrases.json")

    headline_patterns = patterns_data.get("headline_patterns", [])
    headlines: list[AdHeadline] = []
    seen_texts: set[str] = set()

    def _add_headline(text: str) -> bool:
        text = _apply_swedish_rules(text)
        text = _fit_to_limit(text, 30)
        if not text or text in seen_texts or len(text) > 30:
            return False
        seen_texts.add(text)
        headlines.append(AdHeadline(text=text))
        return True

    # 1. Brand headline (pinned to position 1)
    _add_headline(client.business_name)

    # 2. Service/theme headline (pinned to position 2)
    _add_headline(ad_group_theme.capitalize())

    # 3. Generate from patterns
    for pat in headline_patterns:
        if len(headlines) >= 15:
            break
        filled = _fill_pattern(pat["pattern"], client, ad_group_theme, keywords)
        _add_headline(filled)

    # 4. CTA headlines from cta_phrases.json
    for category in ["quote", "contact", "book"]:
        if len(headlines) >= 15:
            break
        phrases = cta_data.get(category, [])
        for phrase in phrases[:2]:
            if len(headlines) >= 15:
                break
            _add_headline(phrase)

    # 5. Keyword-based headlines
    for kw in keywords[:5]:
        if len(headlines) >= 15:
            break
        _add_headline(kw.capitalize())

    # 6. Location-based if we have geo targets
    if client.geographic_targets:
        for geo in client.geographic_targets[:2]:
            if len(headlines) >= 15:
                break
            _add_headline(f"{ad_group_theme.capitalize()} i {geo.name}")
            _add_headline(f"{geo.name} - {ad_group_theme.capitalize()}")

    logger.info(
        "Generated %d headlines for ad group '%s'",
        len(headlines), ad_group_theme,
    )
    return headlines[:15]


def generate_descriptions(
    ad_group_theme: str,
    client: ClientProfile,
    keywords: list[str],
) -> list[AdDescription]:
    """Generate up to 4 descriptions (max 90 chars each) for an ad group."""
    patterns_data = _load_json("ad_copy_patterns.json")
    description_patterns = patterns_data.get("description_patterns", [])

    descriptions: list[AdDescription] = []
    seen_texts: set[str] = set()

    def _add_description(text: str) -> bool:
        text = _apply_swedish_rules(text)
        text = _fit_to_limit(text, 90)
        if not text or text in seen_texts or len(text) > 90:
            return False
        seen_texts.add(text)
        descriptions.append(AdDescription(text=text))
        return True

    # Generate from patterns
    for pat in description_patterns:
        if len(descriptions) >= 4:
            break
        filled = _fill_pattern(pat["pattern"], client, ad_group_theme, keywords)
        _add_description(filled)

    # Fallback descriptions if patterns didn't produce enough
    fallbacks = [
        f"Professionell {ad_group_theme.lower()} till bra priser. Kontakta oss för en kostnadsfri offert.",
        f"{client.business_name} erbjuder {ad_group_theme.lower()}. Ring oss idag för mer information.",
        f"Behöver du {ad_group_theme.lower()}? Vi hjälper dig snabbt och professionellt.",
        f"Boka {ad_group_theme.lower()} online. Snabb service och nöjd kund-garanti.",
    ]
    for fb in fallbacks:
        if len(descriptions) >= 4:
            break
        _add_description(fb)

    logger.info(
        "Generated %d descriptions for ad group '%s'",
        len(descriptions), ad_group_theme,
    )
    return descriptions[:4]


def generate_rsa(
    ad_group_theme: str,
    client: ClientProfile,
    keywords: list[str],
    final_url: str,
) -> ResponsiveSearchAd:
    """Generate a full Responsive Search Ad with headlines, descriptions, URL, and paths."""
    headlines = generate_headlines(ad_group_theme, client, keywords)
    descriptions = generate_descriptions(ad_group_theme, client, keywords)

    # Generate URL paths from theme
    theme_words = ad_group_theme.lower().split()
    path1 = _fit_to_limit(theme_words[0] if theme_words else "", 15)
    path2 = _fit_to_limit(theme_words[1] if len(theme_words) > 1 else "", 15)

    # Ensure minimum requirements
    if len(headlines) < 3:
        logger.warning("Only %d headlines generated, minimum is 3", len(headlines))
        while len(headlines) < 3:
            headlines.append(AdHeadline(text=f"{ad_group_theme[:30]}"))

    if len(descriptions) < 2:
        logger.warning("Only %d descriptions generated, minimum is 2", len(descriptions))
        while len(descriptions) < 2:
            descriptions.append(AdDescription(text=f"{client.business_name} - {ad_group_theme}"[:90]))

    return ResponsiveSearchAd(
        headlines=headlines,
        descriptions=descriptions,
        final_url=final_url,
        path1=path1,
        path2=path2,
    )
