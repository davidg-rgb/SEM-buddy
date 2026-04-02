"""Tests for SEO scraper — synthetic data generators and heading validation."""

from datetime import datetime

import pytest

from src.scrapers.seo_scraper import (
    _validate_heading_hierarchy,
    generate_synthetic_page_data,
    generate_synthetic_site_data,
)
from src.models.seo import PageSeoData, SiteSeoData


class TestHeadingHierarchyValidation:
    def test_valid_hierarchy(self):
        headings = [
            {"tag": "h1", "text": "Main"},
            {"tag": "h2", "text": "Sub"},
            {"tag": "h3", "text": "Sub-sub"},
        ]
        assert _validate_heading_hierarchy(headings) is True

    def test_empty_headings(self):
        assert _validate_heading_hierarchy([]) is False

    def test_no_h1(self):
        headings = [{"tag": "h2", "text": "Sub"}]
        assert _validate_heading_hierarchy(headings) is False

    def test_multiple_h1(self):
        headings = [
            {"tag": "h1", "text": "First"},
            {"tag": "h1", "text": "Second"},
        ]
        assert _validate_heading_hierarchy(headings) is False

    def test_skipped_level(self):
        headings = [
            {"tag": "h1", "text": "Main"},
            {"tag": "h3", "text": "Skipped h2"},
        ]
        assert _validate_heading_hierarchy(headings) is False

    def test_h1_then_h2_then_h4_skips(self):
        headings = [
            {"tag": "h1", "text": "Main"},
            {"tag": "h2", "text": "Sub"},
            {"tag": "h4", "text": "Skipped h3"},
        ]
        assert _validate_heading_hierarchy(headings) is False

    def test_valid_deep_hierarchy(self):
        headings = [
            {"tag": "h1", "text": "Main"},
            {"tag": "h2", "text": "Sub"},
            {"tag": "h3", "text": "Sub-sub"},
            {"tag": "h2", "text": "Another sub"},
        ]
        # h3 -> h2 is a step back, which is fine (not a skip forward)
        assert _validate_heading_hierarchy(headings) is True


class TestSyntheticPageData:
    def test_returns_valid_model(self):
        data = generate_synthetic_page_data("https://example.se")
        assert isinstance(data, PageSeoData)
        assert data.url == "https://example.se"

    def test_has_title(self):
        data = generate_synthetic_page_data("https://example.se")
        assert data.title != ""
        assert data.title_length > 0

    def test_has_h1(self):
        data = generate_synthetic_page_data("https://example.se")
        assert data.h1 != ""
        assert data.h1_count == 1

    def test_has_headings(self):
        data = generate_synthetic_page_data("https://example.se")
        assert len(data.headings) >= 3

    def test_has_images_with_some_missing_alt(self):
        data = generate_synthetic_page_data("https://example.se")
        assert len(data.images) >= 2
        assert data.images_without_alt >= 1

    def test_has_links(self):
        data = generate_synthetic_page_data("https://example.se")
        assert len(data.internal_links) >= 2
        assert len(data.external_links) >= 1

    def test_has_open_graph(self):
        data = generate_synthetic_page_data("https://example.se")
        assert len(data.open_graph) >= 1

    def test_no_schema_for_demo_issues(self):
        data = generate_synthetic_page_data("https://example.se")
        assert len(data.schema_markup) == 0

    def test_has_render_blocking(self):
        data = generate_synthetic_page_data("https://example.se")
        assert len(data.render_blocking_resources) >= 1

    def test_serialization_roundtrip(self):
        data = generate_synthetic_page_data("https://example.se")
        json_str = data.model_dump_json()
        restored = PageSeoData.model_validate_json(json_str)
        assert restored.url == data.url
        assert restored.title == data.title


class TestSyntheticSiteData:
    def test_returns_valid_model(self):
        data = generate_synthetic_site_data("https://example.se")
        assert isinstance(data, SiteSeoData)
        assert data.domain != ""

    def test_has_multiple_pages(self):
        data = generate_synthetic_site_data("https://example.se")
        assert len(data.pages) >= 3
        assert data.total_pages_crawled == len(data.pages)

    def test_has_robots_txt(self):
        data = generate_synthetic_site_data("https://example.se")
        assert data.robots_txt.exists is True
        assert len(data.robots_txt.sitemap_urls) >= 1

    def test_has_sitemap(self):
        data = generate_synthetic_site_data("https://example.se")
        assert len(data.sitemaps) >= 1
        assert data.sitemaps[0].exists is True

    def test_has_orphan_pages(self):
        data = generate_synthetic_site_data("https://example.se")
        assert len(data.orphan_pages) >= 1

    def test_link_counts(self):
        data = generate_synthetic_site_data("https://example.se")
        assert data.total_internal_links > 0

    def test_pages_have_varying_quality(self):
        """Synthetic data should include pages with different quality levels."""
        data = generate_synthetic_site_data("https://example.se")
        meta_lens = [p.meta_description_length for p in data.pages]
        # At least one page should be missing meta description
        assert 0 in meta_lens
        # At least one page should have one
        assert any(ml > 0 for ml in meta_lens)

    def test_serialization_roundtrip(self):
        data = generate_synthetic_site_data("https://example.se")
        json_str = data.model_dump_json()
        restored = SiteSeoData.model_validate_json(json_str)
        assert restored.domain == data.domain
        assert len(restored.pages) == len(data.pages)
