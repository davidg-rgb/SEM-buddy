"""Swedish NLP utilities for SEM Master."""

from __future__ import annotations

from pathlib import Path

_STOPWORDS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "swedish" / "stopwords.txt"

_stopwords_cache: set[str] | None = None


def _load_stopwords() -> set[str]:
    global _stopwords_cache
    if _stopwords_cache is not None:
        return _stopwords_cache
    if _STOPWORDS_PATH.exists():
        _stopwords_cache = {
            line.strip().lower()
            for line in _STOPWORDS_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
    else:
        _stopwords_cache = set()
    return _stopwords_cache


SWEDISH_STOPWORDS: set[str] = set()


def get_stopwords() -> set[str]:
    global SWEDISH_STOPWORDS
    if not SWEDISH_STOPWORDS:
        SWEDISH_STOPWORDS = _load_stopwords()
    return SWEDISH_STOPWORDS


# Common Swedish compound word suffixes for splitting heuristic
_COMPOUND_SUFFIXES = [
    "tjänst", "tjänster", "butik", "butiken", "system", "företag",
    "service", "verkstad", "handel", "center", "grupp", "byrå",
    "konsult", "teknik", "produkt", "produkter", "lösning", "lösningar",
]


def split_compound_word(word: str) -> list[str]:
    """Basic Swedish compound word splitting.

    Tries to split at common suffix boundaries. Returns [word] if no split found.
    """
    word_lower = word.lower()
    for suffix in sorted(_COMPOUND_SUFFIXES, key=len, reverse=True):
        if word_lower.endswith(suffix) and len(word_lower) > len(suffix) + 2:
            prefix = word[: len(word) - len(suffix)]
            # Handle binding-s: "företagstjänst" -> "företag" + "tjänst"
            if prefix.endswith("s"):
                prefix = prefix[:-1]
            if len(prefix) >= 3:
                return [prefix, word[-len(suffix):]]
    return [word]


_DIACRITICS_MAP = {
    "a": "å",
    "å": "a",
    "o": "ö",
    "ö": "o",
    "a": "ä",
    "ä": "a",
}


def generate_diacritics_variants(text: str) -> list[str]:
    """Generate variants with Swedish diacritics swapped (a/å, o/ö, a/ä)."""
    variants: set[str] = set()
    text_lower = text.lower()

    replacements = [
        ("a", "å"), ("å", "a"),
        ("o", "ö"), ("ö", "o"),
        ("a", "ä"), ("ä", "a"),
    ]

    for orig, repl in replacements:
        if orig in text_lower:
            variants.add(text_lower.replace(orig, repl, 1))

    variants.discard(text_lower)
    return sorted(variants)


def get_shorter_synonym(word: str, max_chars: int) -> str | None:
    """Placeholder for synonym lookup. Returns None until dictionary is loaded."""
    return None


def count_display_chars(text: str) -> int:
    """Count display characters for Google Ads validation.

    For Swedish text this is the same as len(), but this function exists
    for consistency and potential future adjustments.
    """
    return len(text)
