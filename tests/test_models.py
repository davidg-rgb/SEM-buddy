"""Tests for Pydantic model validation -- headlines, descriptions, paths, RSA, campaigns."""

import pytest
from pydantic import ValidationError

from src.models.campaign import (
    AdHeadline, AdDescription, ResponsiveSearchAd, Campaign, Sitelink, AdGroup, Keyword,
)


# ---------------------------------------------------------------------------
# AdHeadline
# ---------------------------------------------------------------------------

class TestAdHeadline:
    def test_exactly_30_chars_passes(self):
        text = "A" * 30
        h = AdHeadline(text=text)
        assert h.text == text

    def test_31_chars_raises(self):
        with pytest.raises(ValidationError):
            AdHeadline(text="A" * 31)

    def test_swedish_chars_count_correctly(self):
        # "Få offert nu - rörmokare Sthlm" is exactly 30 chars
        text = "Få offert nu - rörmokare Sthlm"
        assert len(text) == 30
        h = AdHeadline(text=text)
        assert h.text == text
        assert h.char_count == 30


# ---------------------------------------------------------------------------
# AdDescription
# ---------------------------------------------------------------------------

class TestAdDescription:
    def test_exactly_90_chars_passes(self):
        text = "B" * 90
        d = AdDescription(text=text)
        assert d.text == text

    def test_91_chars_raises(self):
        with pytest.raises(ValidationError):
            AdDescription(text="B" * 91)


# ---------------------------------------------------------------------------
# Path fields (max_length=15 via Field)
# ---------------------------------------------------------------------------

class TestPathFields:
    def test_path_15_chars_passes(self):
        rsa = ResponsiveSearchAd(
            headlines=[AdHeadline(text="H1"), AdHeadline(text="H2"), AdHeadline(text="H3")],
            descriptions=[AdDescription(text="D1"), AdDescription(text="D2")],
            final_url="https://example.se",
            path1="a" * 15,
            path2="b" * 15,
        )
        assert len(rsa.path1) == 15
        assert len(rsa.path2) == 15

    def test_path_16_chars_raises(self):
        with pytest.raises(ValidationError):
            ResponsiveSearchAd(
                headlines=[AdHeadline(text="H1"), AdHeadline(text="H2"), AdHeadline(text="H3")],
                descriptions=[AdDescription(text="D1"), AdDescription(text="D2")],
                final_url="https://example.se",
                path1="a" * 16,
                path2="",
            )


# ---------------------------------------------------------------------------
# Sitelink (max_length=25)
# ---------------------------------------------------------------------------

class TestSitelink:
    def test_sitelink_25_chars_passes(self):
        sl = Sitelink(text="A" * 25, final_url="https://example.se")
        assert len(sl.text) == 25

    def test_sitelink_26_chars_raises(self):
        with pytest.raises(ValidationError):
            Sitelink(text="A" * 26, final_url="https://example.se")


# ---------------------------------------------------------------------------
# RSA minimum requirements
# ---------------------------------------------------------------------------

class TestRSA:
    def test_min_3_headlines_2_descriptions(self):
        rsa = ResponsiveSearchAd(
            headlines=[AdHeadline(text="H1"), AdHeadline(text="H2"), AdHeadline(text="H3")],
            descriptions=[AdDescription(text="D1"), AdDescription(text="D2")],
            final_url="https://example.se",
        )
        assert len(rsa.headlines) == 3
        assert len(rsa.descriptions) == 2

    def test_fewer_than_3_headlines_raises(self):
        with pytest.raises(ValidationError):
            ResponsiveSearchAd(
                headlines=[AdHeadline(text="H1"), AdHeadline(text="H2")],
                descriptions=[AdDescription(text="D1"), AdDescription(text="D2")],
                final_url="https://example.se",
            )

    def test_fewer_than_2_descriptions_raises(self):
        with pytest.raises(ValidationError):
            ResponsiveSearchAd(
                headlines=[AdHeadline(text="H1"), AdHeadline(text="H2"), AdHeadline(text="H3")],
                descriptions=[AdDescription(text="D1")],
                final_url="https://example.se",
            )


# ---------------------------------------------------------------------------
# Campaign defaults
# ---------------------------------------------------------------------------

class TestCampaign:
    def test_default_status_is_paused(self):
        c = Campaign(name="Test", budget_sek_daily=100)
        assert c.status == "PAUSED"
