"""Swedish NLP utilities for SEM Master."""

from __future__ import annotations

import functools
from pathlib import Path

import simplemma

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


def _is_swedish_word(word: str) -> bool:
    """Check if a word is recognized in the Swedish dictionary via simplemma."""
    return simplemma.is_known(word.lower(), lang="sv")


@functools.lru_cache(maxsize=4096)
def split_compound_word(word: str) -> list[str]:
    """Split a Swedish compound word into its components.

    Uses simplemma's Swedish dictionary to validate candidate splits.
    Handles -s- interfix (e.g. 'företagstjänst' -> 'företag' + 'tjänst').
    Supports recursive splitting for 3+ part compounds.
    Results are cached for performance.
    """
    word_lower = word.lower()

    if len(word_lower) < 6:
        return [word_lower]

    best_split: list[str] | None = None
    best_score = 0

    # Try all split positions
    for i in range(3, len(word_lower) - 2):
        left = word_lower[:i]
        right = word_lower[i:]

        # Build candidate splits: (left_part, right_part, bonus)
        # bonus rewards interfix-stripped forms (base forms preferred)
        candidates = [(left, right, 0)]

        # Handle -s- interfix: 'badrumsrenovering' -> 'badrum' + 'renovering'
        if right.startswith("s") and len(right) > 3:
            candidates.append((left, right[1:], 1))
        if left.endswith("s") and len(left) > 3:
            candidates.append((left[:-1], right, 1))

        for l_part, r_part, bonus in candidates:
            if len(l_part) < 3 or len(r_part) < 3:
                continue

            l_known = _is_swedish_word(l_part)
            r_known = _is_swedish_word(r_part)

            if l_known and r_known:
                # Score: prefer balanced splits; bonus for interfix-stripped base forms
                score = min(len(l_part), len(r_part)) + bonus
                if score > best_score:
                    best_score = score
                    best_split = [l_part, r_part]

    if best_split is None:
        return [word_lower]

    # Recursively try to split the right part for 3+ component compounds
    # Only recurse if the right part is long enough to be a real compound
    if len(best_split[1]) >= 10:
        right_parts = split_compound_word(best_split[1])
        if len(right_parts) > 1:
            return [best_split[0]] + right_parts

    return best_split


# Bidirectional diacritics mapping as list of tuples to avoid duplicate key issues
_DIACRITICS_PAIRS = [
    ("a", "å"),
    ("a", "ä"),
    ("o", "ö"),
]


def generate_diacritics_variants(text: str) -> list[str]:
    """Generate variants with Swedish diacritics swapped (a/å, a/ä, o/ö)."""
    variants: set[str] = set()
    text_lower = text.lower()

    # Build bidirectional replacements from pairs
    replacements = []
    for ascii_char, diacritic_char in _DIACRITICS_PAIRS:
        replacements.append((ascii_char, diacritic_char))
        replacements.append((diacritic_char, ascii_char))

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
