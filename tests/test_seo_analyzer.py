"""Tests for SEO scoring engine."""

import pytest

from src.analysis.seo_analyzer import (
    _score_on_page,
    _score_technical,
    _score_content,
    _score_links,
    _score_schema,
    _score_to_grade,
    _detect_site_level_issues,
    analyze_page_seo,
    analyze_site_seo,
)
from src.models.seo import (
    CoreWebVitals,
    ImageAudit,
    IssueCategory,
    IssueSeverity,
    LighthouseResult,
    LinkInfo,
    MetaTag,
    PageSeoData,
    RobotsTxtData,
    SchemaMarkup,
    SiteSeoData,
)
from src.scrapers.seo_scraper import generate_synthetic_page_data, generate_synthetic_site_data


def _make_good_page() -> PageSeoData:
    """Create a page with near-perfect SEO data."""
    return PageSeoData(
        url="https://example.se",
        status_code=200,
        title="Tandvård Stockholm — Kvalificerad Tandläkare",
        title_length=47,
        meta_description="Vi erbjuder professionell tandvård i centrala Stockholm. Boka tid för konsultation redan idag hos erfarna tandläkare.",
        meta_description_length=113,
        canonical_url="https://example.se",
        is_self_canonical=True,
        h1="Tandvård i Stockholm",
        h1_count=1,
        headings=[
            {"tag": "h1", "text": "Tandvård i Stockholm"},
            {"tag": "h2", "text": "Våra tjänster"},
            {"tag": "h3", "text": "Tandblekning"},
        ],
        heading_hierarchy_valid=True,
        body_text="word " * 1000,
        word_count=1000,
        images=[
            ImageAudit(src="/img1.jpg", alt="Tandläkare", has_alt=True),
            ImageAudit(src="/img2.jpg", alt="Klinik", has_alt=True),
        ],
        images_without_alt=0,
        internal_links=[
            LinkInfo(url="https://example.se/about"),
            LinkInfo(url="https://example.se/services"),
            LinkInfo(url="https://example.se/contact"),
            LinkInfo(url="https://example.se/prices"),
            LinkInfo(url="https://example.se/blog"),
        ],
        external_links=[LinkInfo(url="https://1177.se", is_external=True)],
        schema_markup=[
            SchemaMarkup(
                schema_type="LocalBusiness",
                format="json-ld",
                raw_data={"@type": "LocalBusiness", "name": "Example Tandvård"},
            )
        ],
        open_graph=[
            MetaTag(name="og:title", content="Tandvård Stockholm"),
            MetaTag(name="og:description", content="Professionell tandvård"),
        ],
        twitter_card=[MetaTag(name="twitter:card", content="summary")],
    )


def _make_bad_page() -> PageSeoData:
    """Create a page with many SEO issues."""
    return PageSeoData(
        url="http://example.se",
        status_code=200,
        title="",
        title_length=0,
        meta_description="",
        meta_description_length=0,
        h1="",
        h1_count=0,
        headings=[],
        heading_hierarchy_valid=False,
        body_text="Short.",
        word_count=1,
        images=[],
        images_without_alt=0,
        internal_links=[],
        external_links=[],
        schema_markup=[],
        open_graph=[],
        twitter_card=[],
    )


class TestScoreToGrade:
    def test_grades(self):
        assert _score_to_grade(95) == "A"
        assert _score_to_grade(85) == "B"
        assert _score_to_grade(75) == "C"
        assert _score_to_grade(65) == "D"
        assert _score_to_grade(55) == "E"
        assert _score_to_grade(30) == "F"


class TestOnPageScoring:
    def test_good_page_high_score(self):
        page = _make_good_page()
        score, issues = _score_on_page(page)
        assert score >= 80
        assert len(issues) <= 2  # May have minor issues like meta desc length

    def test_bad_page_low_score(self):
        page = _make_bad_page()
        score, issues = _score_on_page(page)
        assert score < 20
        high_issues = [i for i in issues if i.severity == IssueSeverity.HIGH]
        assert len(high_issues) >= 2  # Missing title, H1, meta desc

    def test_missing_title_is_high_severity(self):
        page = PageSeoData(url="https://example.se", title="", title_length=0)
        _, issues = _score_on_page(page)
        title_issues = [i for i in issues if "title" in i.title.lower()]
        assert any(i.severity == IssueSeverity.HIGH for i in title_issues)

    def test_missing_h1_is_high_severity(self):
        page = PageSeoData(url="https://example.se", h1_count=0)
        _, issues = _score_on_page(page)
        h1_issues = [i for i in issues if "H1" in i.title]
        assert len(h1_issues) == 1
        assert h1_issues[0].severity == IssueSeverity.HIGH

    def test_multiple_h1_is_medium(self):
        page = PageSeoData(url="https://example.se", h1="Test", h1_count=3)
        _, issues = _score_on_page(page)
        h1_issues = [i for i in issues if "H1" in i.title]
        assert h1_issues[0].severity == IssueSeverity.MEDIUM

    def test_issues_have_swedish_text(self):
        page = _make_bad_page()
        _, issues = _score_on_page(page)
        for issue in issues:
            assert issue.title  # Non-empty
            assert issue.fix_suggestion  # Non-empty
            assert issue.impact_estimate  # Non-empty
            assert issue.category == IssueCategory.ON_PAGE

    def test_issues_have_affected_urls(self):
        page = _make_bad_page()
        _, issues = _score_on_page(page)
        for issue in issues:
            assert page.url in issue.affected_urls


class TestTechnicalScoring:
    def test_https_page_gets_points(self):
        page = PageSeoData(url="https://example.se", status_code=200)
        score, issues = _score_technical(page, None)
        assert score > 0
        https_issues = [i for i in issues if "HTTPS" in i.title]
        assert len(https_issues) == 0

    def test_http_page_gets_issue(self):
        page = PageSeoData(url="http://example.se", status_code=200)
        _, issues = _score_technical(page, None)
        https_issues = [i for i in issues if "HTTPS" in i.title]
        assert len(https_issues) == 1
        assert https_issues[0].severity == IssueSeverity.HIGH

    def test_noindex_detected(self):
        page = PageSeoData(url="https://example.se", robots_meta="noindex, follow")
        _, issues = _score_technical(page, None)
        noindex_issues = [i for i in issues if "noindex" in i.title.lower()]
        assert len(noindex_issues) == 1

    def test_without_lighthouse_scales_to_100(self):
        page = PageSeoData(url="https://example.se", status_code=200)
        score, _ = _score_technical(page, None)
        # Should be scaled — HTTPS(15) + status(15) + no-redirect(10) + render(10) = 50/50 = 100
        assert score == 100.0

    def test_with_good_lighthouse(self):
        page = PageSeoData(url="https://example.se", status_code=200)
        lh = LighthouseResult(
            url="https://example.se",
            performance_score=90,
            core_web_vitals=CoreWebVitals(lcp_ms=1500, cls=0.05, tbt_ms=100, ttfb_ms=500),
        )
        score, issues = _score_technical(page, lh)
        assert score >= 80

    def test_with_bad_lighthouse(self):
        page = PageSeoData(url="https://example.se", status_code=200)
        lh = LighthouseResult(
            url="https://example.se",
            performance_score=30,
            core_web_vitals=CoreWebVitals(lcp_ms=6000, cls=0.5, tbt_ms=1000, ttfb_ms=3000),
        )
        score, issues = _score_technical(page, lh)
        # Base checks pass (HTTPS, status 200, no redirects, robots OK) but all CWV fail
        assert score < 70
        high_issues = [i for i in issues if i.severity == IssueSeverity.HIGH]
        assert len(high_issues) >= 2


class TestContentScoring:
    def test_good_content(self):
        page = PageSeoData(
            url="https://example.se",
            body_text="word " * 1000,
            word_count=1000,
            images=[ImageAudit(src="/img.jpg", alt="test", has_alt=True)],
            images_without_alt=0,
        )
        score, issues = _score_content(page)
        assert score >= 80
        assert len(issues) == 0

    def test_thin_content(self):
        page = PageSeoData(url="https://example.se", word_count=50, body_text="word " * 50)
        score, issues = _score_content(page)
        content_issues = [i for i in issues if "innehåll" in i.title.lower() or "tunt" in i.title.lower()]
        assert len(content_issues) >= 1

    def test_missing_images(self):
        page = PageSeoData(url="https://example.se", word_count=500, images=[])
        _, issues = _score_content(page)
        img_issues = [i for i in issues if "bild" in i.title.lower()]
        assert len(img_issues) >= 1

    def test_images_without_alt(self):
        page = PageSeoData(
            url="https://example.se",
            word_count=500,
            images=[
                ImageAudit(src="/a.jpg", has_alt=False),
                ImageAudit(src="/b.jpg", has_alt=False),
                ImageAudit(src="/c.jpg", has_alt=True, alt="ok"),
            ],
            images_without_alt=2,
        )
        _, issues = _score_content(page)
        alt_issues = [i for i in issues if "alt" in i.title.lower()]
        assert len(alt_issues) >= 1


class TestLinksScoring:
    def test_good_links(self):
        page = PageSeoData(
            url="https://example.se",
            internal_links=[LinkInfo(url=f"/p{i}") for i in range(6)],
            external_links=[LinkInfo(url="https://other.se", is_external=True)],
        )
        score, issues = _score_links(page)
        assert score >= 80

    def test_no_links(self):
        page = PageSeoData(url="https://example.se")
        score, issues = _score_links(page)
        assert score < 50
        assert any("intern" in i.title.lower() for i in issues)


class TestSchemaScoring:
    def test_no_schema(self):
        page = PageSeoData(url="https://example.se")
        score, issues = _score_schema(page)
        assert score == 0
        assert any("schema" in i.title.lower() for i in issues)

    def test_good_schema(self):
        page = PageSeoData(
            url="https://example.se",
            schema_markup=[
                SchemaMarkup(
                    schema_type="LocalBusiness",
                    format="json-ld",
                    raw_data={"@type": "LocalBusiness", "name": "Test"},
                )
            ],
        )
        score, issues = _score_schema(page)
        assert score == 100
        assert len(issues) == 0


class TestSiteLevelIssues:
    def test_duplicate_titles(self):
        site = generate_synthetic_site_data("https://example.se")
        # Make two pages have the same title
        if len(site.pages) >= 2:
            site.pages[1].title = site.pages[0].title
        issues = _detect_site_level_issues(site)
        dup_issues = [i for i in issues if "Duplicerade title" in i.title]
        assert len(dup_issues) >= 1

    def test_orphan_pages_detected(self):
        site = generate_synthetic_site_data("https://example.se")
        assert len(site.orphan_pages) >= 1
        issues = _detect_site_level_issues(site)
        orphan_issues = [i for i in issues if "Föräldralösa" in i.title]
        assert len(orphan_issues) >= 1

    def test_missing_robots_txt(self):
        site = generate_synthetic_site_data("https://example.se")
        site.robots_txt.exists = False
        issues = _detect_site_level_issues(site)
        robots_issues = [i for i in issues if "robots" in i.title.lower()]
        assert len(robots_issues) >= 1


class TestAnalyzePageSeo:
    def test_good_page_scores_high(self):
        page = _make_good_page()
        scorecard = analyze_page_seo(page)
        assert scorecard.overall_score >= 70
        assert len(scorecard.category_scores) == 5
        assert scorecard.summary_sv  # Non-empty

    def test_bad_page_scores_low(self):
        page = _make_bad_page()
        scorecard = analyze_page_seo(page)
        assert scorecard.overall_score < 40
        assert len(scorecard.issues) >= 5

    def test_scores_are_weighted(self):
        page = _make_good_page()
        scorecard = analyze_page_seo(page)
        # Verify weights: overall should be between min and max category scores
        cat_scores = [cs.score for cs in scorecard.category_scores]
        assert scorecard.overall_score >= min(cat_scores) * 0.5
        assert scorecard.overall_score <= max(cat_scores)

    def test_with_lighthouse(self):
        page = _make_good_page()
        lh = LighthouseResult(
            performance_score=85,
            core_web_vitals=CoreWebVitals(lcp_ms=2000, cls=0.05, tbt_ms=150, ttfb_ms=600),
        )
        scorecard = analyze_page_seo(page, lh)
        assert scorecard.overall_score >= 60

    def test_synthetic_data(self):
        page = generate_synthetic_page_data("https://example.se")
        scorecard = analyze_page_seo(page)
        assert 0 <= scorecard.overall_score <= 100
        assert len(scorecard.issues) > 0  # Synthetic data has deliberate issues


class TestAnalyzeSiteSeo:
    def test_synthetic_site(self):
        site = generate_synthetic_site_data("https://example.se")
        scorecard = analyze_site_seo(site)
        assert 0 <= scorecard.overall_score <= 100
        assert len(scorecard.category_scores) == 5
        assert len(scorecard.issues) > 0
        assert scorecard.summary_sv

    def test_empty_site(self):
        from datetime import datetime
        site = SiteSeoData(domain="example.se", crawl_date=datetime.now(), pages=[])
        scorecard = analyze_site_seo(site)
        assert scorecard.overall_score == 0

    def test_deduplicates_issues(self):
        site = generate_synthetic_site_data("https://example.se")
        scorecard = analyze_site_seo(site)
        # No two issues should have the exact same title
        titles = [i.title for i in scorecard.issues]
        assert len(titles) == len(set(titles))

    def test_site_issues_included(self):
        site = generate_synthetic_site_data("https://example.se")
        # Force duplicate titles
        if len(site.pages) >= 2:
            site.pages[1].title = site.pages[0].title
        scorecard = analyze_site_seo(site)
        has_dup_title = any("Duplicerade title" in i.title for i in scorecard.issues)
        assert has_dup_title
