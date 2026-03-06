"""Tests for Swedish data files -- parsing, diacritics, schema validation."""

import json
import re
from pathlib import Path

import jsonschema

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "swedish"
SCHEMA_DIR = Path(__file__).resolve().parent.parent / "data" / "schemas"

_DATA_FILES = [
    "negative_keywords.json",
    "cta_phrases.json",
    "ad_copy_patterns.json",
    "industry_keywords.json",
]

# Patterns that indicate missing Swedish diacritics (ASCII approximations).
# Each tuple: (regex_pattern, description)
_ASCII_APPROXIMATIONS = [
    (r"\btjanst", "tjanst (should be tjänst)"),
    (r"\bsjalv", "sjalv (should be själv)"),
    (r"\bsokord", "sokord (should be sökord)"),
    (r"\bkarriar\b", "karriar (should be karriär)"),
    (r"\blon\b", "lon (should be lön)"),
    (r"\bFa\b", "Fa (should be Få)"),
]


class TestDataFilesParseClean:
    """All four JSON data files should parse without errors."""

    def test_all_json_files_parse(self):
        for fname in _DATA_FILES:
            path = DATA_DIR / fname
            assert path.exists(), f"Missing data file: {fname}"
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data, f"{fname} is empty"


class TestNoDiacriticsApproximations:
    """Data files must use real Swedish diacritics, not ASCII stand-ins."""

    def test_no_ascii_swedish_in_data_files(self):
        for fname in _DATA_FILES:
            path = DATA_DIR / fname
            content = path.read_text(encoding="utf-8")
            for pattern, desc in _ASCII_APPROXIMATIONS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                assert not matches, (
                    f"ASCII approximation '{desc}' found in {fname}: {matches}"
                )


class TestCTAHeadlineLengths:
    """CTA phrases that could serve as headlines must be within 30 chars."""

    def test_cta_phrases_within_headline_limit(self):
        path = DATA_DIR / "cta_phrases.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for category, phrases in data.items():
            for phrase in phrases:
                assert len(phrase) <= 30, (
                    f"CTA phrase too long for headline ({len(phrase)} chars): "
                    f"'{phrase}' in category '{category}'"
                )


class TestNegativeKeywordsNonEmpty:
    """Every category in negative_keywords.json must have entries."""

    def test_all_categories_non_empty(self):
        path = DATA_DIR / "negative_keywords.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for category, terms in data.items():
            assert len(terms) > 0, f"Empty category: {category}"


class TestNoDuplicatesWithinCategories:
    """No duplicate entries within the same category in any data file."""

    def test_no_duplicates(self):
        for fname in ["negative_keywords.json", "cta_phrases.json", "industry_keywords.json"]:
            path = DATA_DIR / fname
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for category, items in data.items():
                if not isinstance(items, list):
                    continue
                lowered = [i.lower() for i in items]
                dupes = [x for x in lowered if lowered.count(x) > 1]
                assert not dupes, (
                    f"Duplicates in {fname} -> {category}: {set(dupes)}"
                )


class TestJSONSchemaValidation:
    """Data files must validate against their JSON schemas."""

    _SCHEMA_MAP = {
        "negative_keywords.json": "negative_keywords.schema.json",
        "cta_phrases.json": "cta_phrases.schema.json",
        "ad_copy_patterns.json": "ad_copy_patterns.schema.json",
        "industry_keywords.json": "industry_keywords.schema.json",
    }

    def test_validate_against_schemas(self):
        for data_file, schema_file in self._SCHEMA_MAP.items():
            data_path = DATA_DIR / data_file
            schema_path = SCHEMA_DIR / schema_file

            assert schema_path.exists(), f"Missing schema: {schema_file}"

            with open(data_path, encoding="utf-8") as f:
                data = json.load(f)
            with open(schema_path, encoding="utf-8") as f:
                schema = json.load(f)

            jsonschema.validate(instance=data, schema=schema)
