"""Tests for ad copy generator -- Swedish rules, headline/description generation, RSA assembly."""

import pytest

from src.generators.ad_copy_generator import (
    _apply_swedish_rules,
    _fit_to_limit,
    _fill_pattern,
    generate_headlines,
    generate_descriptions,
    generate_rsa,
)
from src.models.campaign import AdHeadline, AdDescription, ResponsiveSearchAd
from src.models.client import ClientProfile


class TestApplySwedishRules:
    def test_replaces_er_with_du_forms(self):
        assert _apply_swedish_rules("Er tandhygienist") == "Din tandhygienist"
        assert _apply_swedish_rules("Ert val") == "Ditt val"
        assert _apply_swedish_rules("Era tjänster") == "Dina tjänster"

    def test_formats_prices_correctly(self):
        assert "1 299 kr" in _apply_swedish_rules("1299kr")
        assert "1 299 kr" in _apply_swedish_rules("1299 kr")

    def test_large_price_formatting(self):
        result = _apply_swedish_rules("50000kr")
        assert "50 000 kr" in result

    def test_leaves_correct_text_unchanged(self):
        text = "Boka din tid idag"
        assert _apply_swedish_rules(text) == text


class TestFitToLimit:
    def test_short_text_unchanged(self):
        assert _fit_to_limit("Kort text", 30) == "Kort text"

    def test_abbreviation_applied(self):
        result = _fit_to_limit("Professionell telefon information", 30)
        assert len(result) <= 30

    def test_truncates_at_word_boundary(self):
        long_text = "Detta är en väldigt lång rubriktext som inte passar"
        result = _fit_to_limit(long_text, 30)
        assert len(result) <= 30
        assert not result.endswith(" ")

    def test_exact_limit_unchanged(self):
        text = "A" * 30
        assert _fit_to_limit(text, 30) == text


class TestFillPattern:
    def test_fills_company_and_service(self, sample_client: ClientProfile):
        result = _fill_pattern("{Företag} - {Tjänst}", sample_client, "rörmokare", [])
        assert sample_client.business_name in result
        assert "Rörmokare" in result

    def test_fills_city(self, sample_client: ClientProfile):
        result = _fill_pattern("{Tjänst} i {Stad}", sample_client, "vvs", [])
        assert "Stockholm" in result

    def test_cleans_empty_placeholders(self, sample_client: ClientProfile):
        result = _fill_pattern("{Tjänst} - {Telefon}", sample_client, "vvs", [])
        # Should clean up trailing dash from empty phone
        assert not result.endswith(" - ")


class TestGenerateHeadlines:
    def test_returns_at_most_15(self, sample_client: ClientProfile):
        headlines = generate_headlines("rörmokare", sample_client, ["rörmokare stockholm"])
        assert len(headlines) <= 15

    def test_returns_at_least_3(self, sample_client: ClientProfile):
        headlines = generate_headlines("vvs", sample_client, ["vvs"])
        assert len(headlines) >= 3

    def test_all_within_30_chars(self, sample_client: ClientProfile):
        headlines = generate_headlines("rörmokare", sample_client, ["rörmokare", "vvs-jour"])
        for h in headlines:
            assert isinstance(h, AdHeadline)
            assert len(h.text) <= 30, f"Headline too long: '{h.text}' ({len(h.text)} chars)"

    def test_no_duplicates(self, sample_client: ClientProfile):
        headlines = generate_headlines("rörmokare", sample_client, ["rörmokare", "vvs"])
        texts = [h.text for h in headlines]
        assert len(texts) == len(set(texts)), f"Duplicate headlines: {texts}"

    def test_includes_brand_name(self, sample_client: ClientProfile):
        headlines = generate_headlines("rörmokare", sample_client, ["rörmokare"])
        texts = [h.text for h in headlines]
        assert sample_client.business_name in texts or any(
            sample_client.business_name in t for t in texts
        )


class TestGenerateDescriptions:
    def test_returns_at_most_4(self, sample_client: ClientProfile):
        descriptions = generate_descriptions("rörmokare", sample_client, ["rörmokare"])
        assert len(descriptions) <= 4

    def test_returns_at_least_2(self, sample_client: ClientProfile):
        descriptions = generate_descriptions("vvs", sample_client, ["vvs"])
        assert len(descriptions) >= 2

    def test_all_within_90_chars(self, sample_client: ClientProfile):
        descriptions = generate_descriptions("rörmokare", sample_client, ["rörmokare", "vvs-jour"])
        for d in descriptions:
            assert isinstance(d, AdDescription)
            assert len(d.text) <= 90, f"Description too long: '{d.text}' ({len(d.text)} chars)"

    def test_no_duplicates(self, sample_client: ClientProfile):
        descriptions = generate_descriptions("rörmokare", sample_client, ["rörmokare"])
        texts = [d.text for d in descriptions]
        assert len(texts) == len(set(texts))


class TestGenerateRSA:
    def test_returns_valid_rsa(self, sample_client: ClientProfile):
        rsa = generate_rsa(
            "rörmokare",
            sample_client,
            ["rörmokare stockholm", "vvs-jour"],
            "https://www.stockholmsrormokare.se",
        )
        assert isinstance(rsa, ResponsiveSearchAd)
        assert len(rsa.headlines) >= 3
        assert len(rsa.descriptions) >= 2

    def test_url_paths_within_limits(self, sample_client: ClientProfile):
        rsa = generate_rsa(
            "rörmokare",
            sample_client,
            ["rörmokare"],
            "https://www.stockholmsrormokare.se",
        )
        assert len(rsa.path1) <= 15
        assert len(rsa.path2) <= 15

    def test_swedish_chars_in_output(self, sample_client: ClientProfile):
        rsa = generate_rsa(
            "rörmokare",
            sample_client,
            ["rörmokare stockholm"],
            "https://www.stockholmsrormokare.se",
        )
        all_text = " ".join(h.text for h in rsa.headlines) + " ".join(d.text for d in rsa.descriptions)
        # Should contain Swedish characters since the theme and client have them
        has_swedish = any(c in all_text for c in "åäöÅÄÖ")
        assert has_swedish, f"No Swedish diacritics found in ad copy: {all_text}"


class TestTargetGeoOverride:
    """target_geo lets geo-structured campaigns produce per-geo adaptive copy."""

    def test_headlines_use_target_geo_when_set(self, sample_client: ClientProfile, monkeypatch):
        from src.models.client import GeoTarget

        monkeypatch.setenv("SEM_DISABLE_LLM", "1")
        # sample_client has Stockholm in its business name AND geographic_targets,
        # which would mask the geo-override bug. Strip that and use Göteborg as override.
        client = sample_client.model_copy(update={
            "business_name": "Rörmokare Sverige AB",
            "geographic_targets": [GeoTarget(name="Stockholm")],
        })
        target = GeoTarget(name="Göteborg", google_geo_id=2711533)
        headlines = generate_headlines(
            "rörmokare", client, ["rörmokare"], target_geo=target
        )
        texts = [h.text for h in headlines]
        assert any("Göteborg" in t for t in texts), f"No Göteborg headline: {texts}"
        # Now that brand doesn't contain "Stockholm", a leak must come from the geo path
        assert not any("Stockholm" in t for t in texts), (
            f"Headlines leaked Stockholm despite target_geo=Göteborg: {texts}"
        )

    def test_falls_back_to_client_geos_when_target_geo_none(self, sample_client: ClientProfile, monkeypatch):
        monkeypatch.setenv("SEM_DISABLE_LLM", "1")
        headlines = generate_headlines("rörmokare", sample_client, ["rörmokare"])
        texts = [h.text for h in headlines]
        assert any("Stockholm" in t for t in texts), (
            f"Without target_geo, should use client's Stockholm: {texts}"
        )

    def test_fill_pattern_uses_target_geo(self, sample_client: ClientProfile):
        from src.generators.ad_copy_generator import _fill_pattern
        from src.models.client import GeoTarget

        target = GeoTarget(name="Malmö")
        result = _fill_pattern(
            "{Tjänst} i {Stad}", sample_client, "rörmokare", [], target_geo=target,
        )
        assert "Malmö" in result
        assert "Stockholm" not in result
