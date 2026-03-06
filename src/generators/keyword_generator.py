"""Keyword research and grouping engine for Swedish SEM campaigns."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

from src.models.campaign import Keyword
from src.models.client import ClientProfile
from src.utils.config import PROJECT_ROOT

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


def expand_keywords_swedish(seeds: list[str]) -> list[str]:
    """Expand seed keywords with Swedish-specific variants.

    Includes: compound word variants, diacritics alternatives (a/å, o/ö),
    common modifiers, and city name combinations.
    """
    expanded: set[str] = set()

    for seed in seeds:
        expanded.add(seed)

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

        # Compound word splitting/joining (Swedish compound words)
        # e.g., "badrumsrenovering" -> "badrums renovering"
        if len(seed) > 10 and " " not in seed:
            # Try splitting at common Swedish compound boundaries
            for i in range(4, len(seed) - 3):
                if seed[i] == "s" and i > 3:
                    variant = seed[:i + 1] + " " + seed[i + 1:]
                    expanded.add(variant)
                    break

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
