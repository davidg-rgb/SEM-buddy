"""Competitor SEO comparison and gap analysis."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from src.models.seo import (
    CompetitorSeoProfile,
    IssueCategory,
    PageSeoData,
    SeoCompetitorAnalysis,
    SeoGap,
    SeoScorecard,
)

logger = logging.getLogger(__name__)


async def analyze_competitor_seo(
    client_url: str,
    competitor_urls: list[str],
    client_scorecard: SeoScorecard,
    client_page: PageSeoData | None,
) -> SeoCompetitorAnalysis:
    """Scrape each competitor URL, score it, produce gap analysis."""
    from src.scrapers.seo_scraper import crawl_seo_single
    from src.analysis.seo_analyzer import analyze_page_seo

    competitors: list[CompetitorSeoProfile] = []

    for comp_url in competitor_urls:
        try:
            logger.info("Analyzing competitor: %s", comp_url)
            comp_page = await crawl_seo_single(comp_url)
            comp_scorecard = analyze_page_seo(comp_page)
            domain = urlparse(comp_url).netloc

            competitors.append(CompetitorSeoProfile(
                url=comp_url,
                domain=domain,
                scorecard=comp_scorecard,
                page_data=comp_page,
            ))
        except Exception as exc:
            logger.warning("Could not analyze competitor %s: %s", comp_url, exc)
            domain = urlparse(comp_url).netloc
            competitors.append(CompetitorSeoProfile(
                url=comp_url,
                domain=domain,
            ))

    # Compute gaps and advantages
    all_gaps: list[SeoGap] = []
    for comp in competitors:
        if client_page and comp.page_data:
            gaps = _compute_gaps(client_page, client_scorecard, comp.page_data, comp.scorecard)
            all_gaps.extend(gaps)

    advantages = _identify_advantages(client_scorecard, [c.scorecard for c in competitors])

    return SeoCompetitorAnalysis(
        client_url=client_url,
        client_scorecard=client_scorecard,
        competitors=competitors,
        gaps=all_gaps,
        advantages=advantages,
    )


def _compute_gaps(
    client: PageSeoData,
    client_score: SeoScorecard,
    competitor: PageSeoData,
    competitor_score: SeoScorecard,
) -> list[SeoGap]:
    """Compare client vs competitor and return gaps where competitor is stronger."""
    gaps: list[SeoGap] = []
    domain = urlparse(competitor.url).netloc

    # Schema markup gap
    client_schemas = len(client.schema_markup)
    comp_schemas = len(competitor.schema_markup)
    if comp_schemas > 0 and client_schemas == 0:
        comp_types = ", ".join(s.schema_type for s in competitor.schema_markup)
        gaps.append(SeoGap(
            area="Schema markup",
            client_value="Saknas",
            competitor_value=comp_types,
            competitor_domain=domain,
            recommendation=f"Lägg till JSON-LD schema ({comp_types}) för att matcha konkurrenten.",
        ))

    # Content length gap
    if competitor.word_count > client.word_count * 1.5 and competitor.word_count >= 500:
        gaps.append(SeoGap(
            area="Innehållslängd",
            client_value=f"{client.word_count} ord",
            competitor_value=f"{competitor.word_count} ord",
            competitor_domain=domain,
            recommendation=f"Utöka innehållet till minst {competitor.word_count} ord för att matcha konkurrenten.",
        ))

    # Image optimization gap
    client_alt_pct = _alt_text_pct(client)
    comp_alt_pct = _alt_text_pct(competitor)
    if comp_alt_pct > client_alt_pct + 30 and comp_alt_pct >= 80:
        gaps.append(SeoGap(
            area="Bild-optimering (alt-text)",
            client_value=f"{client_alt_pct:.0f}% har alt-text",
            competitor_value=f"{comp_alt_pct:.0f}% har alt-text",
            competitor_domain=domain,
            recommendation="Lägg till beskrivande alt-text på alla bilder.",
        ))

    # Internal linking gap
    client_links = len(client.internal_links)
    comp_links = len(competitor.internal_links)
    if comp_links > client_links * 2 and comp_links >= 5:
        gaps.append(SeoGap(
            area="Intern länkning",
            client_value=f"{client_links} länkar",
            competitor_value=f"{comp_links} länkar",
            competitor_domain=domain,
            recommendation="Förbättra intern länkning med fler kontextuella länkar mellan sidor.",
        ))

    # Meta description gap
    if not client.meta_description and competitor.meta_description:
        gaps.append(SeoGap(
            area="Meta-beskrivning",
            client_value="Saknas",
            competitor_value=f"{competitor.meta_description_length} tecken",
            competitor_domain=domain,
            recommendation="Skriv en unik meta-beskrivning (120-160 tecken) med sökord och CTA.",
        ))

    # Heading structure gap
    if not client.heading_hierarchy_valid and competitor.heading_hierarchy_valid:
        gaps.append(SeoGap(
            area="Rubrikstruktur",
            client_value="Bruten hierarki",
            competitor_value="Korrekt hierarki",
            competitor_domain=domain,
            recommendation="Strukturera rubrikerna hierarkiskt: H1 → H2 → H3 utan att hoppa över nivåer.",
        ))

    # CWV / page speed gap (based on render-blocking resources as proxy without Lighthouse)
    client_blocking = len(client.render_blocking_resources)
    comp_blocking = len(competitor.render_blocking_resources)
    if comp_blocking < client_blocking and client_blocking > 3 and comp_blocking <= 2:
        gaps.append(SeoGap(
            area="Sidladdningstid",
            client_value=f"{client_blocking} renderingsblockerande resurser",
            competitor_value=f"{comp_blocking} renderingsblockerande resurser",
            competitor_domain=domain,
            recommendation="Minska antal renderingsblockerande resurser genom att använda async/defer och inline kritisk CSS.",
        ))

    # Category-level score gaps
    client_cats = {cs.category: cs.score for cs in client_score.category_scores}
    comp_cats = {cs.category: cs.score for cs in competitor_score.category_scores}
    for cat in IssueCategory:
        c_score = client_cats.get(cat, 0)
        comp_s = comp_cats.get(cat, 0)
        if comp_s > c_score + 20:
            cat_labels = {
                IssueCategory.ON_PAGE: "On-page SEO",
                IssueCategory.TECHNICAL: "Teknisk SEO",
                IssueCategory.CONTENT: "Innehåll",
                IssueCategory.LINKS: "Länkstruktur",
                IssueCategory.SCHEMA: "Strukturerad data",
            }
            gaps.append(SeoGap(
                area=cat_labels.get(cat, cat.value),
                client_value=f"{c_score:.0f}/100",
                competitor_value=f"{comp_s:.0f}/100",
                competitor_domain=domain,
                recommendation=f"Fokusera på att förbättra {cat_labels.get(cat, cat.value).lower()} för att matcha konkurrenten.",
            ))

    return gaps


def _identify_advantages(
    client_score: SeoScorecard,
    competitor_scores: list[SeoScorecard],
) -> list[str]:
    """Identify categories where client outperforms all competitors."""
    advantages: list[str] = []
    client_cats = {cs.category: cs.score for cs in client_score.category_scores}

    cat_labels = {
        IssueCategory.ON_PAGE: "On-page SEO",
        IssueCategory.TECHNICAL: "Teknisk SEO",
        IssueCategory.CONTENT: "Innehåll",
        IssueCategory.LINKS: "Länkstruktur",
        IssueCategory.SCHEMA: "Strukturerad data",
    }

    for cat in IssueCategory:
        c_score = client_cats.get(cat, 0)
        if c_score < 50:
            continue
        all_lower = True
        for comp_sc in competitor_scores:
            comp_cats = {cs.category: cs.score for cs in comp_sc.category_scores}
            if comp_cats.get(cat, 0) >= c_score:
                all_lower = False
                break
        if all_lower and competitor_scores:
            label = cat_labels.get(cat, cat.value)
            advantages.append(f"Starkare {label.lower()} ({c_score:.0f}/100) än alla analyserade konkurrenter.")

    if client_score.overall_score > max((s.overall_score for s in competitor_scores), default=0):
        advantages.append(f"Högst total SEO-poäng ({client_score.overall_score:.0f}/100) bland alla analyserade webbplatser.")

    return advantages


def _alt_text_pct(page: PageSeoData) -> float:
    if not page.images:
        return 100.0
    with_alt = sum(1 for img in page.images if img.has_alt)
    return (with_alt / len(page.images)) * 100


# ---------------------------------------------------------------------------
# Synthetic competitor data for --dry-run
# ---------------------------------------------------------------------------


def generate_synthetic_competitor_data(
    competitor_urls: list[str],
    client_scorecard: SeoScorecard,
) -> SeoCompetitorAnalysis:
    """Generate synthetic competitor data for dry-run mode."""
    from src.scrapers.seo_scraper import generate_synthetic_page_data
    from src.analysis.seo_analyzer import analyze_page_seo
    from src.models.seo import SchemaMarkup

    competitors: list[CompetitorSeoProfile] = []

    for i, comp_url in enumerate(competitor_urls):
        comp_page = generate_synthetic_page_data(comp_url)
        # Make competitor slightly different
        comp_page.word_count = 1200 + i * 200
        comp_page.body_text = "word " * comp_page.word_count
        comp_page.schema_markup = [
            SchemaMarkup(
                schema_type="LocalBusiness",
                format="json-ld",
                raw_data={"@type": "LocalBusiness", "name": f"Competitor {i + 1}"},
            )
        ]
        comp_page.images_without_alt = 0
        for img in comp_page.images:
            img.has_alt = True
            img.alt = "Descriptive alt text"

        comp_scorecard = analyze_page_seo(comp_page)
        domain = urlparse(comp_url).netloc

        competitors.append(CompetitorSeoProfile(
            url=comp_url,
            domain=domain,
            scorecard=comp_scorecard,
            page_data=comp_page,
        ))

    # Compute gaps
    client_page = generate_synthetic_page_data("https://client.se")
    all_gaps: list[SeoGap] = []
    for comp in competitors:
        if comp.page_data:
            gaps = _compute_gaps(client_page, client_scorecard, comp.page_data, comp.scorecard)
            all_gaps.extend(gaps)

    advantages = _identify_advantages(client_scorecard, [c.scorecard for c in competitors])

    return SeoCompetitorAnalysis(
        client_url="https://client.se",
        client_scorecard=client_scorecard,
        competitors=competitors,
        gaps=all_gaps,
        advantages=advantages,
    )
