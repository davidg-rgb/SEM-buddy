"""Competitor analysis: positioning, keyword gaps, ad patterns."""

from __future__ import annotations

import logging
import re
from collections import Counter

from src.models.competitor import CompetitorProfile, TransparencyAd

logger = logging.getLogger(__name__)


def analyze_competitors(competitors: list[CompetitorProfile]) -> dict:
    """Summarize competitive landscape from competitor profiles.

    Returns dict with: market_positioning, common_keywords, ad_copy_themes,
    gaps_and_opportunities, price_signals.
    """
    if not competitors:
        return {
            "market_positioning": [],
            "common_keywords": [],
            "ad_copy_themes": [],
            "gaps_and_opportunities": [],
            "price_signals": [],
        }

    all_keywords: list[str] = []
    all_ads: list[TransparencyAd] = []
    positioning: list[dict] = []

    for comp in competitors:
        kw_list = getattr(comp, "top_keywords", []) or []
        all_keywords.extend(kw_list)

        ads_list = getattr(comp, "transparency_ads", []) or []
        all_ads.extend(ads_list)

        positioning.append({
            "domain": getattr(comp, "domain", ""),
            "name": getattr(comp, "name", ""),
            "estimated_spend": getattr(comp, "estimated_monthly_spend", None),
            "keyword_count": len(kw_list),
            "ad_count": len(ads_list),
        })

    keyword_freq = Counter(all_keywords)
    common_keywords = [kw for kw, count in keyword_freq.most_common(30)]
    ad_themes = extract_ad_patterns(all_ads)
    price_signals = _extract_price_signals(all_ads)

    return {
        "market_positioning": positioning,
        "common_keywords": common_keywords,
        "ad_copy_themes": ad_themes,
        "gaps_and_opportunities": _find_opportunities(competitors, common_keywords),
        "price_signals": price_signals,
    }


def find_keyword_gaps(
    our_keywords: list[str],
    competitor_keywords: dict[str, list[str]],
) -> list[str]:
    """Find keywords competitors target that we don't.

    Args:
        our_keywords: Keywords we currently target.
        competitor_keywords: Dict mapping competitor domain to their keyword list.

    Returns list of gap keywords sorted by how many competitors use them.
    """
    our_set = {kw.lower().strip() for kw in our_keywords}
    gap_counter: Counter[str] = Counter()

    for domain, keywords in competitor_keywords.items():
        for kw in keywords:
            kw_lower = kw.lower().strip()
            if kw_lower not in our_set:
                gap_counter[kw_lower] += 1

    return [kw for kw, _count in gap_counter.most_common(50)]


def extract_ad_patterns(ads: list[TransparencyAd]) -> list[str]:
    """Extract common themes and patterns from competitor ad copy."""
    if not ads:
        return []

    patterns: Counter[str] = Counter()

    cta_patterns = [
        (r"(?:boka|beställ|ring|kontakta)", "CTA: direct action"),
        (r"(?:gratis|kostnadsfri|fri)", "offer: free/gratis"),
        (r"(?:rabatt|erbjudande|rea|\d+%)", "offer: discount/deal"),
        (r"(?:snabb|express|samma dag|idag)", "urgency: speed"),
        (r"(?:bäst|ledande|#1|nummer ett)", "positioning: best/leading"),
        (r"(?:pris|billig|prisvärd|lågt pris)", "price: competitive"),
        (r"(?:garanti|trygg|säker|certifierad)", "trust: guarantee/safety"),
        (r"(?:lokal|nära dig|i \w+stad)", "local: geographic"),
        (r"(?:recension|omdöme|betyg|\d+\s*stjärn)", "social proof: reviews"),
        (r"(?:erfarenhet|sedan \d{4}|år)", "trust: experience"),
    ]

    for ad in ads:
        text = (ad.ad_text or "").lower()
        for pattern, label in cta_patterns:
            if re.search(pattern, text):
                patterns[label] += 1

    return [pattern for pattern, _count in patterns.most_common(15)]


def _find_opportunities(
    competitors: list[CompetitorProfile],
    common_keywords: list[str],
) -> list[str]:
    """Identify gaps and opportunities in the competitive landscape."""
    opportunities: list[str] = []

    if len(competitors) >= 2:
        spend_values = [
            getattr(c, "estimated_monthly_spend", None)
            for c in competitors
            if getattr(c, "estimated_monthly_spend", None) is not None
        ]
        if spend_values:
            avg_spend = sum(spend_values) / len(spend_values)
            low_spend = [
                getattr(c, "domain", "unknown")
                for c in competitors
                if (getattr(c, "estimated_monthly_spend", None) or 0) < avg_spend * 0.5
            ]
            if low_spend:
                opportunities.append(
                    f"Weak competition from: {', '.join(low_spend)} (below-average spend)"
                )

    keyword_sets = []
    for comp in competitors:
        kws = getattr(comp, "top_keywords", []) or []
        keyword_sets.append(set(kw.lower() for kw in kws))

    if len(keyword_sets) >= 2:
        all_kws = set()
        for ks in keyword_sets:
            all_kws.update(ks)
        underused = [
            kw for kw in all_kws
            if sum(1 for ks in keyword_sets if kw in ks) == 1
        ]
        if underused:
            opportunities.append(
                f"Undercontested keywords (only 1 competitor): {len(underused)} found"
            )

    return opportunities


def _extract_price_signals(ads: list[TransparencyAd]) -> list[str]:
    """Extract pricing information from ad copy."""
    signals: list[str] = []
    seen: set[str] = set()

    for ad in ads:
        text = ad.ad_text or ""
        price_matches = re.findall(
            r"(?:från\s+)?\d[\d\s]*(?:kr|sek|:-|\s*kronor)",
            text,
            re.I,
        )
        for match in price_matches:
            normalized = match.strip().lower()
            if normalized not in seen:
                signals.append(match.strip())
                seen.add(normalized)

        pct_matches = re.findall(r"\d+\s*%\s*(?:rabatt|off|avdrag)", text, re.I)
        for match in pct_matches:
            normalized = match.strip().lower()
            if normalized not in seen:
                signals.append(match.strip())
                seen.add(normalized)

    return signals[:20]
