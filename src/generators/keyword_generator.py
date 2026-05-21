"""Keyword research and grouping engine for Swedish + English SEM campaigns."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Literal

from src.models.campaign import Keyword
from src.models.catalog import Product
from src.models.client import ClientProfile
from src.utils.config import PROJECT_ROOT
from src.utils.swedish_nlp import split_compound_word, generate_diacritics_variants

logger = logging.getLogger(__name__)

DATA_DIR = PROJECT_ROOT / "data" / "swedish"

# Swedish-specific modifiers for keyword expansion
SWEDISH_MODIFIERS = [
    "bäst", "billig", "billigaste", "professionell", "bra",
    "nära mig", "i närheten", "lokal", "prisvärd", "kvalitet",
    "snabb", "pålitlig", "erfaren", "auktoriserad", "certifierad",
]

# Common Swedish city names for geo-expansion
SWEDISH_CITIES = [
    "Stockholm", "Göteborg", "Malmö", "Uppsala", "Linköping",
    "Örebro", "Västerås", "Helsingborg", "Norrköping", "Jönköping",
    "Lund", "Umeå", "Gävle", "Sundsvall", "Karlstad",
]

# Diacritics mapping for Swedish character variants
DIACRITICS_MAP = {
    "å": "a", "ä": "a", "ö": "o",
    "Å": "A", "Ä": "A", "Ö": "O",
}


def load_industry_seeds(industry: str) -> list[str]:
    """Load seed keywords for a given industry from data/swedish/industry_keywords.json."""
    path = DATA_DIR / "industry_keywords.json"
    if not path.exists():
        logger.warning("Industry keywords file not found: %s", path)
        return []

    with open(path, encoding="utf-8") as f:
        data: dict[str, list[str]] = json.load(f)

    # Try exact match first, then normalized match
    industry_key = industry.lower().replace(" ", "_").replace("-", "_")
    if industry_key in data:
        return data[industry_key]

    # Fuzzy match on keys
    for key, seeds in data.items():
        if industry_key in key or key in industry_key:
            return seeds

    logger.info("No industry seeds found for '%s', available: %s", industry, list(data.keys()))
    return []


def generate_seed_keywords(
    client: ClientProfile,
    site_content: list[str],
    competitor_keywords: list[str],
) -> list[str]:
    """Combine multiple sources into a deduplicated list of seed keywords.

    Sources: client services, site headings/text, competitor keywords,
    industry templates from data/swedish/industry_keywords.json.
    """
    seeds: set[str] = set()

    # 1. Client services
    for service in client.products_services:
        seeds.add(service.lower().strip())

    # 2. Site content (headings, important text)
    for text in site_content:
        cleaned = text.strip().lower()
        if 2 <= len(cleaned) <= 60:
            seeds.add(cleaned)

    # 3. Competitor keywords
    for kw in competitor_keywords:
        cleaned = kw.strip().lower()
        if cleaned:
            seeds.add(cleaned)

    # 4. Industry-specific seeds
    industry_seeds = load_industry_seeds(client.industry)
    for kw in industry_seeds:
        seeds.add(kw.lower().strip())

    result = sorted(seeds)
    logger.info("Generated %d seed keywords from all sources", len(result))
    return result


def expand_keyword_variations(keyword: str) -> list[str]:
    """Generate keyword variations using compound splitting, diacritics, and plural/singular.

    Returns a list of variant strings (not including the original).
    """
    variants: set[str] = set()
    kw_lower = keyword.lower().strip()

    # 1. Compound splits as separate words
    if " " not in kw_lower and len(kw_lower) > 5:
        parts = split_compound_word(kw_lower)
        if len(parts) > 1:
            variants.add(" ".join(parts))

    # For multi-word keywords, try splitting each word
    if " " in kw_lower:
        words = kw_lower.split()
        for idx, w in enumerate(words):
            if len(w) > 5:
                parts = split_compound_word(w)
                if len(parts) > 1:
                    new_words = words[:idx] + parts + words[idx + 1:]
                    variants.add(" ".join(new_words))

    # 2. Diacritics variants (a/å, a/ä, o/ö)
    diac_variants = generate_diacritics_variants(kw_lower)
    variants.update(diac_variants)

    # 3. Basic plural/singular forms
    if kw_lower.endswith("ar"):
        variants.add(kw_lower[:-2])  # hundar -> hund
    elif kw_lower.endswith("er"):
        variants.add(kw_lower[:-2])  # tjänster -> tjänst
    elif kw_lower.endswith("or"):
        variants.add(kw_lower[:-2])  # faktorer -> faktor (approx)
    elif kw_lower.endswith("na") or kw_lower.endswith("en"):
        variants.add(kw_lower[:-2])  # definite form: bilen -> bil
    elif not kw_lower.endswith("s"):
        # Try adding common plural suffixes
        variants.add(kw_lower + "ar")
        variants.add(kw_lower + "er")

    variants.discard(kw_lower)
    return sorted(variants)


def expand_keywords_swedish(seeds: list[str]) -> list[str]:
    """Expand seed keywords with Swedish-specific variants.

    Includes: compound word variants, diacritics alternatives (a/å, o/ö),
    common modifiers, city name combinations, and keyword variations.
    """
    expanded: set[str] = set()

    for seed in seeds:
        expanded.add(seed)

        # Add keyword variations (compound splits, diacritics, plural/singular)
        variations = expand_keyword_variations(seed)
        expanded.update(variations)

        # Add diacritics-stripped variant
        stripped = seed
        for char, replacement in DIACRITICS_MAP.items():
            stripped = stripped.replace(char, replacement)
        if stripped != seed:
            expanded.add(stripped)

        # Add modifier combinations (only for short seeds to avoid overly long keywords)
        if len(seed.split()) <= 3:
            for modifier in SWEDISH_MODIFIERS:
                expanded.add(f"{modifier} {seed}")
                expanded.add(f"{seed} {modifier}")

        # Add city combinations for service-type keywords
        if len(seed.split()) <= 2:
            for city in SWEDISH_CITIES:
                expanded.add(f"{seed} {city.lower()}")
                expanded.add(f"{seed} i {city.lower()}")

        # If multi-word, also try joining as compound
        if " " in seed:
            parts = seed.split()
            if len(parts) == 2:
                expanded.add("".join(parts))
                expanded.add(parts[0] + "s" + parts[1])

    result = sorted(expanded)
    logger.info("Expanded %d seeds into %d keyword variants", len(seeds), len(result))
    return result


def group_keywords(
    keywords: list[dict],
    max_per_group: int = 20,
) -> dict[str, list[dict]]:
    """Group keywords by semantic similarity/theme.

    Args:
        keywords: List of keyword dicts with at least a 'text' key.
        max_per_group: Maximum keywords per group.

    Returns:
        Dict mapping group_name -> list of keyword dicts.
    """
    groups: dict[str, list[dict]] = defaultdict(list)

    for kw in keywords:
        text = kw.get("text", "").lower()
        words = text.split()

        # Use longest meaningful word as group key
        group_word = max(words, key=len) if words else "other"

        # Normalize group name
        group_name = group_word.replace("-", " ").strip()
        groups[group_name].append(kw)

    # Split groups that exceed max_per_group
    final_groups: dict[str, list[dict]] = {}
    for name, kws in groups.items():
        if len(kws) <= max_per_group:
            final_groups[name] = kws
        else:
            for i in range(0, len(kws), max_per_group):
                chunk = kws[i:i + max_per_group]
                suffix = f" {i // max_per_group + 1}" if i > 0 else ""
                final_groups[f"{name}{suffix}"] = chunk

    logger.info("Grouped %d keywords into %d groups", len(keywords), len(final_groups))
    return final_groups


def assign_match_types(
    keywords: list[dict],
    monthly_budget_sek: int,
) -> list[dict]:
    """Assign match types to keywords based on budget strategy.

    Strategy:
    - <10K SEK/month: Exact + Phrase (tight control)
    - 10-30K SEK/month: Phrase primary, some Exact for top terms
    - >30K SEK/month: Broad + smart bidding friendly
    """
    result = []

    for kw in keywords:
        kw_copy = dict(kw)

        if monthly_budget_sek < 10_000:
            # Tight budget: exact and phrase only
            kw_exact = dict(kw_copy, match_type="EXACT")
            kw_phrase = dict(kw_copy, match_type="PHRASE")
            result.extend([kw_exact, kw_phrase])

        elif monthly_budget_sek <= 30_000:
            # Medium budget: phrase primary
            kw_phrase = dict(kw_copy, match_type="PHRASE")
            result.append(kw_phrase)
            # Add exact for high-value keywords (those with CPC data or short terms)
            text = kw_copy.get("text", "")
            if len(text.split()) <= 2 or kw_copy.get("avg_cpc_sek", 0) and kw_copy["avg_cpc_sek"] > 10:
                kw_exact = dict(kw_copy, match_type="EXACT")
                result.append(kw_exact)

        else:
            # High budget: broad for smart bidding
            kw_broad = dict(kw_copy, match_type="BROAD")
            result.append(kw_broad)

    logger.info(
        "Assigned match types for %d keywords (budget: %d SEK), produced %d entries",
        len(keywords), monthly_budget_sek, len(result),
    )
    return result


def generate_negative_keywords(
    target_keywords: list[str],
    industry: str,
) -> list[str]:
    """Generate negative keyword list from universal negatives + industry-specific terms.

    Loads from data/swedish/negative_keywords.json and ensures no conflicts
    with target keywords.
    """
    path = DATA_DIR / "negative_keywords.json"
    negatives: set[str] = set()

    if path.exists():
        with open(path, encoding="utf-8") as f:
            data: dict[str, list[str]] = json.load(f)

        # Add all universal negative categories
        for category, terms in data.items():
            for term in terms:
                negatives.add(term.lower().strip())
    else:
        logger.warning("Negative keywords file not found: %s", path)

    # Remove any negatives that conflict with target keywords
    target_set = {kw.lower().strip() for kw in target_keywords}
    conflicts = negatives & target_set
    if conflicts:
        logger.warning(
            "Removed %d negative keywords that conflict with targets: %s",
            len(conflicts), conflicts,
        )
        negatives -= conflicts

    # Also remove negatives that are substrings of target keywords
    to_remove = set()
    for neg in negatives:
        for target in target_set:
            if neg in target.split():
                to_remove.add(neg)
                break
    if to_remove:
        logger.warning(
            "Removed %d negative keywords that appear in target keyword phrases: %s",
            len(to_remove), to_remove,
        )
        negatives -= to_remove

    result = sorted(negatives)
    logger.info("Generated %d negative keywords for industry '%s'", len(result), industry)
    return result


# ---------------------------------------------------------------------------
# Catalog-driven keyword templating (C9)
# ---------------------------------------------------------------------------


MatchType = Literal["BROAD", "PHRASE", "EXACT"]

_KEYWORD_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _resolve_placeholder(name: str, product: Product) -> str | None:
    if name == "name":
        return product.name
    if name == "sku":
        return product.sku
    val = product.attributes.get(name)
    if val is None:
        return None
    return str(val)


# Google Ads keyword text rules: letters, digits, whitespace, and a narrow
# punctuation allowlist. Anything else is stripped (with surrounding whitespace
# collapsed) so a destination name like "West Palm Beach (Florida)" still
# produces a valid keyword "West Palm Beach Florida".
#
# Comma is explicitly NOT in the allowed list — Google rejects keywords like
# "flights to Paris, France" as having invalid characters. Period and slash
# are also rejected. The empirically-safe allowlist is: hyphen, ampersand,
# apostrophe, plus.
_KEYWORD_ALLOWED_PUNCT = "-&'+"
_KEYWORD_DISALLOWED_RE = re.compile(
    r"[^\w\s" + re.escape(_KEYWORD_ALLOWED_PUNCT) + r"]",
    flags=re.UNICODE,
)


def sanitize_keyword_text(text: str) -> str:
    """Strip characters Google Ads does not accept in keyword text.

    Disallowed by Google: parentheses, brackets, `*`, `!`, `?`, `/`, `\\`,
    `:`, `;`, `@`, `#`, `$`, etc. Allowed: letters / digits / whitespace plus
    `- + & ' . ,`. We replace each disallowed char with a space then collapse
    whitespace so the result remains a valid multi-word keyword.
    """
    out = _KEYWORD_DISALLOWED_RE.sub(" ", text)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def render_keyword_template(template: str, product: Product) -> str | None:
    """Render a single keyword template for one product.

    Returns None if any required placeholder is missing (skipped rather than
    rendered with an empty string — empty keywords pollute the structure).
    """
    parts: list[str] = []
    last = 0
    for match in _KEYWORD_PLACEHOLDER_RE.finditer(template):
        parts.append(template[last:match.start()])
        val = _resolve_placeholder(match.group(1), product)
        if val is None or val == "":
            return None
        parts.append(val)
        last = match.end()
    parts.append(template[last:])
    text = "".join(parts).strip()
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Sanitize disallowed characters (parentheses, brackets, etc.)
    text = sanitize_keyword_text(text)
    return text or None


def generate_keywords_for_product(
    product: Product,
    templates: list[str],
    match_types: list[MatchType] | None = None,
) -> list[Keyword]:
    """Expand `templates` against `product` and produce one Keyword per template × match_type.

    When the product carries `aliases` (alternate names harvested from
    duplicate-primary-key source rows — e.g. 'Bali' / 'Denpasar Bali' /
    'Bali Denpasar' all sharing IATA 'DPS'), each `{name}`-templated keyword
    is also rendered against every alias so the ad group's match-coverage
    spans every name the catalog had for the destination. Templates that
    don't reference `{name}` (e.g. '{sku} flights') only render once per
    product since the alias swap is name-only. Dedup is global across the
    name + every alias.
    """
    match_types = match_types or ["PHRASE"]
    out: list[Keyword] = []
    seen: set[tuple[str, str]] = set()

    # Variants of the product to render against: the canonical record first,
    # then a clone per alias (with name swapped). Limit to a reasonable cap
    # to keep ad-group keyword counts from exploding for pathological
    # catalogs — 5 alternates per destination covers every legitimate case
    # in the etraveli dataset (NYC has 3, DFW has 3, the rest have 2).
    variants: list[Product] = [product]
    for alias in (product.aliases or [])[:5]:
        alias_str = (alias or "").strip()
        if not alias_str or alias_str.lower() == product.name.lower():
            continue
        variants.append(product.model_copy(update={"name": alias_str}))

    for template in templates:
        # Templates that don't reference {name} render identically across
        # variants — skip the alias loop to avoid wasted dedup hits.
        template_uses_name = "{name}" in template
        applicable = variants if template_uses_name else variants[:1]
        for p in applicable:
            text = render_keyword_template(template, p)
            if not text:
                continue
            if len(text) > 80:
                logger.warning("Skipping keyword > 80 chars: %r", text)
                continue
            for mt in match_types:
                key = (text.lower(), mt)
                if key in seen:
                    continue
                seen.add(key)
                out.append(Keyword(text=text, match_type=mt))
    return out

