"""Tests for competitor SEO comparison."""

from datetime import datetime

import pytest

from src.analysis.seo_analyzer import analyze_page_seo
from src.analysis.seo_competitor import (
    _compute_gaps,
    _identify_advantages,
    generate_synthetic_competitor_data,
)
from src.models.seo import (
    IssueCategory,
    LinkInfo,
    PageSeoData,
    SchemaMarkup,
    SeoScorecard,
)
from src.scrapers.seo_scraper import generate_synthetic_page_data


class TestComputeGaps:
    def test_schema_gap(self):
        client = PageSeoData(url="https://client.se", schema_markup=[])
        competitor = PageSeoData(
            url="https://rival.se",
            schema_markup=[
                SchemaMarkup(schema_type="LocalBusiness", format="json-ld",
                             raw_data={"@type": "LocalBusiness", "name": "Rival"})
            ],
        )
        client_sc = analyze_page_seo(client)
        comp_sc = analyze_page_seo(competitor)
        gaps = _compute_gaps(client, client_sc, competitor, comp_sc)
        schema_gaps = [g for g in gaps if "Schema" in g.area or "schema" in g.area.lower()]
        assert len(schema_gaps) >= 1

    def test_content_length_gap(self):
        client = PageSeoData(url="https://client.se", word_count=200, body_text="a " * 200)
        competitor = PageSeoData(url="https://rival.se", word_count=1000, body_text="a " * 1000)
        client_sc = analyze_page_seo(client)
        comp_sc = analyze_page_seo(competitor)
        gaps = _compute_gaps(client, client_sc, competitor, comp_sc)
        content_gaps = [g for g in gaps if "Innehåll" in g.area or "innehåll" in g.area.lower()]
        assert len(content_gaps) >= 1

    def test_no_gaps_when_client_is_better(self):
        client = PageSeoData(
            url="https://client.se",
            word_count=2000,
            body_text="a " * 2000,
            meta_description="Good description here for the client page.",
            meta_description_length=43,
            schema_markup=[
                SchemaMarkup(schema_type="LocalBusiness", format="json-ld",
                             raw_data={"@type": "LocalBusiness", "name": "Client"})
            ],
        )
        competitor = PageSeoData(url="https://rival.se", word_count=100, body_text="a " * 100)
        client_sc = analyze_page_seo(client)
        comp_sc = analyze_page_seo(competitor)
        gaps = _compute_gaps(client, client_sc, competitor, comp_sc)
        # Should have no content/schema/meta gaps (client is better)
        content_gaps = [g for g in gaps if "Innehåll" in g.area]
        assert len(content_gaps) == 0

    def test_gaps_have_swedish_recommendations(self):
        client = PageSeoData(url="https://client.se", schema_markup=[])
        competitor = PageSeoData(
            url="https://rival.se",
            schema_markup=[SchemaMarkup(schema_type="LocalBusiness", format="json-ld", raw_data={"name": "R"})],
        )
        client_sc = analyze_page_seo(client)
        comp_sc = analyze_page_seo(competitor)
        gaps = _compute_gaps(client, client_sc, competitor, comp_sc)
        for gap in gaps:
            assert gap.recommendation  # Non-empty
            assert gap.competitor_domain  # Non-empty


class TestIdentifyAdvantages:
    def test_identifies_advantage(self):
        # Client has high on-page score, competitor low
        from src.models.seo import CategoryScore
        client_sc = SeoScorecard(
            overall_score=80,
            category_scores=[
                CategoryScore(category=IssueCategory.ON_PAGE, score=90),
                CategoryScore(category=IssueCategory.TECHNICAL, score=80),
                CategoryScore(category=IssueCategory.CONTENT, score=70),
                CategoryScore(category=IssueCategory.LINKS, score=75),
                CategoryScore(category=IssueCategory.SCHEMA, score=60),
            ],
        )
        comp_sc = SeoScorecard(
            overall_score=50,
            category_scores=[
                CategoryScore(category=IssueCategory.ON_PAGE, score=40),
                CategoryScore(category=IssueCategory.TECHNICAL, score=50),
                CategoryScore(category=IssueCategory.CONTENT, score=45),
                CategoryScore(category=IssueCategory.LINKS, score=55),
                CategoryScore(category=IssueCategory.SCHEMA, score=30),
            ],
        )
        advantages = _identify_advantages(client_sc, [comp_sc])
        assert len(advantages) >= 1

    def test_no_advantages_when_competitor_is_better(self):
        from src.models.seo import CategoryScore
        client_sc = SeoScorecard(
            overall_score=30,
            category_scores=[
                CategoryScore(category=IssueCategory.ON_PAGE, score=20),
                CategoryScore(category=IssueCategory.TECHNICAL, score=30),
                CategoryScore(category=IssueCategory.CONTENT, score=25),
                CategoryScore(category=IssueCategory.LINKS, score=35),
                CategoryScore(category=IssueCategory.SCHEMA, score=10),
            ],
        )
        comp_sc = SeoScorecard(
            overall_score=90,
            category_scores=[
                CategoryScore(category=IssueCategory.ON_PAGE, score=90),
                CategoryScore(category=IssueCategory.TECHNICAL, score=95),
                CategoryScore(category=IssueCategory.CONTENT, score=85),
                CategoryScore(category=IssueCategory.LINKS, score=90),
                CategoryScore(category=IssueCategory.SCHEMA, score=80),
            ],
        )
        advantages = _identify_advantages(client_sc, [comp_sc])
        # Client should have no advantages (all scores below 50)
        assert len(advantages) == 0


class TestSyntheticCompetitorData:
    def test_generates_valid_analysis(self):
        page = generate_synthetic_page_data("https://client.se")
        scorecard = analyze_page_seo(page)
        analysis = generate_synthetic_competitor_data(["https://rival.se"], scorecard)
        assert len(analysis.competitors) == 1
        assert analysis.competitors[0].domain == "rival.se"
        assert analysis.competitors[0].scorecard.overall_score > 0

    def test_generates_gaps(self):
        page = generate_synthetic_page_data("https://client.se")
        scorecard = analyze_page_seo(page)
        analysis = generate_synthetic_competitor_data(
            ["https://rival1.se", "https://rival2.se"], scorecard
        )
        assert len(analysis.competitors) == 2
        # Synthetic competitors should have schema (client doesn't) → at least 1 gap
        assert len(analysis.gaps) >= 1

    def test_multiple_competitors(self):
        page = generate_synthetic_page_data("https://client.se")
        scorecard = analyze_page_seo(page)
        analysis = generate_synthetic_competitor_data(
            ["https://a.se", "https://b.se", "https://c.se"], scorecard
        )
        assert len(analysis.competitors) == 3
