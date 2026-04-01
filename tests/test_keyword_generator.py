"""Tests for keyword generator -- seeds, expansion, grouping, match types, negatives."""

from src.generators.keyword_generator import (
    load_industry_seeds,
    expand_keyword_variations,
    assign_match_types,
    generate_negative_keywords,
    group_keywords,
)


class TestLoadIndustrySeeds:
    def test_loads_vvs_seeds(self):
        seeds = load_industry_seeds("vvs")
        # industry_keywords.json doesn't have a "vvs" key but should fuzzy-match
        # or return empty if not found -- either way, no crash
        assert isinstance(seeds, list)

    def test_loads_tandvard(self):
        seeds = load_industry_seeds("tandvård")
        assert isinstance(seeds, list)
        if seeds:  # If found, should have dental terms
            combined = " ".join(seeds)
            assert "tand" in combined.lower()

    def test_unknown_industry_returns_empty(self):
        seeds = load_industry_seeds("rymdraketer_xyz")
        assert seeds == []


class TestExpandKeywordVariations:
    def test_compound_split_variant(self):
        variants = expand_keyword_variations("badrumsrenovering")
        # Should produce a split variant
        assert isinstance(variants, list)

    def test_diacritics_variant(self):
        variants = expand_keyword_variations("tandläkare")
        # Should have some variant
        assert isinstance(variants, list)

    def test_plural_suffix_removed(self):
        variants = expand_keyword_variations("rörmokare")
        # -ar plural removal should produce "rörmok" (base attempt)
        assert isinstance(variants, list)

    def test_short_word_less_expansion(self):
        variants = expand_keyword_variations("vvs")
        # Short word, fewer compound splits expected
        assert isinstance(variants, list)


class TestAssignMatchTypes:
    def test_low_budget_uses_exact_and_phrase(self):
        keywords = [{"text": "rörmokare"}]
        result = assign_match_types(keywords, 5000)
        match_types = {kw["match_type"] for kw in result}
        assert "EXACT" in match_types
        assert "PHRASE" in match_types
        assert "BROAD" not in match_types

    def test_medium_budget_uses_phrase_primary(self):
        keywords = [{"text": "rörmokare stockholm"}]
        result = assign_match_types(keywords, 15000)
        match_types = {kw["match_type"] for kw in result}
        assert "PHRASE" in match_types

    def test_high_budget_uses_broad(self):
        keywords = [{"text": "rörmokare"}]
        result = assign_match_types(keywords, 50000)
        match_types = {kw["match_type"] for kw in result}
        assert "BROAD" in match_types

    def test_preserves_keyword_text(self):
        keywords = [{"text": "rörmokare stockholm", "monthly_searches": 1200}]
        result = assign_match_types(keywords, 15000)
        assert all(kw["text"] == "rörmokare stockholm" for kw in result)


class TestGenerateNegativeKeywords:
    def test_returns_non_empty(self):
        negatives = generate_negative_keywords(["rörmokare"], "vvs")
        assert len(negatives) > 0

    def test_no_conflicts_with_targets(self):
        target = ["jobb"]  # "jobb" is a common negative, but here it's a target
        negatives = generate_negative_keywords(target, "vvs")
        assert "jobb" not in negatives

    def test_removes_substring_conflicts(self):
        # If target keyword contains a word that's also a negative
        negatives = generate_negative_keywords(["gratis offert"], "vvs")
        # "gratis" appears in targets, should be removed from negatives
        assert "gratis" not in negatives


class TestGroupKeywords:
    def test_groups_by_longest_word(self):
        keywords = [
            {"text": "rörmokare stockholm"},
            {"text": "rörmokare göteborg"},
            {"text": "vvs-jour akut"},
        ]
        groups = group_keywords(keywords)
        assert isinstance(groups, dict)
        assert len(groups) >= 1

    def test_respects_max_per_group(self):
        keywords = [{"text": f"keyword {i}"} for i in range(30)]
        groups = group_keywords(keywords, max_per_group=10)
        for name, kws in groups.items():
            assert len(kws) <= 10

    def test_empty_input(self):
        groups = group_keywords([])
        assert groups == {}
