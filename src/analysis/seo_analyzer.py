"""SEO scoring engine — 5-category analysis with Swedish issue generation."""

from __future__ import annotations

import logging

from src.models.seo import (
    CategoryScore,
    IssueCategory,
    IssueSeverity,
    LighthouseResult,
    PageSeoData,
    SeoIssue,
    SeoScorecard,
    SiteSeoData,
)

logger = logging.getLogger(__name__)

# Scoring weights
WEIGHT_ON_PAGE = 0.30
WEIGHT_TECHNICAL = 0.25
WEIGHT_CONTENT = 0.20
WEIGHT_LINKS = 0.15
WEIGHT_SCHEMA = 0.10


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_page_seo(
    page: PageSeoData, lighthouse: LighthouseResult | None = None
) -> SeoScorecard:
    """Score a single page across all five SEO categories."""
    on_page_score, on_page_issues = _score_on_page(page)
    technical_score, technical_issues = _score_technical(page, lighthouse)
    content_score, content_issues = _score_content(page)
    links_score, links_issues = _score_links(page)
    schema_score, schema_issues = _score_schema(page)

    overall = (
        on_page_score * WEIGHT_ON_PAGE
        + technical_score * WEIGHT_TECHNICAL
        + content_score * WEIGHT_CONTENT
        + links_score * WEIGHT_LINKS
        + schema_score * WEIGHT_SCHEMA
    )

    all_issues = on_page_issues + technical_issues + content_issues + links_issues + schema_issues

    category_scores = [
        CategoryScore(
            category=IssueCategory.ON_PAGE, score=on_page_score,
            issues_found=len(on_page_issues), label="On-page",
        ),
        CategoryScore(
            category=IssueCategory.TECHNICAL, score=technical_score,
            issues_found=len(technical_issues), label="Teknisk",
        ),
        CategoryScore(
            category=IssueCategory.CONTENT, score=content_score,
            issues_found=len(content_issues), label="Innehåll",
        ),
        CategoryScore(
            category=IssueCategory.LINKS, score=links_score,
            issues_found=len(links_issues), label="Länkar",
        ),
        CategoryScore(
            category=IssueCategory.SCHEMA, score=schema_score,
            issues_found=len(schema_issues), label="Strukturerad data",
        ),
    ]

    summary = _generate_summary(overall, all_issues)

    return SeoScorecard(
        overall_score=round(overall, 1),
        category_scores=category_scores,
        issues=all_issues,
        summary_sv=summary,
    )


def analyze_site_seo(
    site: SiteSeoData, lighthouse: LighthouseResult | None = None
) -> SeoScorecard:
    """Score an entire site — average per-page scores plus site-level checks."""
    if not site.pages:
        return SeoScorecard(
            overall_score=0,
            summary_sv="Inga sidor kunde analyseras.",
        )

    # Score each page (Lighthouse only for first/homepage)
    page_scorecards = []
    for i, page in enumerate(site.pages):
        lh = lighthouse if i == 0 else None
        page_scorecards.append(analyze_page_seo(page, lh))

    # Average per-category scores
    cat_avgs: dict[IssueCategory, float] = {}
    cat_issue_counts: dict[IssueCategory, int] = {}
    for cat in IssueCategory:
        scores = []
        issue_count = 0
        for sc in page_scorecards:
            for cs in sc.category_scores:
                if cs.category == cat:
                    scores.append(cs.score)
                    issue_count += cs.issues_found
        cat_avgs[cat] = sum(scores) / len(scores) if scores else 0
        cat_issue_counts[cat] = issue_count

    # Add site-level issues
    site_issues = _detect_site_level_issues(site)

    # Collect all page-level issues (deduplicate by title, aggregate affected URLs)
    issue_map: dict[str, SeoIssue] = {}
    for sc in page_scorecards:
        for issue in sc.issues:
            if issue.title in issue_map:
                existing = issue_map[issue.title]
                for url in issue.affected_urls:
                    if url not in existing.affected_urls:
                        existing.affected_urls.append(url)
            else:
                issue_map[issue.title] = issue.model_copy(deep=True)

    all_issues = list(issue_map.values()) + site_issues

    overall = (
        cat_avgs.get(IssueCategory.ON_PAGE, 0) * WEIGHT_ON_PAGE
        + cat_avgs.get(IssueCategory.TECHNICAL, 0) * WEIGHT_TECHNICAL
        + cat_avgs.get(IssueCategory.CONTENT, 0) * WEIGHT_CONTENT
        + cat_avgs.get(IssueCategory.LINKS, 0) * WEIGHT_LINKS
        + cat_avgs.get(IssueCategory.SCHEMA, 0) * WEIGHT_SCHEMA
    )

    labels = {
        IssueCategory.ON_PAGE: "On-page",
        IssueCategory.TECHNICAL: "Teknisk",
        IssueCategory.CONTENT: "Innehåll",
        IssueCategory.LINKS: "Länkar",
        IssueCategory.SCHEMA: "Strukturerad data",
    }

    category_scores = [
        CategoryScore(
            category=cat,
            score=round(cat_avgs.get(cat, 0), 1),
            issues_found=cat_issue_counts.get(cat, 0),
            label=labels.get(cat, ""),
        )
        for cat in IssueCategory
    ]

    summary = _generate_summary(overall, all_issues, page_count=len(site.pages))

    return SeoScorecard(
        overall_score=round(overall, 1),
        category_scores=category_scores,
        issues=all_issues,
        summary_sv=summary,
    )


# ---------------------------------------------------------------------------
# On-page scoring (30%)
# ---------------------------------------------------------------------------


def _score_on_page(page: PageSeoData) -> tuple[float, list[SeoIssue]]:
    score = 0.0
    max_score = 100.0
    issues: list[SeoIssue] = []

    # Title present (15 pts)
    if page.title:
        score += 15
    else:
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.HIGH,
            title="Saknar title-tagg",
            description="Sidan har ingen title-tagg, vilket är en av de viktigaste on-page SEO-faktorerna.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till en unik, beskrivande title-tagg (50-60 tecken) som innehåller sidans huvudsökord.",
            impact_estimate="Sidor utan title-tagg syns ofta inte korrekt i sökresultat — kan påverka ranking kraftigt.",
            effort="low",
        ))

    # Title length (10 pts)
    if page.title:
        if 50 <= page.title_length <= 60:
            score += 10
        elif 30 <= page.title_length < 50 or 60 < page.title_length <= 70:
            score += 5
            issues.append(SeoIssue(
                category=IssueCategory.ON_PAGE,
                severity=IssueSeverity.MEDIUM,
                title=f"Title-tagg har {'för få' if page.title_length < 50 else 'för många'} tecken ({page.title_length})",
                description=f"Optimalt är 50-60 tecken. Nuvarande längd: {page.title_length} tecken.",
                affected_urls=[page.url],
                fix_suggestion=f"Justera title-taggen till 50-60 tecken. Nuvarande: \"{page.title[:70]}\"",
                impact_estimate="En optimerad title-tagg kan förbättra CTR i sökresultaten med 5-15%.",
                effort="low",
            ))
        else:
            issues.append(SeoIssue(
                category=IssueCategory.ON_PAGE,
                severity=IssueSeverity.MEDIUM,
                title=f"Title-tagg har {'för få' if page.title_length < 30 else 'för många'} tecken ({page.title_length})",
                description=f"Optimalt är 50-60 tecken. Nuvarande längd: {page.title_length} tecken.",
                affected_urls=[page.url],
                fix_suggestion=f"Skriv om title-taggen till 50-60 tecken med huvudsökord och företagsnamn.",
                impact_estimate="En optimerad title-tagg kan förbättra CTR i sökresultaten med 5-15%.",
                effort="low",
            ))

    # Meta description present (15 pts)
    if page.meta_description:
        score += 15
    else:
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.HIGH,
            title="Saknar meta-beskrivning",
            description="Sidan har ingen meta-beskrivning. Google visar då ett automatiskt utdrag som ofta inte är optimalt.",
            affected_urls=[page.url],
            fix_suggestion="Skriv en unik meta-beskrivning (120-160 tecken) med huvudsökord och en tydlig CTA.",
            impact_estimate="Uppskattat +15-25% CTR i Googles sökresultat med en optimerad meta-beskrivning.",
            effort="low",
        ))

    # Meta description length (10 pts)
    if page.meta_description:
        if 120 <= page.meta_description_length <= 160:
            score += 10
        elif 50 <= page.meta_description_length < 120 or 160 < page.meta_description_length <= 200:
            score += 5
            issues.append(SeoIssue(
                category=IssueCategory.ON_PAGE,
                severity=IssueSeverity.MEDIUM,
                title=f"Meta-beskrivning har {'för få' if page.meta_description_length < 120 else 'för många'} tecken ({page.meta_description_length})",
                description=f"Optimalt är 120-160 tecken. Nuvarande: {page.meta_description_length} tecken.",
                affected_urls=[page.url],
                fix_suggestion="Justera meta-beskrivningen till 120-160 tecken.",
                impact_estimate="Korrekt längd säkerställer att hela beskrivningen syns i sökresultaten.",
                effort="low",
            ))

    # H1 present and unique (15 pts)
    if page.h1_count == 1:
        score += 15
    elif page.h1_count == 0:
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.HIGH,
            title="Saknar H1-tagg",
            description="Sidan har ingen H1-rubrik, vilket försvårar Googles förståelse av sidans huvudämne.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till en unik H1-tagg som innehåller sidans huvudsökord.",
            impact_estimate="Hjälper Google förstå sidans ämne, förbättrar relevansranking.",
            effort="low",
        ))
    else:
        score += 5
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.MEDIUM,
            title=f"Flera H1-taggar ({page.h1_count} st)",
            description=f"Sidan har {page.h1_count} H1-taggar. Det bör bara finnas en H1 per sida.",
            affected_urls=[page.url],
            fix_suggestion="Behåll bara en H1-tagg och ändra övriga till H2 eller H3.",
            impact_estimate="En enda H1 ger Google en tydligare signal om sidans huvudämne.",
            effort="low",
        ))

    # Heading hierarchy (10 pts)
    if page.heading_hierarchy_valid:
        score += 10
    else:
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.MEDIUM,
            title="Bruten rubrikhierarki",
            description="Rubriknivåer hoppas över (t.ex. H1 → H3 utan H2).",
            affected_urls=[page.url],
            fix_suggestion="Strukturera rubrikerna hierarkiskt: H1 → H2 → H3 utan att hoppa över nivåer.",
            impact_estimate="Korrekt rubrikstruktur förbättrar tillgänglighet och SEO-signaler.",
            effort="low",
        ))

    # Canonical tag (10 pts)
    if page.canonical_url:
        score += 10
    else:
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.MEDIUM,
            title="Saknar canonical-tagg",
            description="Ingen canonical-tagg hittades. Detta kan leda till problem med duplicerat innehåll.",
            affected_urls=[page.url],
            fix_suggestion=f"Lägg till <link rel=\"canonical\" href=\"{page.url}\"> i sidans <head>.",
            impact_estimate="Förhindrar att Google indexerar duplicerade versioner av sidan.",
            effort="low",
        ))

    # Open Graph tags (10 pts)
    og_names = {m.name for m in page.open_graph}
    has_og_basics = "og:title" in og_names and "og:description" in og_names
    if has_og_basics:
        score += 10
    elif page.open_graph:
        score += 5
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.LOW,
            title="Ofullständiga Open Graph-taggar",
            description="Sidan har några OG-taggar men saknar og:title eller og:description.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till minst og:title, og:description och og:image.",
            impact_estimate="Förbättrar utseendet vid delning på sociala medier.",
            effort="low",
        ))
    else:
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.LOW,
            title="Saknar Open Graph-taggar",
            description="Inga Open Graph-taggar hittades.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till og:title, og:description, og:image och og:url.",
            impact_estimate="Förbättrar utseendet vid delning på sociala medier.",
            effort="low",
        ))

    # Twitter Card (5 pts)
    if page.twitter_card:
        score += 5
    else:
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.LOW,
            title="Saknar Twitter Card-taggar",
            description="Inga Twitter Card-taggar hittades.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till twitter:card, twitter:title, twitter:description och twitter:image.",
            impact_estimate="Förbättrar delningsutseende på Twitter/X.",
            effort="low",
        ))

    return score, issues


# ---------------------------------------------------------------------------
# Technical scoring (25%)
# ---------------------------------------------------------------------------


def _score_technical(
    page: PageSeoData, lighthouse: LighthouseResult | None
) -> tuple[float, list[SeoIssue]]:
    issues: list[SeoIssue] = []

    # Define checks with points — CWV checks are conditional on Lighthouse
    has_lh = lighthouse is not None and lighthouse.performance_score is not None
    cwv = lighthouse.core_web_vitals if has_lh and lighthouse else None

    # Base checks (always available)
    base_max = 65  # status(15) + redirects(10) + HTTPS(15) + render-blocking(10) + robots(15)
    base_score = 0.0

    # Status code (15 pts of base)
    if page.status_code == 200:
        base_score += 15
    else:
        issues.append(SeoIssue(
            category=IssueCategory.TECHNICAL,
            severity=IssueSeverity.HIGH,
            title=f"Sidan returnerar statuskod {page.status_code}",
            description=f"HTTP-statuskod {page.status_code} istället för förväntad 200.",
            affected_urls=[page.url],
            fix_suggestion="Åtgärda serverns svar så att sidan returnerar statuskod 200.",
            impact_estimate="Sidor med felstatuskoder indexeras inte korrekt av sökmotorer.",
            effort="medium",
        ))

    # Redirect chain (10 pts of base)
    if len(page.redirect_chain) <= 1:
        base_score += 10
    else:
        issues.append(SeoIssue(
            category=IssueCategory.TECHNICAL,
            severity=IssueSeverity.MEDIUM,
            title=f"Omdirigeringskedja ({len(page.redirect_chain)} steg)",
            description=f"Sidan omdirigeras {len(page.redirect_chain)} gånger innan den når slutdestinationen.",
            affected_urls=[page.url],
            fix_suggestion="Förkorta omdirigeringskedjan till max 1 omdirigering.",
            impact_estimate="Minskar laddningstid och bevarar mer länkvärde (link equity).",
            effort="medium",
        ))

    # HTTPS (15 pts of base)
    if page.url.startswith("https://"):
        base_score += 15
    else:
        issues.append(SeoIssue(
            category=IssueCategory.TECHNICAL,
            severity=IssueSeverity.HIGH,
            title="Sidan använder inte HTTPS",
            description="Sidan serveras över HTTP istället för HTTPS.",
            affected_urls=[page.url],
            fix_suggestion="Installera SSL-certifikat och omdirigera all HTTP-trafik till HTTPS.",
            impact_estimate="HTTPS är en Google-rankingfaktor. Utan HTTPS visas säkerhetsvarningar i webbläsaren.",
            effort="medium",
        ))

    # Render-blocking resources (10 pts of base)
    blocking_count = len(page.render_blocking_resources)
    if blocking_count <= 2:
        base_score += 10
    elif blocking_count <= 5:
        base_score += 5
        issues.append(SeoIssue(
            category=IssueCategory.TECHNICAL,
            severity=IssueSeverity.LOW,
            title=f"{blocking_count} resurser blockerar rendering",
            description=f"{blocking_count} CSS/JS-filer blockerar initial rendering av sidan.",
            affected_urls=[page.url],
            fix_suggestion="Flytta icke-kritisk CSS till async-laddning och lägg till defer på JS.",
            impact_estimate="Kan förbättra First Contentful Paint med 200-500ms.",
            effort="medium",
        ))
    else:
        issues.append(SeoIssue(
            category=IssueCategory.TECHNICAL,
            severity=IssueSeverity.MEDIUM,
            title=f"{blocking_count} resurser blockerar rendering",
            description=f"{blocking_count} CSS/JS-filer blockerar initial rendering.",
            affected_urls=[page.url],
            fix_suggestion="Inline kritisk CSS, lazy-load resten och defer alla JS-filer.",
            impact_estimate="Kan förbättra FCP med 500ms-2s beroende på filstorlek.",
            effort="high",
        ))

    # Robots meta allows indexing (15 pts of base)
    robots_lower = page.robots_meta.lower()
    if "noindex" in robots_lower:
        issues.append(SeoIssue(
            category=IssueCategory.TECHNICAL,
            severity=IssueSeverity.HIGH,
            title="Sidan blockerar indexering (noindex)",
            description="Robots meta-taggen innehåller 'noindex' — sidan kommer inte att visas i sökresultat.",
            affected_urls=[page.url],
            fix_suggestion="Ta bort 'noindex' från robots meta-taggen om sidan ska indexeras.",
            impact_estimate="Sidan är osynlig i sökresultat tills noindex tas bort.",
            effort="low",
        ))
    else:
        base_score += 15

    if not has_lh:
        # No Lighthouse — scale base score to 100
        score = (base_score / base_max) * 100 if base_max > 0 else 0
        return round(score, 1), issues

    # CWV checks (35 pts when Lighthouse available)
    cwv_max = 35
    cwv_score = 0.0

    # LCP (15 pts of CWV)
    if cwv and cwv.lcp_ms is not None:
        if cwv.lcp_ms <= 2500:
            cwv_score += 15
        elif cwv.lcp_ms <= 4000:
            cwv_score += 8
            issues.append(SeoIssue(
                category=IssueCategory.TECHNICAL,
                severity=IssueSeverity.MEDIUM,
                title=f"LCP behöver förbättras ({cwv.lcp_ms:.0f}ms)",
                description=f"Largest Contentful Paint är {cwv.lcp_ms:.0f}ms. Bör vara under 2500ms.",
                affected_urls=[page.url],
                fix_suggestion="Optimera den största synliga resursen: komprimera bilder, använd CDN, lazy-load bilder under fold.",
                impact_estimate="Google prioriterar sidor med LCP under 2.5s — kan förbättra ranking.",
                effort="medium",
            ))
        else:
            issues.append(SeoIssue(
                category=IssueCategory.TECHNICAL,
                severity=IssueSeverity.HIGH,
                title=f"LCP för hög ({cwv.lcp_ms:.0f}ms)",
                description=f"Largest Contentful Paint är {cwv.lcp_ms:.0f}ms — långt över gränsvärdet 2500ms.",
                affected_urls=[page.url],
                fix_suggestion="Optimera hero-bilden: konvertera till WebP, max 200KB, ange width/height-attribut. Överväg CDN.",
                impact_estimate="Google prioriterar sidor med LCP under 2.5s — en avgörande rankingfaktor.",
                effort="high",
            ))

    # CLS (10 pts of CWV)
    if cwv and cwv.cls is not None:
        if cwv.cls <= 0.1:
            cwv_score += 10
        elif cwv.cls <= 0.25:
            cwv_score += 5
            issues.append(SeoIssue(
                category=IssueCategory.TECHNICAL,
                severity=IssueSeverity.MEDIUM,
                title=f"CLS behöver förbättras ({cwv.cls:.3f})",
                description=f"Cumulative Layout Shift är {cwv.cls:.3f}. Bör vara under 0.1.",
                affected_urls=[page.url],
                fix_suggestion="Ange width/height på bilder och videor. Undvik att infoga innehåll ovanför befintligt.",
                impact_estimate="Bättre CLS förbättrar användarupplevelsen och kan stärka rankingen.",
                effort="medium",
            ))
        else:
            issues.append(SeoIssue(
                category=IssueCategory.TECHNICAL,
                severity=IssueSeverity.HIGH,
                title=f"CLS för högt ({cwv.cls:.3f})",
                description=f"CLS är {cwv.cls:.3f} — långt över gränsvärdet 0.1.",
                affected_urls=[page.url],
                fix_suggestion="Reservera utrymme för alla bilder, annonser och dynamiskt innehåll. Använd CSS aspect-ratio.",
                impact_estimate="Högt CLS leder till dålig användarupplevelse och lägre ranking.",
                effort="high",
            ))

    # TBT (10 pts of CWV — proxy for FID)
    if cwv and cwv.tbt_ms is not None:
        if cwv.tbt_ms <= 200:
            cwv_score += 10
        elif cwv.tbt_ms <= 600:
            cwv_score += 5
            issues.append(SeoIssue(
                category=IssueCategory.TECHNICAL,
                severity=IssueSeverity.MEDIUM,
                title=f"Total Blocking Time behöver förbättras ({cwv.tbt_ms:.0f}ms)",
                description=f"TBT är {cwv.tbt_ms:.0f}ms. Bör vara under 200ms.",
                affected_urls=[page.url],
                fix_suggestion="Dela upp långa JavaScript-tasks, använd code splitting och lazy loading.",
                impact_estimate="Lägre TBT ger snabbare interaktivitet och bättre användarupplevelse.",
                effort="high",
            ))
        else:
            issues.append(SeoIssue(
                category=IssueCategory.TECHNICAL,
                severity=IssueSeverity.HIGH,
                title=f"Total Blocking Time för hög ({cwv.tbt_ms:.0f}ms)",
                description=f"TBT är {cwv.tbt_ms:.0f}ms — långt över gränsvärdet 200ms.",
                affected_urls=[page.url],
                fix_suggestion="Reducera JavaScript-bundles, ta bort oanvänd JS, använd web workers för tung bearbetning.",
                impact_estimate="Hög TBT gör sidan trög och skadar ranking i Google.",
                effort="high",
            ))

    # TTFB (informational — not scored, but generates issue if slow)
    if cwv and cwv.ttfb_ms is not None:
        if cwv.ttfb_ms > 1800:
            issues.append(SeoIssue(
                category=IssueCategory.TECHNICAL,
                severity=IssueSeverity.MEDIUM,
                title=f"TTFB behöver förbättras ({cwv.ttfb_ms:.0f}ms)",
                description=f"Time to First Byte är {cwv.ttfb_ms:.0f}ms. Bör vara under 800ms.",
                affected_urls=[page.url],
                fix_suggestion="Optimera server-svartider: caching, CDN, databasoptimering.",
                impact_estimate="Snabbare TTFB förbättrar alla efterföljande laddningsmått.",
                effort="high",
            ))

    # Combine base + CWV
    total_max = base_max + cwv_max
    score = ((base_score + cwv_score) / total_max) * 100

    return round(score, 1), issues


# ---------------------------------------------------------------------------
# Content scoring (20%)
# ---------------------------------------------------------------------------


def _score_content(page: PageSeoData) -> tuple[float, list[SeoIssue]]:
    score = 0.0
    issues: list[SeoIssue] = []

    # Word count (70 pts total: 40 base + 20 good + 10 excellent)
    wc = page.word_count
    if wc >= 1500:
        score += 70
    elif wc >= 800:
        score += 60
    elif wc >= 300:
        score += 40
    elif wc >= 100:
        score += 20
        issues.append(SeoIssue(
            category=IssueCategory.CONTENT,
            severity=IssueSeverity.MEDIUM,
            title=f"Tunt innehåll ({wc} ord)",
            description=f"Sidan har {wc} ord. Minst 300 ord rekommenderas för att ge sökmotorer tillräckligt med kontext.",
            affected_urls=[page.url],
            fix_suggestion="Utöka innehållet till minst 300 ord med relevant, unik text som besvarar användarens sökintention.",
            impact_estimate="Sidor med mer innehåll rankar ofta bättre för relevanta sökfrågor.",
            effort="medium",
        ))
    else:
        issues.append(SeoIssue(
            category=IssueCategory.CONTENT,
            severity=IssueSeverity.HIGH,
            title=f"Mycket tunt innehåll ({wc} ord)",
            description=f"Sidan har bara {wc} ord — för lite för att Google ska förstå sidans ämne.",
            affected_urls=[page.url],
            fix_suggestion="Skriv substantiellt innehåll (minst 300 ord) som adresserar sökarens frågor och behov.",
            impact_estimate="Sidor med under 100 ord har mycket svårt att ranka i sökresultat.",
            effort="medium",
        ))

    # Images present (15 pts)
    if page.images:
        score += 15
    else:
        issues.append(SeoIssue(
            category=IssueCategory.CONTENT,
            severity=IssueSeverity.LOW,
            title="Sidan saknar bilder",
            description="Inga bilder hittades på sidan.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till relevanta bilder med beskrivande alt-text.",
            impact_estimate="Bilder förbättrar användarengagemang och kan driva trafik via Google Bildresultat.",
            effort="medium",
        ))

    # Image alt text (15 pts)
    if page.images:
        total_images = len(page.images)
        without_alt = page.images_without_alt
        if without_alt == 0:
            score += 15
        elif without_alt <= total_images * 0.3:
            score += 10
            issues.append(SeoIssue(
                category=IssueCategory.CONTENT,
                severity=IssueSeverity.LOW,
                title=f"{without_alt} bild{'er' if without_alt > 1 else ''} saknar alt-text",
                description=f"{without_alt} av {total_images} bilder saknar alt-attribut.",
                affected_urls=[page.url],
                fix_suggestion="Lägg till beskrivande alt-text med relevanta sökord för varje bild.",
                impact_estimate="Förbättrar tillgänglighet och bildsökning.",
                effort="low",
            ))
        else:
            issues.append(SeoIssue(
                category=IssueCategory.CONTENT,
                severity=IssueSeverity.MEDIUM,
                title=f"{without_alt} bilder saknar alt-text",
                description=f"{without_alt} av {total_images} bilder saknar alt-attribut — en stor andel.",
                affected_urls=[page.url],
                fix_suggestion="Lägg till beskrivande alt-text för alla bilder. Inkludera relevanta sökord.",
                impact_estimate="Förbättrar tillgänglighet, bildsökning och on-page SEO-signaler.",
                effort="low",
            ))

    return score, issues


# ---------------------------------------------------------------------------
# Links scoring (15%)
# ---------------------------------------------------------------------------


def _score_links(
    page: PageSeoData, site: SiteSeoData | None = None
) -> tuple[float, list[SeoIssue]]:
    score = 0.0
    issues: list[SeoIssue] = []

    internal_count = len(page.internal_links)
    external_count = len(page.external_links)

    # Internal links present (30 pts)
    if internal_count >= 5:
        score += 30
    elif internal_count >= 3:
        score += 25
    elif internal_count >= 1:
        score += 15
        issues.append(SeoIssue(
            category=IssueCategory.LINKS,
            severity=IssueSeverity.MEDIUM,
            title=f"För få interna länkar ({internal_count})",
            description=f"Sidan har bara {internal_count} intern(a) länk(ar). Minst 3 rekommenderas.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till fler interna länkar till relevanta sidor på webbplatsen.",
            impact_estimate="Fler interna länkar hjälper Google förstå sidstrukturen och sprida länkvärde.",
            effort="low",
        ))
    else:
        issues.append(SeoIssue(
            category=IssueCategory.LINKS,
            severity=IssueSeverity.HIGH,
            title="Inga interna länkar",
            description="Sidan har inga interna länkar till andra sidor på webbplatsen.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till minst 3-5 interna länkar till relevanta undersidor.",
            impact_estimate="Interna länkar är avgörande för Googles crawlning och sidstruktur.",
            effort="low",
        ))

    # Internal links adequate bonus (20 pts)
    if internal_count >= 5:
        score += 20

    # External links (15 pts)
    if external_count >= 1:
        score += 15
    else:
        issues.append(SeoIssue(
            category=IssueCategory.LINKS,
            severity=IssueSeverity.LOW,
            title="Inga externa länkar",
            description="Sidan har inga utgående länkar till externa webbplatser.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till relevanta externa länkar till auktoritativa källor.",
            impact_estimate="Externa länkar till trovärdiga källor kan stärka sidans trovärdighet.",
            effort="low",
        ))

    # Broken links placeholder (20 pts — always awarded since we don't check live status)
    score += 20

    # Orphan page check (15 pts — only in site mode)
    if site:
        all_linked: set[str] = set()
        for p in site.pages:
            for link in p.internal_links:
                all_linked.add(link.url.rstrip("/"))
        if page.url.rstrip("/") in all_linked or page.url == (site.pages[0].url if site.pages else ""):
            score += 15
        else:
            issues.append(SeoIssue(
                category=IssueCategory.LINKS,
                severity=IssueSeverity.MEDIUM,
                title="Föräldralös sida",
                description="Sidan länkas inte från någon annan sida på webbplatsen.",
                affected_urls=[page.url],
                fix_suggestion="Lägg till navigeringslänkar eller kontextuella länkar till denna sida från andra sidor.",
                impact_estimate="Föräldralösa sidor kan missas vid crawlning och tappar intern länkvärde.",
                effort="low",
            ))
    else:
        score += 15  # Award in single-page mode (can't check)

    return score, issues


# ---------------------------------------------------------------------------
# Schema scoring (10%)
# ---------------------------------------------------------------------------


def _score_schema(page: PageSeoData) -> tuple[float, list[SeoIssue]]:
    score = 0.0
    issues: list[SeoIssue] = []

    # JSON-LD present (40 pts)
    json_ld_schemas = [s for s in page.schema_markup if s.format == "json-ld"]
    if json_ld_schemas:
        score += 40
    else:
        issues.append(SeoIssue(
            category=IssueCategory.SCHEMA,
            severity=IssueSeverity.MEDIUM,
            title="Saknar schema markup (JSON-LD)",
            description="Ingen JSON-LD strukturerad data hittades på sidan.",
            affected_urls=[page.url],
            fix_suggestion="Lägg till relevant JSON-LD schema: LocalBusiness för lokala företag, Product för produktsidor, FAQPage för FAQ-sidor.",
            impact_estimate="Möjliggör rich snippets i sökresultaten, uppskattat +20-30% synlighet i SERP.",
            effort="medium",
        ))

    # Schema type appropriate (30 pts)
    if json_ld_schemas:
        known_types = {"LocalBusiness", "Organization", "Product", "Service",
                       "FAQPage", "Article", "BlogPosting", "WebPage",
                       "BreadcrumbList", "WebSite"}
        has_known = any(s.schema_type in known_types for s in json_ld_schemas)
        if has_known:
            score += 30
        else:
            score += 15
            issues.append(SeoIssue(
                category=IssueCategory.SCHEMA,
                severity=IssueSeverity.LOW,
                title="Schema-typ kan förbättras",
                description=f"Hittade schema av typ: {', '.join(s.schema_type for s in json_ld_schemas)}. Överväg mer specifika typer.",
                affected_urls=[page.url],
                fix_suggestion="Använd specifika schema-typer som LocalBusiness, Product eller FAQPage.",
                impact_estimate="Mer specifika schema-typer ger rikare visning i sökresultaten.",
                effort="low",
            ))

    # Required fields present (30 pts)
    if json_ld_schemas:
        has_name = any("name" in s.raw_data for s in json_ld_schemas)
        if has_name:
            score += 30
        else:
            score += 15
            issues.append(SeoIssue(
                category=IssueCategory.SCHEMA,
                severity=IssueSeverity.LOW,
                title="Schema saknar obligatoriska fält",
                description="JSON-LD-schemat saknar grundläggande fält som 'name'.",
                affected_urls=[page.url],
                fix_suggestion="Lägg till obligatoriska fält: name, description, url. För LocalBusiness: address, telephone.",
                impact_estimate="Komplett schema ökar chansen att Google visar rich snippets.",
                effort="low",
            ))

    return score, issues


# ---------------------------------------------------------------------------
# Site-level issue detection
# ---------------------------------------------------------------------------


def _detect_site_level_issues(site: SiteSeoData) -> list[SeoIssue]:
    """Detect issues visible only at site level."""
    issues: list[SeoIssue] = []

    # Duplicate titles
    titles = [p.title for p in site.pages if p.title]
    title_counts: dict[str, list[str]] = {}
    for p in site.pages:
        if p.title:
            title_counts.setdefault(p.title, []).append(p.url)
    duplicates = {t: urls for t, urls in title_counts.items() if len(urls) > 1}
    if duplicates:
        dup_count = sum(len(urls) for urls in duplicates.values())
        all_urls = [url for urls in duplicates.values() for url in urls]
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.MEDIUM,
            title=f"Duplicerade title-taggar ({dup_count} sidor)",
            description=f"{len(duplicates)} title-taggar återanvänds på flera sidor.",
            affected_urls=all_urls[:10],
            fix_suggestion="Skriv unika, beskrivande titlar (50-60 tecken) för varje sida.",
            impact_estimate="Undviker kannibalisering, förbättrar CTR för varje sida.",
            effort="medium",
        ))

    # Duplicate meta descriptions
    meta_counts: dict[str, list[str]] = {}
    for p in site.pages:
        if p.meta_description:
            meta_counts.setdefault(p.meta_description, []).append(p.url)
    dup_metas = {m: urls for m, urls in meta_counts.items() if len(urls) > 1}
    if dup_metas:
        dup_meta_count = sum(len(urls) for urls in dup_metas.values())
        all_meta_urls = [url for urls in dup_metas.values() for url in urls]
        issues.append(SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.MEDIUM,
            title=f"Duplicerade meta-beskrivningar ({dup_meta_count} sidor)",
            description=f"{len(dup_metas)} meta-beskrivningar återanvänds på flera sidor.",
            affected_urls=all_meta_urls[:10],
            fix_suggestion="Skriv unika meta-beskrivningar (120-160 tecken) för varje sida.",
            impact_estimate="Unika meta-beskrivningar förbättrar CTR för varje sida i sökresultaten.",
            effort="medium",
        ))

    # Orphan pages
    if site.orphan_pages:
        issues.append(SeoIssue(
            category=IssueCategory.LINKS,
            severity=IssueSeverity.MEDIUM,
            title=f"Föräldralösa sidor ({len(site.orphan_pages)} st)",
            description=f"{len(site.orphan_pages)} sidor länkas inte från någon annan sida på webbplatsen.",
            affected_urls=site.orphan_pages[:10],
            fix_suggestion="Lägg till interna länkar till dessa sidor från relevanta navigeringselement eller innehåll.",
            impact_estimate="Föräldralösa sidor missas ofta vid Googles crawlning och tappar intern länkvärde.",
            effort="low",
        ))

    # Missing robots.txt
    if not site.robots_txt.exists:
        issues.append(SeoIssue(
            category=IssueCategory.TECHNICAL,
            severity=IssueSeverity.LOW,
            title="Saknar robots.txt",
            description="Ingen robots.txt-fil hittades på webbplatsen.",
            affected_urls=[f"https://{site.domain}/robots.txt"],
            fix_suggestion="Skapa en robots.txt-fil som tillåter crawlning och anger sitemap-URL.",
            impact_estimate="Förbättrar crawlningseffektivitet och ger sökmotorer information om sidstrukturen.",
            effort="low",
        ))

    # robots.txt blocks crawling
    if site.robots_txt.exists and not site.robots_txt.allows_crawling:
        issues.append(SeoIssue(
            category=IssueCategory.TECHNICAL,
            severity=IssueSeverity.HIGH,
            title="robots.txt blockerar crawlning",
            description="robots.txt blockerar sökmotorer från att crawla webbplatsen.",
            affected_urls=[f"https://{site.domain}/robots.txt"],
            fix_suggestion="Uppdatera robots.txt för att tillåta crawlning: ta bort 'Disallow: /' under User-agent: *.",
            impact_estimate="Webbplatsen kan inte indexeras alls i nuvarande konfiguration.",
            effort="low",
        ))

    # Missing sitemap
    if not site.sitemaps or not any(s.exists for s in site.sitemaps):
        issues.append(SeoIssue(
            category=IssueCategory.TECHNICAL,
            severity=IssueSeverity.MEDIUM,
            title="Saknar sitemap.xml",
            description="Ingen sitemap.xml hittades.",
            affected_urls=[f"https://{site.domain}/sitemap.xml"],
            fix_suggestion="Skapa en sitemap.xml med alla indexerbara URL:er och skicka den via Google Search Console.",
            impact_estimate="Förbättrar crawlningseffektivitet, snabbare indexering av nya sidor.",
            effort="low",
        ))

    return issues


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------


def _generate_summary(
    overall: float, issues: list[SeoIssue], page_count: int | None = None
) -> str:
    """Generate a 2-3 sentence Swedish summary of findings."""
    high_count = sum(1 for i in issues if i.severity == IssueSeverity.HIGH)
    medium_count = sum(1 for i in issues if i.severity == IssueSeverity.MEDIUM)
    total = len(issues)

    grade = _score_to_grade(overall)

    parts = []
    if page_count:
        parts.append(f"Webbplatsen fick betyg {grade} ({overall:.0f}/100) baserat på analys av {page_count} sidor.")
    else:
        parts.append(f"Sidan fick betyg {grade} ({overall:.0f}/100) i SEO-analysen.")

    if high_count > 0:
        parts.append(f"{high_count} kritisk{'a' if high_count > 1 else 't'} problem hittades som bör åtgärdas omgående.")
    elif medium_count > 0:
        parts.append(f"{medium_count} förbättringsområde{'n' if medium_count > 1 else ''} identifierades.")
    else:
        parts.append("Inga allvarliga problem hittades.")

    if total > 0:
        parts.append(f"Totalt {total} förbättringsförslag med specifika åtgärder och uppskattad effekt.")

    return " ".join(parts)


def _score_to_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    elif score >= 50:
        return "E"
    return "F"
