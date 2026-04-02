"""Tests for SEO Pydantic models."""

from datetime import datetime

import pytest

from src.models.seo import (
    CategoryScore,
    CompetitorSeoProfile,
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
    SeoAnalysisResult,
    SeoCompetitorAnalysis,
    SeoGap,
    SeoIssue,
    SeoScorecard,
    SiteSeoData,
    SitemapData,
)


class TestEnums:
    def test_issue_severity_values(self):
        assert IssueSeverity.HIGH == "high"
        assert IssueSeverity.MEDIUM == "medium"
        assert IssueSeverity.LOW == "low"

    def test_issue_category_values(self):
        assert IssueCategory.TECHNICAL == "technical"
        assert IssueCategory.CONTENT == "content"
        assert IssueCategory.ON_PAGE == "on_page"
        assert IssueCategory.LINKS == "links"
        assert IssueCategory.SCHEMA == "schema"


class TestMetaTag:
    def test_basic(self):
        tag = MetaTag(name="og:title", content="Test Page")
        assert tag.name == "og:title"
        assert tag.content == "Test Page"


class TestSchemaMarkup:
    def test_json_ld(self):
        schema = SchemaMarkup(
            schema_type="LocalBusiness",
            format="json-ld",
            raw_data={"@type": "LocalBusiness", "name": "Test"},
        )
        assert schema.schema_type == "LocalBusiness"
        assert schema.format == "json-ld"

    def test_default_raw_data(self):
        schema = SchemaMarkup(schema_type="Product", format="microdata")
        assert schema.raw_data == {}


class TestImageAudit:
    def test_with_alt(self):
        img = ImageAudit(src="/img.jpg", alt="Description", has_alt=True, width=800, height=600)
        assert img.has_alt is True
        assert img.width == 800

    def test_without_alt(self):
        img = ImageAudit(src="/img.jpg")
        assert img.has_alt is False
        assert img.alt == ""
        assert img.width is None


class TestLinkInfo:
    def test_internal_link(self):
        link = LinkInfo(url="https://example.se/about", anchor_text="Om oss")
        assert link.is_external is False
        assert link.is_nofollow is False

    def test_external_nofollow(self):
        link = LinkInfo(url="https://other.se", is_external=True, is_nofollow=True)
        assert link.is_external is True
        assert link.is_nofollow is True


class TestPageSeoData:
    def test_minimal(self):
        page = PageSeoData(url="https://example.se")
        assert page.url == "https://example.se"
        assert page.status_code == 200
        assert page.title == ""
        assert page.word_count == 0
        assert page.images == []
        assert page.schema_markup == []

    def test_full(self):
        page = PageSeoData(
            url="https://example.se",
            status_code=200,
            title="Test Title",
            title_length=10,
            meta_description="A description",
            meta_description_length=13,
            canonical_url="https://example.se",
            h1="Main Heading",
            h1_count=1,
            headings=[{"tag": "h1", "text": "Main Heading"}],
            body_text="Some content here.",
            word_count=3,
            images=[ImageAudit(src="/img.jpg", has_alt=True, alt="test")],
            images_without_alt=0,
            internal_links=[LinkInfo(url="/about")],
            external_links=[LinkInfo(url="https://other.se", is_external=True)],
            schema_markup=[SchemaMarkup(schema_type="LocalBusiness", format="json-ld")],
            open_graph=[MetaTag(name="og:title", content="Test")],
            twitter_card=[MetaTag(name="twitter:card", content="summary")],
        )
        assert page.title_length == 10
        assert len(page.images) == 1
        assert len(page.schema_markup) == 1

    def test_serialization_roundtrip(self):
        page = PageSeoData(url="https://example.se", title="Test")
        json_str = page.model_dump_json()
        restored = PageSeoData.model_validate_json(json_str)
        assert restored.url == page.url
        assert restored.title == page.title


class TestRobotsTxtData:
    def test_defaults(self):
        r = RobotsTxtData()
        assert r.exists is False
        assert r.allows_crawling is True
        assert r.sitemap_urls == []

    def test_blocking(self):
        r = RobotsTxtData(exists=True, allows_crawling=False, disallowed_paths=["/"])
        assert r.allows_crawling is False


class TestSitemapData:
    def test_defaults(self):
        s = SitemapData()
        assert s.exists is False
        assert s.page_count == 0

    def test_with_urls(self):
        s = SitemapData(exists=True, url="/sitemap.xml", page_count=3, urls=["a", "b", "c"])
        assert len(s.urls) == 3


class TestSiteSeoData:
    def test_minimal(self):
        site = SiteSeoData(domain="example.se", crawl_date=datetime.now())
        assert site.domain == "example.se"
        assert site.pages == []
        assert site.orphan_pages == []

    def test_serialization_roundtrip(self):
        site = SiteSeoData(
            domain="example.se",
            crawl_date=datetime(2026, 4, 2),
            pages=[PageSeoData(url="https://example.se")],
            total_pages_crawled=1,
        )
        json_str = site.model_dump_json()
        restored = SiteSeoData.model_validate_json(json_str)
        assert restored.domain == "example.se"
        assert len(restored.pages) == 1


class TestCoreWebVitals:
    def test_defaults(self):
        cwv = CoreWebVitals()
        assert cwv.lcp_ms is None
        assert cwv.cls is None

    def test_with_values(self):
        cwv = CoreWebVitals(lcp_ms=2500, cls=0.1, tbt_ms=200)
        assert cwv.lcp_ms == 2500


class TestLighthouseResult:
    def test_empty(self):
        lr = LighthouseResult()
        assert lr.performance_score is None
        assert lr.core_web_vitals.lcp_ms is None

    def test_with_scores(self):
        lr = LighthouseResult(
            url="https://example.se",
            performance_score=85.0,
            seo_score=92.0,
            core_web_vitals=CoreWebVitals(lcp_ms=1800),
        )
        assert lr.performance_score == 85.0


class TestSeoIssue:
    def test_creation(self):
        issue = SeoIssue(
            category=IssueCategory.ON_PAGE,
            severity=IssueSeverity.HIGH,
            title="Saknar meta-beskrivning",
            description="Sidan saknar en meta-beskrivning.",
            affected_urls=["https://example.se"],
            fix_suggestion="Skriv en unik meta-beskrivning (120-160 tecken).",
            impact_estimate="Uppskattat +15-25% CTR",
            effort="low",
        )
        assert issue.severity == IssueSeverity.HIGH
        assert issue.effort == "low"


class TestSeoScorecard:
    def test_creation(self):
        sc = SeoScorecard(
            overall_score=72.5,
            category_scores=[
                CategoryScore(category=IssueCategory.ON_PAGE, score=80, label="On-page"),
                CategoryScore(category=IssueCategory.TECHNICAL, score=65, label="Teknisk"),
            ],
            issues=[],
            summary_sv="Webbplatsen har en bra grund men behöver förbättringar.",
        )
        assert sc.overall_score == 72.5
        assert len(sc.category_scores) == 2


class TestCompetitorModels:
    def test_seo_gap(self):
        gap = SeoGap(
            area="Schema markup",
            client_value="Saknas",
            competitor_value="LocalBusiness JSON-LD",
            competitor_domain="rival.se",
            recommendation="Lägg till LocalBusiness-schema.",
        )
        assert gap.competitor_domain == "rival.se"

    def test_competitor_profile(self):
        profile = CompetitorSeoProfile(url="https://rival.se", domain="rival.se")
        assert profile.scorecard.overall_score == 0

    def test_competitor_analysis(self):
        analysis = SeoCompetitorAnalysis(
            client_url="https://example.se",
            client_scorecard=SeoScorecard(overall_score=70),
            competitors=[],
            gaps=[],
            advantages=["Bättre innehåll"],
        )
        assert len(analysis.advantages) == 1


class TestSeoAnalysisResult:
    def test_single_mode(self):
        result = SeoAnalysisResult(
            mode="single",
            analyzed_at=datetime.now(),
            page_data=PageSeoData(url="https://example.se"),
            scorecard=SeoScorecard(overall_score=75),
        )
        assert result.mode == "single"
        assert result.site_data is None

    def test_site_mode(self):
        result = SeoAnalysisResult(
            mode="site",
            analyzed_at=datetime.now(),
            site_data=SiteSeoData(domain="example.se", crawl_date=datetime.now()),
            scorecard=SeoScorecard(overall_score=68),
        )
        assert result.mode == "site"
        assert result.page_data is None

    def test_full_serialization_roundtrip(self):
        result = SeoAnalysisResult(
            mode="single",
            analyzed_at=datetime(2026, 4, 2, 12, 0, 0),
            page_data=PageSeoData(url="https://example.se", title="Test"),
            lighthouse=LighthouseResult(url="https://example.se", performance_score=90),
            scorecard=SeoScorecard(
                overall_score=82,
                issues=[
                    SeoIssue(
                        category=IssueCategory.ON_PAGE,
                        severity=IssueSeverity.MEDIUM,
                        title="Test issue",
                        description="Description",
                        fix_suggestion="Fix it",
                        impact_estimate="Impact",
                    )
                ],
            ),
        )
        json_str = result.model_dump_json()
        restored = SeoAnalysisResult.model_validate_json(json_str)
        assert restored.mode == "single"
        assert restored.scorecard.overall_score == 82
        assert len(restored.scorecard.issues) == 1
        assert restored.lighthouse.performance_score == 90
