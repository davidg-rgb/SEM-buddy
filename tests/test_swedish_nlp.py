"""Tests for Swedish NLP utilities."""

from src.utils.swedish_nlp import (
    split_compound_word,
    generate_diacritics_variants,
    get_stopwords,
    count_display_chars,
)


class TestSplitCompoundWord:
    def test_badrumsrenovering(self):
        parts = split_compound_word("badrumsrenovering")
        assert len(parts) >= 2, f"Expected compound split, got {parts}"
        joined = "".join(parts)
        # The joined parts (ignoring interfix 's') should relate to the original
        assert "bad" in parts[0] or "badrum" in parts[0]

    def test_foretagstjanst(self):
        parts = split_compound_word("företagstjänst")
        assert len(parts) >= 2, f"Expected compound split, got {parts}"

    def test_short_word_no_split(self):
        parts = split_compound_word("bil")
        assert parts == ["bil"]


class TestDiacriticsVariants:
    def test_generates_variants_with_diacritics(self):
        variants = generate_diacritics_variants("tjanst")
        # Should produce a variant with ä
        assert any("ä" in v for v in variants), f"Expected ä variant, got {variants}"

    def test_no_crash_on_plain_word(self):
        variants = generate_diacritics_variants("bil")
        assert isinstance(variants, list)


class TestGetStopwords:
    def test_returns_non_empty_set(self):
        sw = get_stopwords()
        assert len(sw) > 0

    def test_contains_common_stopwords(self):
        sw = get_stopwords()
        for word in ["och", "att", "det"]:
            assert word in sw, f"Expected '{word}' in stopwords"


class TestCountDisplayChars:
    def test_swedish_text(self):
        assert count_display_chars("Få offert") == 9

    def test_empty_string(self):
        assert count_display_chars("") == 0
