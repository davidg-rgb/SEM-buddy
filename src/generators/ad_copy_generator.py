"""Multi-language RSA ad copy generator for Google Ads campaigns.

Originally Swedish-only; v0.3 made the language pack and price/number
formatting data-driven. Set `client.language` to "en" to load `data/en/*`
instead of `data/swedish/*`.

v0.3.2 introduces variant-aware generation: `generate_rsa_variants(product)`
returns 3-5 distinct RSAs per ad group, each anchoring a different
psychological lever (price, discount, social proof, urgency, loss aversion).
Patterns are tagged with `variant_role` in `data/<lang>/ad_copy_patterns.json`.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from src.generators import llm_ad_copy
from src.models.campaign import AdHeadline, AdDescription, ResponsiveSearchAd
from src.models.catalog import Product
from src.models.client import ClientProfile, GeoTarget
from src.utils.config import PROJECT_ROOT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Variant policy constants (also exported for tests + callers)
# ---------------------------------------------------------------------------

# Below this threshold the percent number is too small to be a hook; we
# downgrade the variant and emit a `loss_aversion` slot instead.
MIN_DISCOUNT_PCT_FOR_DISCOUNT_LED = 0.15

# LEGACY — retained for backward compatibility with import-by-name. v0.3.4
# operator constraint: SKU/IATA NEVER appears in customer-facing copy. The
# generator no longer consults this set; `_should_use_iata_in_customer_copy`
# returns False unconditionally. Kept to avoid breaking external imports.
IATA_HOUSEHOLD_CODES: frozenset[str] = frozenset()

# Max number of headlines in a discount_led RSA that may repeat the discount
# percent string. Above this, Google flags semantic-similarity. Tail headlines
# and universals fill the rest.
MAX_DISCOUNT_PCT_HEADLINES = 5


# Language → data subdirectory under data/
_LANG_DIRS = {
    "sv": "swedish",
    "en": "en",
}

DATA_ROOT = PROJECT_ROOT / "data"


# Language-specific ad copy conventions
_LANG_CONVENTIONS: dict[str, dict] = {
    "sv": {
        "address_form": "du",
        "currency_suffix": "kr",
        "currency_prefix": "",
        "thousand_separator": " ",
        "decimal_separator": ",",
        "common_abbreviations": {
            "telefon": "tel",
            "information": "info",
            "professionell": "prof.",
            "kostnadsfri": "gratis",
        },
        "filler_words": [" och ", " samt ", " med ", " för ", " din ", " ditt "],
        "ampersand_pairs": (" och ", " samt "),
    },
    "en": {
        "address_form": "you",
        "currency_suffix": "",
        "currency_prefix": "$",
        "thousand_separator": ",",
        "decimal_separator": ".",
        "common_abbreviations": {
            "professional": "pro",
            "guaranteed": "guar.",
            "information": "info",
        },
        "filler_words": [" and ", " with ", " for ", " your ", " our "],
        "ampersand_pairs": (" and ",),
    },
}

# Header types & priorities for RSAs
HEADLINE_TYPES = ["brand", "service", "cta", "usp", "location", "price", "catalog"]


def _lang_dir(language: str) -> Path:
    subdir = _LANG_DIRS.get(language)
    if subdir is None:
        logger.warning("No language pack for %r; falling back to Swedish", language)
        subdir = _LANG_DIRS["sv"]
    return DATA_ROOT / subdir


def _load_json(filename: str, language: str = "sv") -> dict:
    path = _lang_dir(language) / filename
    if not path.exists():
        # Fall back to Swedish defaults if a translation is missing
        fallback = DATA_ROOT / "swedish" / filename
        if fallback.exists():
            logger.warning(
                "Language pack %s missing %s; falling back to Swedish",
                language, filename,
            )
            path = fallback
        else:
            logger.warning("Data file not found: %s", path)
            return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _format_number(value: float | int, language: str) -> str:
    """Format a number per the language's thousand/decimal separators."""
    conv = _LANG_CONVENTIONS.get(language, _LANG_CONVENTIONS["sv"])
    thousand = conv["thousand_separator"]
    decimal = conv["decimal_separator"]
    is_integer = float(value).is_integer()
    if is_integer:
        s = f"{int(value):,}"
        return s.replace(",", thousand) if thousand != "," else s
    s = f"{float(value):,.2f}"
    if thousand == ",":
        # Already uses "," as thousand and "." as decimal — only need to swap
        # when the language differs from Python's default
        if decimal != ".":
            # Swap manually: 1,234.56 -> 1.234,56 by going through a sentinel
            s = s.replace(",", "\x00").replace(".", decimal).replace("\x00", thousand)
    else:
        s = s.replace(",", "\x00").replace(".", decimal).replace("\x00", thousand)
    return s


def _format_price(value: float | int, language: str) -> str:
    conv = _LANG_CONVENTIONS.get(language, _LANG_CONVENTIONS["sv"])
    num = _format_number(value, language)
    return f"{conv['currency_prefix']}{num}{(' ' + conv['currency_suffix']).rstrip() if conv['currency_suffix'] else ''}".strip()


def _apply_swedish_rules(text: str) -> str:
    """Swedish-specific post-processing (du-form, price normalization)."""
    replacements = {
        "Kontakta er": "Kontakta oss",
        "kontakta er": "kontakta oss",
        "Er ": "Din ",
        "Ert ": "Ditt ",
        "Era ": "Dina ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    def fix_price(m: re.Match) -> str:
        n_str = m.group(1).replace(" ", "")
        n = int(n_str)
        formatted = f"{n:,}".replace(",", " ")
        return f"{formatted} kr"

    text = re.sub(r"(\d[\d ]+)\s*kr\b", fix_price, text)
    return text


def _apply_language_rules(text: str, language: str) -> str:
    if language == "sv":
        text = _apply_swedish_rules(text)
    # English-specific or shared: stop-slop post-pass runs after language rules
    return _stop_slop_pass(text)


_TRAILING_CONNECTORS_EN = {
    "the", "a", "an", "and", "or", "with", "from", "in", "of", "for", "to",
    "on", "at", "by", "as", "is", "are", "be",
}
_TRAILING_CONNECTORS_SV = {
    "och", "samt", "med", "för", "din", "ditt", "en", "ett", "av", "till",
    "från", "för", "som", "i", "på",
}

# Single-syllable nouns / fragments that, when stranded at the end of a
# truncated line, leave the reader with an incomplete-sentence feel. We drop
# them aggressively rather than ship "free 24h" / "save the difference on
# every" / "Last-minute Bhubaneswar" style fragments.
# Small set of stop-words that stay lowercase in English title case.
_TITLE_CASE_LOWER_EN = {"to", "the", "a", "an", "for", "of", "and", "in", "on", "at", "by"}


def _title_case_word(word: str) -> str:
    """Title-case a single word, hyphen-aware.

    Python's built-in `str.capitalize()` lowercases everything after the
    first character — which destroys hyphenated proper nouns like
    'Petropavlovsk-Kamchatsky' → 'Petropavlovsk-kamchatsky' (lowercase
    'k' on the second segment). We split on '-' and capitalize each
    segment so the casing survives. Already-uppercase tokens (IATA
    codes like 'NYC', 'DFW') are preserved as-is.
    """
    if word.isupper():
        return word
    if "-" in word:
        return "-".join(seg if seg.isupper() else seg.capitalize() for seg in word.split("-"))
    return word.capitalize()


def _title_case_keyword(kw: str) -> str:
    """Title-case a keyword for use as a headline. First and last words are
    always capitalized; middle stop-words stay lowercase per English
    title-case convention (so 'cheap flights to hartford' becomes
    'Cheap Flights to Hartford' rather than 'Cheap flights to hartford').

    Hyphenated tokens are title-cased segment-by-segment via
    `_title_case_word` so 'petropavlovsk-kamchatsky' becomes
    'Petropavlovsk-Kamchatsky' rather than 'Petropavlovsk-kamchatsky'.
    """
    parts = kw.split()
    if not parts:
        return kw
    out: list[str] = []
    last_idx = len(parts) - 1
    for i, p in enumerate(parts):
        low = p.lower()
        if 0 < i < last_idx and low in _TITLE_CASE_LOWER_EN:
            out.append(low)
        else:
            out.append(_title_case_word(p))
    return " ".join(out)


_TRAILING_INCOMPLETE_FRAGMENTS_EN = {
    "leg", "fee", "fees", "now", "today", "free", "fare", "fares",
    "flights", "flight", "deals", "search", "compare", "cancellation",
    # Common OTA description tail fragments — these read incomplete when
    # the trailing word(s) of the original sentence get chopped.
    "24h", "policy", "support", "hour", "hours", "every", "seconds", "minutes",
    "side", "by", "online",
    # Naked numbers stranded at end (almost always a truncated "60 seconds",
    # "10 minutes", "1.5M travelers", etc.)
    "60", "30", "24", "10", "15",
    # Romance-language particles ("Fernando De Noronha" → "Fernando De"
    # reads broken). Match case-insensitively via _drop_trailing_bad_tokens'
    # `.lower()` lookup. NOTE: we intentionally do NOT add nominal heads
    # like 'St'/'San'/'Santa' here — those are first-words of destination
    # names and dropping them would mangle 'Santa Cruz' → ''.
    "de", "do", "da", "du", "del", "della", "di",
    "la", "le", "los", "las", "el",
}


_PRICE_TOKEN_RE = re.compile(r"\$\d[\d.,]*")


def _fit_to_limit(text: str, max_chars: int, language: str = "sv") -> str:
    """Trim or abbreviate text so it fits within `max_chars`.

    On truncation, walks back past any trailing connector word (the, and, with,
    from, …) so the result doesn't end mid-clause. Also strips trailing
    punctuation, and returns empty string if the trimmed result would be
    aggressively short (<50% of budget) so the caller can skip the pattern
    rather than ship a fragment.

    Price-token preservation (v0.3.4): if the input carries a `$<digits>`
    price token (e.g. '$224') and truncation drops it from the output, the
    result is rejected — better to skip the pattern entirely than ship the
    operator's mandatory price-bearing description without the price.
    """
    original_prices = set(_PRICE_TOKEN_RE.findall(text)) if text else set()
    connector_words = (
        _TRAILING_CONNECTORS_EN if language == "en" else _TRAILING_CONNECTORS_SV
    )

    def _strip_trailing_punct(s: str) -> str:
        return s.rstrip(" ,.;:-—–")

    def _drop_trailing_bad_tokens(s: str) -> str:
        """Drop trailing connectors AND any English fragments that read
        incomplete when stranded ('leg', 'free', 'flights', 'cancellation').

        Iterates a few times: drop a connector → maybe an incomplete-fragment
        is now exposed → drop that too. Capped to avoid eating the line.
        """
        for _ in range(6):
            stripped = _strip_trailing_punct(s)
            if " " not in stripped:
                return stripped
            head, tail = stripped.rsplit(" ", 1)
            tail_lower = tail.lower()
            if tail_lower in connector_words:
                s = head
                continue
            if language == "en" and tail_lower in _TRAILING_INCOMPLETE_FRAGMENTS_EN:
                s = head
                continue
            return stripped
        return _strip_trailing_punct(s)

    if len(text) <= max_chars:
        # Even when the whole string fits, normalize trailing punct so the
        # caller doesn't have to.
        return _strip_trailing_punct(text)

    conv = _LANG_CONVENTIONS.get(language, _LANG_CONVENTIONS["sv"])

    abbreviated = text
    for long_form, short_form in conv["common_abbreviations"].items():
        abbreviated = abbreviated.replace(long_form, short_form)
        abbreviated = abbreviated.replace(long_form.capitalize(), short_form.capitalize())
        if len(abbreviated) <= max_chars:
            return _strip_trailing_punct(abbreviated)

    trimmed = abbreviated
    for filler in conv["filler_words"]:
        if len(trimmed) > max_chars:
            replacement = " & " if filler in conv["ampersand_pairs"] else " "
            trimmed = trimmed.replace(filler, replacement)

    if len(trimmed) <= max_chars:
        return _strip_trailing_punct(trimmed)

    if len(trimmed) > max_chars:
        cut = trimmed[:max_chars]
        # Prefer to truncate at a sentence end if one's reasonably close
        # (within the last half of the cut). Avoids dangling action verbs.
        last_sentence_end = max(
            cut.rfind(". "), cut.rfind("! "), cut.rfind("? "),
        )
        if last_sentence_end >= int(max_chars * 0.5):
            # Keep up through the punctuation but drop the trailing space
            trimmed = cut[: last_sentence_end + 1]
        else:
            # v0.3.4: refuse the pattern when the word about to be dropped at
            # the cut is a meaning-bearing tail ('fees', 'today', 'now',
            # 'flights', etc.) — chopping it leaves a partial like
            # 'No hidden Fernando' instead of 'No hidden Fernando fees'. The
            # caller's fallback picks a shorter pattern instead.
            after_cut = trimmed[max_chars:].split(" ", 1)[0].rstrip(".,;:!?-").lower()
            if (
                language == "en"
                and after_cut in _TRAILING_INCOMPLETE_FRAGMENTS_EN
                and after_cut not in {"60", "30", "24", "10", "15"}
            ):
                return ""
            trimmed = cut.rsplit(" ", 1)[0]

    cleaned = _drop_trailing_bad_tokens(trimmed)

    # Final guard: if the result is also too aggressively short (less than
    # 50% of the budget), the caller is better off skipping this pattern
    # than shipping a fragment. Return empty string to signal "skip".
    if len(cleaned) < int(max_chars * 0.5):
        return ""

    # Price-token preservation (v0.3.4): if the input had a price anchor
    # ('$224' / '$1,299') and truncation dropped it, refuse — better to skip
    # the pattern than ship the operator's mandatory price-bearing copy
    # without the price.
    if original_prices:
        kept_prices = set(_PRICE_TOKEN_RE.findall(cleaned))
        if not kept_prices & original_prices:
            return ""

    return cleaned


# Map of legacy Swedish placeholders → equivalent English placeholders so the
# same fill routine handles both packs.
_PLACEHOLDER_ALIASES = {
    "Företag": "Company",
    "företag": "company",
    "Tjänst": "Service",
    "tjänst": "service",
    "Stad": "City",
    "stad": "city",
    "Pris": "Price",
    "Antal": "Count",
    "antal": "count",
    "Telefon": "Phone",
    "telefon": "phone",
}


_IATA_3LETTER_RE = re.compile(r"^[A-Z]{3}$")


# Tokens that, when leading or trailing a multi-word name, can be dropped to
# shorten without hurting recognition. Conservative — we don't touch the
# first SIGNIFICANT word (e.g., "San Carlos De Bariloche" → "Bariloche" would
# be too aggressive; "San Carlos De Bariloche" → "San Carlos Bariloche" by
# dropping "De" is acceptable for fit but we keep that to a last-resort
# step). Order matters: paren/comma strips first, particle strip last.
_NAME_PARTICLES_DROPPABLE: tuple[str, ...] = (
    " De La ", " De Los ", " De Las ", " Do ", " Da ", " Du ",
)


# Romance-language particles that appear INSIDE a multi-word destination name
# ("Fernando De Noronha", "San Carlos De Bariloche", "St. Denis De La Reunion").
# When the full name overflows the char budget, the destination's primary
# token is the suffix AFTER the particle (Noronha, Bariloche, La Reunion),
# never the prefix before it ("Fernando", "San Carlos", "St. Denis") which
# reads as an orphan first name.
_INTERNAL_PARTICLES_EN: frozenset[str] = frozenset({
    "de", "del", "della", "di", "do", "da", "du",
    "la", "le", "los", "las", "el",
})


def _strip_parens(s: str) -> str:
    """Drop parenthesized suffixes, e.g. 'West Palm Beach (Florida)' → 'West Palm Beach'."""
    return re.sub(r"\s*\([^)]*\)\s*", " ", s).strip()


def _shrink_name_with_particles(s: str) -> str:
    """Drop trivial connective particles when name is still too long after
    paren/comma strips. 'St. Denis De La Reunion' → 'St. Denis La Reunion'
    is mildly awkward; the chained final fallback in the generator handles
    that case by selecting a shorter candidate pattern instead.
    """
    out = s
    for particle in _NAME_PARTICLES_DROPPABLE:
        out = re.sub(particle, " ", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


def _try_destination_head_token(name: str, max_chars: int) -> str | None:
    """For 3+ word destination names, surface a short recognizable token.

    Two strategies, tried in order:

    1. Internal Romance-particle slicing — for names with an INTERNAL particle
       (De/Del/Da/La/Le/Los/etc.) the destination's primary token is the
       SUFFIX after the last particle:
         'Fernando De Noronha' → 'Noronha'
         'San Carlos De Bariloche' → 'Bariloche'
         'St. Denis De La Reunion' → 'La Reunion' (or 'Reunion' if budget tight)

    2. Last-word for 3+ word names with no particle — the OTA convention is
       that the last token is the city/region root:
         'Bandar Seri Begawan' → 'Begawan'

    Returns None when no shortened form exists OR when the only shortening
    available is the FIRST word of a multi-word name (which reads as an
    orphan first name — 'Fernando', 'San Carlos', 'Grand Cayman' have no
    last-word substitute that doesn't lose the destination's identity).

    The two-word case ('Grand Cayman', 'San Andres', 'Mineralnye Vody')
    returns None — there's no safe shortening; the caller must either fit
    the full name or skip the pattern.
    """
    tokens = name.split()
    if len(tokens) < 3:
        return None

    # 1. Internal-particle suffix — use the LAST internal particle so
    # 'St. Denis De La Reunion' surfaces 'La Reunion' (not 'Reunion'),
    # preserving the recognizable place name when budget allows.
    last_particle_idx = -1
    for i in range(1, len(tokens) - 1):
        if tokens[i].lower().rstrip(".,") in _INTERNAL_PARTICLES_EN:
            last_particle_idx = i
    if last_particle_idx > 0:
        tail = " ".join(tokens[last_particle_idx + 1:]).strip()
        if tail and len(tail) <= max_chars:
            return tail
        # Tail still too long — try just the last word (always after a
        # particle the city root is the last token).
        if tokens[-1] and len(tokens[-1]) <= max_chars and len(tokens[-1]) >= 4:
            return tokens[-1]

    # 2. Last-word for 3+ word names with no particle.
    last = tokens[-1].strip(".,")
    if last and len(last) >= 4 and len(last) <= max_chars:
        return last

    return None


def _resolve_customer_display_name(product: Product, max_chars: int) -> str:
    """Best-fitting destination NAME for a char budget — never falls back to SKU.

    v0.3.4 operator constraint: customer-facing copy NEVER shows the IATA/SKU
    code. Hierarchy:
      1. product.short_name (operator-curated)
      2. paren-stripped name ('West Palm Beach (Florida)' → 'West Palm Beach')
      3. comma-segment ('Petropavlovsk-Kamchats, Russian Federation' →
         'Petropavlovsk-Kamchats')
      4. paren-strip + comma-segment combined
      5. particle-strip ('San Carlos De Bariloche' → 'San Carlos Bariloche')
      6. head-token surfacing — for 3+ word names, slice after the internal
         particle ('Fernando De Noronha' → 'Noronha', 'San Carlos De
         Bariloche' → 'Bariloche'), or use the last word for non-particle
         3+ word names ('Bandar Seri Begawan' → 'Begawan'). This step
         prevents orphan first-name truncations downstream
         ('Fernando De Noronha' chopping to 'Fernando' inside _fit_to_limit).
      7. full product.name (caller's `_fit_to_limit` may still truncate — when
         that happens the pattern is typically rejected by the 50%-budget
         guard so the caller skips this pattern entirely)

    Returns a string that the caller can compose into a pattern; the function
    never returns the SKU and never returns an empty string when a name exists.
    """
    short = (product.short_name or "").strip()
    if short and len(short) <= max_chars:
        return short

    full = (product.name or "").strip()

    # 2. paren-strip
    no_parens = _strip_parens(full)
    if no_parens and len(no_parens) <= max_chars:
        return no_parens

    # 3. comma-segment of original
    if "," in full:
        seg = full.split(",", 1)[0].strip()
        if seg and len(seg) <= max_chars:
            return seg

    # 4. paren-strip + comma-segment
    if "," in no_parens:
        seg2 = no_parens.split(",", 1)[0].strip()
        if seg2 and len(seg2) <= max_chars:
            return seg2

    # 5. particle-strip
    base = no_parens.split(",", 1)[0].strip() if "," in no_parens else no_parens
    shrunk = _shrink_name_with_particles(base)
    if shrunk and len(shrunk) <= max_chars:
        return shrunk

    # 6. head-token surfacing — covers names where the full form overflows
    # the budget and the previous shortenings didn't help. Prevents the
    # 'Fernando' orphan that the v0.3.4 reviewer agent flagged.
    head = _try_destination_head_token(base, max_chars)
    if head:
        return head
    # Try also on the no-parens version when base was comma-trimmed.
    if base != no_parens:
        head2 = _try_destination_head_token(no_parens, max_chars)
        if head2:
            return head2

    # 7. final fallback — return whatever we have. Caller's `_fit_to_limit`
    # will reject if it can't fit. NEVER the SKU.
    return full or (short or "")


def _resolve_display_name(product: Product, max_chars: int) -> str:
    """Backward-compat shim. v0.3.4 routes everything through the no-SKU
    customer display name resolver; the previous IATA-last-resort path is
    gone (operator constraint — customer never sees the code)."""
    return _resolve_customer_display_name(product, max_chars)


def _should_use_iata_in_customer_copy(product: Product) -> bool:
    """v0.3.4: SKU/IATA NEVER appears in customer copy. Always False.

    Kept as a function (not deleted) so callers importing by name keep
    working — but the semantics are now hard-coded to False.
    """
    return False


def _compute_was_price(product: Product | None) -> tuple[int, int] | None:
    """Compute (was_price, now_price) when both fields are known.

    Returns None if either `from_price` or `discount_pct` is missing or zero.
    `was_price` is reverse-calculated from the discount so we can ship a real
    "Was $Y, now $Z" anchor that's truthful, not a hand-wavy "full price".
    """
    if product is None:
        return None
    fp = product.attributes.get("from_price")
    dp = product.attributes.get("discount_pct")
    if fp is None or dp is None:
        return None
    try:
        now_price = float(fp)
        discount = float(dp)
    except (TypeError, ValueError):
        return None
    if discount <= 0 or now_price <= 0:
        return None
    # Normalize fraction vs percent representations
    if discount > 1:
        discount = discount / 100.0
    if discount >= 1.0:
        return None  # Avoid div-by-zero (100% off => was = infinity)
    was_price = now_price / (1 - discount)
    return int(round(was_price)), int(round(now_price))


# Patterns that, when rendered, leave a sentence-fragment we should reject
# entirely rather than ship. Each regex matches the WHOLE result string after
# substitution.
_BAD_RESULT_PATTERNS = [
    re.compile(r"\$(\s|\.|,|$)"),  # bare $ followed by space, period, comma, EOS
    re.compile(r"\bfrom\s+(?:\s|\.|,|$)"),  # "from " with nothing after
    re.compile(r"^\s*\$\s*$"),  # whole line is just "$"
]

# v0.3.4: headlines that title-case into the sem-ad-copy banned phrase
# 'Cheap {name} flights' (or its variant 'Cheap flights to {name}') ship a
# disqualifying claim. Reject any line that leads with 'Cheap '. This catches
# keyword-templated fallback paths that bypass the structured pattern pack.
_BANNED_HEADLINE_PREFIX_RE = re.compile(r"^\s*Cheap\b", re.IGNORECASE)


def _is_banned_headline(text: str, language: str) -> bool:
    """Reject ad-copy lines that hit operator-banned phrases.

    Currently checks for the 'Cheap …' lead-in (FTC/ASA risk + sem-ad-copy
    skill banlist). English-only — Swedish keyword fallback uses different
    phrasing and isn't affected.
    """
    if language != "en" or not text:
        return False
    return bool(_BANNED_HEADLINE_PREFIX_RE.match(text))


def _result_has_bad_price_fragment(result: str) -> bool:
    """Return True if the rendered pattern leaks a placeholder fragment
    that would ship as visible noise (naked `$`, "from " with no number, etc.)
    """
    if not result:
        return False
    for rx in _BAD_RESULT_PATTERNS:
        if rx.search(result):
            return True
    return False


# Conservative ASCII→diacritic restoration for known names. We only apply
# whole-word matches so we never corrupt a legitimate English word.
_DIACRITIC_RESTORE_MAP = {
    "Sao Jose": "São José",
    "Sao Paulo": "São Paulo",
    "Reunion": "Réunion",
}


def _stop_slop_pass(text: str) -> str:
    """Final cleanup pass on rendered ad copy.

    1. Normalize ` - ` (hyphen with spaces) → `, ` in mid-sentence context.
       Reviewers flagged hyphen-as-em-dash as a slop tell.
    2. Restore known ASCII-flattened diacritics (Sao Paulo → São Paulo).
    3. Collapse double spaces.
    4. Strip spaces around punctuation ("a , b" → "a, b").
    """
    if not text:
        return text

    # 1. hyphen-as-pause → comma (only when surrounded by spaces, i.e. used
    # mid-sentence; we don't touch hyphenated words like "Petropavlovsk-K.")
    text = re.sub(r"\s+-\s+", ", ", text)

    # 2. restore diacritics (whole-word/phrase match only)
    for ascii_form, restored in _DIACRITIC_RESTORE_MAP.items():
        text = re.sub(r"\b" + re.escape(ascii_form) + r"\b", restored, text)

    # 3. collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)

    # 4. strip space before punctuation ("a , b" -> "a, b")
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)

    return text.strip()


def _fill_pattern(
    pattern: str,
    client: ClientProfile,
    theme: str,
    keywords: list[str],
    target_geo: GeoTarget | None = None,
    product: Product | None = None,
    language: str = "sv",
    *,
    pattern_meta: dict | None = None,
) -> str:
    """Substitute placeholders in `pattern` with concrete values.

    Adds catalog-level placeholders ({name}, {sku}, {from_price}, etc.) when a
    `Product` is supplied. Falls back to per-language defaults otherwise.

    `pattern_meta` is the pattern's full dict (with `requires_from_price`,
    `long_name_fallback`, `max_chars`, etc.). Used to honor the new schema
    flags from Agent A's pattern pack.

    Returns the rendered string, or an EMPTY STRING if the pattern can't be
    rendered cleanly — e.g. it requires a price that's null, or substitution
    leaves a visible `$`/"from " fragment. The caller skips empty results.
    """
    pattern_meta = pattern_meta or {}
    is_long_name_fallback = bool(pattern_meta.get("long_name_fallback"))
    requires_from_price = bool(pattern_meta.get("requires_from_price"))
    requires_was_price = bool(pattern_meta.get("requires_was_price"))
    # `max_chars` is the budget Google enforces on this slot. We pass it to
    # `_resolve_display_name` so it can pick the best-fitting name variant.
    max_chars = int(pattern_meta.get("max_chars") or 30)

    # Early-skip: pattern explicitly requires a from_price the product lacks.
    if product is not None and requires_from_price:
        fp = product.attributes.get("from_price")
        if fp is None:
            return ""

    # Early-skip: pattern requires a computed `was_price` anchor we can't
    # produce (i.e. discount or price is missing).
    if requires_was_price and _compute_was_price(product) is None:
        return ""

    primary_service = theme or (client.products_services[0] if client.products_services else "")
    primary_city = ""
    if target_geo is not None:
        primary_city = target_geo.name
    elif client.geographic_targets:
        primary_city = client.geographic_targets[0].name

    # Build the substitution map. Names appear in both Swedish and English
    # since some patterns mix them.
    fills: dict[str, str] = {
        "Company": client.business_name,
        "company": client.business_name.lower(),
        "Service": primary_service.capitalize(),
        "service": primary_service.lower(),
        "City": primary_city,
        "city": primary_city.lower(),
        "Price": "499",
        "Count": "100",
        "count": "10",
        "Phone": "",
        "phone": "",
        "CTA": "Contact us today" if language == "en" else "Kontakta oss idag",
    }

    # Catalog-aware substitutions — attributes first so name/sku win
    if product is not None:
        for k, v in product.attributes.items():
            if v is None:
                fills[k] = ""
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                if k == "discount_pct":
                    # Discounts in the canonical case are fractions (0.0–1.0).
                    # Render as integer percent for ad copy.
                    pct = v * 100 if v <= 1 else v
                    fills[k] = str(int(round(pct)))
                elif k.endswith("_price") or k == "price":
                    fills[k] = _format_number(v, language)
                else:
                    fills[k] = _format_number(v, language)
            else:
                fills[k] = str(v)

        # Computed price pair for "Was $Y, now $Z" anchors
        was_now = _compute_was_price(product)
        if was_now is not None:
            was_price, now_price = was_now
            fills["was_price"] = _format_number(was_price, language)
            fills["now_price"] = _format_number(now_price, language)
            fills["was_minus_now"] = _format_number(was_price - now_price, language)
        else:
            fills["was_price"] = ""
            fills["now_price"] = ""
            fills["was_minus_now"] = ""

        # name/sku precedence over any attributes of the same name.
        # For {name}, compute the ACTUAL pattern overhead (everything in the
        # pattern except {name}) so the resolver gets a true budget and can
        # surface a shorter form ('Fernando De Noronha' → 'Noronha') when
        # the pattern has high non-name overhead like
        # 'Save up to {discount_pct}% to {name}' (~18 chars of overhead).
        if "{name}" in pattern:
            overhead_template = pattern.replace("{name}", "")
            # Substitute every other resolved fill so we measure the true
            # rendered overhead, not the template length.
            for key, value in fills.items():
                if key == "name":
                    continue
                overhead_template = overhead_template.replace("{" + key + "}", str(value))
            # Strip any unresolved $name / {name} placeholders so they don't
            # inflate the overhead estimate.
            overhead_template = re.sub(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", "", overhead_template)
            overhead_template = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", "", overhead_template)
            name_budget = max_chars - len(overhead_template)
        else:
            name_budget = max_chars - 4
        # Floor at 4 chars — below that no destination token is recognizable
        # and the pattern will fail at _fit_to_limit anyway.
        name_budget = max(4, name_budget)
        fills["name"] = _resolve_customer_display_name(product, name_budget)

        # v0.3.4 operator constraint: NO SKU in customer copy. Even patterns
        # flagged `long_name_fallback: true` must use {name} (resolved via the
        # customer display-name hierarchy). {sku} placeholders are emptied so
        # any leftover legacy pattern that still references {sku} renders to
        # an empty/short string and is rejected by the downstream guards.
        fills["sku"] = ""

    # Apply alias mappings so legacy Swedish placeholders still work
    for sv_name, en_name in _PLACEHOLDER_ALIASES.items():
        if en_name in fills:
            fills[sv_name] = fills[en_name]

    result = pattern
    for key, value in fills.items():
        result = result.replace("{" + key + "}", value)

    # Drop unrecognized $name placeholders (legacy)
    result = re.sub(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", "", result)
    # Clean up sentence-final dangling punctuation
    result = re.sub(r"\s*-\s*$", "", result)
    result = re.sub(r"\s{2,}", " ", result).strip()

    # Final null-safety check: if the substitution left a naked `$` or a
    # bare "from " fragment (because from_price was null), reject the line.
    if _result_has_bad_price_fragment(result):
        return ""

    # v0.3.4 orphan-prevention guard. When the pattern uses {name} and the
    # rendered result OVERFLOWS the slot budget, `_fit_to_limit` would chop
    # the trailing word(s) — orphaning a multi-word destination as the lone
    # first word ('Save up to 46% to Mineralnye Vody' → 'Save up to 46% to
    # Mineralnye'). The resolver already tried every shortening; if the
    # multi-word name still doesn't fit, the right move is to skip this
    # pattern and let the caller try another candidate.
    if (
        product is not None
        and "{name}" in pattern
        and " " in fills.get("name", "")
        and len(result) > max_chars
    ):
        return ""

    # v0.3.4 banned-phrase guard. The sem-ad-copy skill bans 'Cheap {name}
    # flights'-style headlines. Reject any line that starts with 'Cheap '
    # to catch keyword-templated paths ('cheap flights to {name}' →
    # 'Cheap Flights to Karpathos') that title-case into the banned shape.
    if language == "en" and _BANNED_HEADLINE_PREFIX_RE.match(result):
        return ""

    return result


def generate_headlines(
    ad_group_theme: str,
    client: ClientProfile,
    keywords: list[str],
    llm_headlines: list[str] | None = None,
    target_geo: GeoTarget | None = None,
    product: Product | None = None,
) -> list[AdHeadline]:
    """Up to 15 max-30-char headlines for an ad group."""
    language = client.language
    patterns_data = _load_json("ad_copy_patterns.json", language)
    cta_data = _load_json("cta_phrases.json", language)

    headline_patterns = patterns_data.get("headline_patterns", [])
    headlines: list[AdHeadline] = []
    seen_texts: set[str] = set()

    def _add(text: str) -> bool:
        text = _apply_language_rules(text, language)
        text = _fit_to_limit(text, 30, language)
        if not text or len(text) > 30:
            return False
        # Case-insensitive dedup so 'Karpathos Flights' + 'Karpathos flights'
        # don't both ship in the same variant (Google's RSA optimizer dampens
        # ad strength on near-duplicates).
        key = text.casefold()
        if key in seen_texts:
            return False
        seen_texts.add(key)
        headlines.append(AdHeadline(text=text))
        return True

    # 1. Brand
    _add(client.business_name)

    # 2. Service / theme — for catalog mode, prefer the product name
    if product is not None and product.name:
        _add(product.name)
    else:
        _add(ad_group_theme.capitalize())

    # 3. LLM-generated
    for llm_text in llm_headlines or []:
        if len(headlines) >= 15:
            break
        _add(llm_text)

    # 4. Template patterns
    for pat in headline_patterns:
        if len(headlines) >= 15:
            break
        filled = _fill_pattern(
            pat["pattern"], client, ad_group_theme, keywords,
            target_geo, product, language,
            pattern_meta=pat,
        )
        _add(filled)

    # 5. CTA categories
    for category in ("quote", "contact", "book", "travel"):
        if len(headlines) >= 15:
            break
        for phrase in cta_data.get(category, [])[:2]:
            if len(headlines) >= 15:
                break
            _add(phrase)

    # 6. Keyword-based — title-case for English so "cheap flights to hartford" →
    # "Cheap Flights to Hartford". v0.3.4: filter out the banned 'Cheap …' lead-in
    # (FTC/ASA risk) before adding; keywords like "cheap flights to {name}" are
    # legitimate match terms but never ship as headline copy.
    for kw in keywords[:5]:
        if len(headlines) >= 15:
            break
        cand = _title_case_keyword(kw)
        if _is_banned_headline(cand, language):
            continue
        _add(cand)

    # 7. Geo
    geo_sources: list[GeoTarget] = (
        [target_geo] if target_geo is not None else list(client.geographic_targets[:2])
    )
    for geo in geo_sources:
        if len(headlines) >= 15:
            break
        in_word = "in" if language == "en" else "i"
        _add(f"{ad_group_theme.capitalize()} {in_word} {geo.name}")
        _add(f"{geo.name} - {ad_group_theme.capitalize()}")

    logger.info("Generated %d headlines for ad group '%s'", len(headlines), ad_group_theme)
    return headlines[:15]


def generate_descriptions(
    ad_group_theme: str,
    client: ClientProfile,
    keywords: list[str],
    llm_descriptions: list[str] | None = None,
    target_geo: GeoTarget | None = None,
    product: Product | None = None,
) -> list[AdDescription]:
    """Up to 4 max-90-char descriptions for an ad group."""
    language = client.language
    patterns_data = _load_json("ad_copy_patterns.json", language)
    description_patterns = patterns_data.get("description_patterns", [])

    descriptions: list[AdDescription] = []
    seen: set[str] = set()

    def _add(text: str) -> bool:
        text = _apply_language_rules(text, language)
        text = _fit_to_limit(text, 90, language)
        if not text or len(text) > 90:
            return False
        key = text.casefold()
        if key in seen:
            return False
        seen.add(key)
        descriptions.append(AdDescription(text=text))
        return True

    for llm_text in llm_descriptions or []:
        if len(descriptions) >= 4:
            break
        _add(llm_text)

    for pat in description_patterns:
        if len(descriptions) >= 4:
            break
        filled = _fill_pattern(
            pat["pattern"], client, ad_group_theme, keywords,
            target_geo, product, language,
            pattern_meta=pat,
        )
        _add(filled)

    # Fallback templates per language
    if language == "en":
        name_for_fallback = product.name if product else ad_group_theme.lower()
        fallbacks = [
            f"Professional {ad_group_theme.lower()} at great prices. Contact us for a free quote.",
            f"{client.business_name} offers {name_for_fallback}. Get in touch today for details.",
            f"Need {name_for_fallback}? We help you fast and professionally.",
            f"Book {name_for_fallback} online. Quick service and satisfaction guaranteed.",
        ]
    else:
        fallbacks = [
            f"Professionell {ad_group_theme.lower()} till bra priser. Kontakta oss för en kostnadsfri offert.",
            f"{client.business_name} erbjuder {ad_group_theme.lower()}. Ring oss idag för mer information.",
            f"Behöver du {ad_group_theme.lower()}? Vi hjälper dig snabbt och professionellt.",
            f"Boka {ad_group_theme.lower()} online. Snabb service och nöjd kund-garanti.",
        ]
    for fb in fallbacks:
        if len(descriptions) >= 4:
            break
        _add(fb)

    logger.info("Generated %d descriptions for ad group '%s'", len(descriptions), ad_group_theme)
    return descriptions[:4]


def generate_rsa(
    ad_group_theme: str,
    client: ClientProfile,
    keywords: list[str],
    final_url: str,
    target_geo: GeoTarget | None = None,
    product: Product | None = None,
) -> ResponsiveSearchAd:
    """Generate a full RSA. When `product` is set, per-row interpolation kicks in."""
    llm_headlines, llm_descriptions = llm_ad_copy.generate_llm_ad_copy(
        client, ad_group_theme, keywords, target_geo=target_geo, product=product,
    )
    headlines = generate_headlines(
        ad_group_theme, client, keywords, llm_headlines, target_geo, product,
    )
    descriptions = generate_descriptions(
        ad_group_theme, client, keywords, llm_descriptions, target_geo, product,
    )

    # URL paths derived from theme (or product name when catalog-driven)
    if product is not None and product.name:
        path_basis = product.name.lower().split()
    else:
        path_basis = ad_group_theme.lower().split()
    path1 = _fit_to_limit(path_basis[0] if path_basis else "", 15, client.language)
    path2 = _fit_to_limit(path_basis[1] if len(path_basis) > 1 else "", 15, client.language)

    if len(headlines) < 3:
        while len(headlines) < 3:
            headlines.append(AdHeadline(text=f"{ad_group_theme[:30]}"))
    if len(descriptions) < 2:
        while len(descriptions) < 2:
            descriptions.append(AdDescription(text=f"{client.business_name} - {ad_group_theme}"[:90]))

    return ResponsiveSearchAd(
        headlines=headlines,
        descriptions=descriptions,
        final_url=final_url,
        path1=path1,
        path2=path2,
    )


# ---------------------------------------------------------------------------
# Multi-variant RSA generation (v0.3.2)
# ---------------------------------------------------------------------------


# Canonical variant order. `discount_led` is conditional on discount_pct>0 —
# emitted as the second variant when applicable so high-discount destinations
# lead with the angle most likely to win the auction.
VARIANT_ORDER: tuple[str, ...] = (
    "price_led",
    "discount_led",
    "social_proof",
    "urgency",
    "loss_aversion",
)

# When the discount variant is skipped we still emit 4 variants (no loss).
NON_DISCOUNT_VARIANTS: tuple[str, ...] = (
    "price_led",
    "social_proof",
    "urgency",
    "loss_aversion",
)

# Minimum / maximum RSAs per ad group, per the requirement "3-5 variants
# per destination". Floors at 3 even for products missing both price and
# discount data so Pydantic still validates.
MIN_VARIANTS = 3
MAX_VARIANTS = 5


def _product_has_discount(product: Product | None) -> bool:
    """True when the product carries a discount large enough to lead a variant.

    Reviewers flagged that the `discount_led` variant was emitting even at
    5–11% off, where the % is too small to be a hook. We floor at
    `MIN_DISCOUNT_PCT_FOR_DISCOUNT_LED` (0.15) — below that, the variant
    falls back to `loss_aversion` and the slot stays useful instead of
    shipping a weak number.
    """
    if product is None:
        return False
    dp = product.attributes.get("discount_pct")
    if dp is None:
        return False
    try:
        value = float(dp)
    except (TypeError, ValueError):
        return False
    # Normalize percent-vs-fraction representations
    if value > 1:
        value = value / 100.0
    return value >= MIN_DISCOUNT_PCT_FOR_DISCOUNT_LED


def _format_discount_pct_str(product: Product) -> str:
    """Render discount as an integer-percent string (e.g. '38')."""
    dp = product.attributes.get("discount_pct")
    if dp is None:
        return ""
    try:
        v = float(dp)
    except (TypeError, ValueError):
        return ""
    pct = v * 100 if v <= 1 else v
    return str(int(round(pct)))


def _variants_for_product(product: Product | None) -> list[str]:
    """Decide which variants to emit for this product.

    Returns 3-5 variant role names. The discount variant is included iff
    `discount_pct > 0`. Order matches `VARIANT_ORDER` so higher-confidence
    variants are pushed to Google first.
    """
    if _product_has_discount(product):
        return list(VARIANT_ORDER)
    return list(NON_DISCOUNT_VARIANTS)


def _select_variant_headline_patterns(
    patterns_data: dict, variant_role: str,
) -> list[dict]:
    """Pull patterns from the variant block, falling back to legacy / universal."""
    variants_block = patterns_data.get("variants", {})
    variant = variants_block.get(variant_role, {})
    return list(variant.get("headline_patterns", []))


def _select_variant_description_patterns(
    patterns_data: dict, variant_role: str,
) -> list[dict]:
    variants_block = patterns_data.get("variants", {})
    variant = variants_block.get(variant_role, {})
    return list(variant.get("description_patterns", []))


def _select_variant_cta(patterns_data: dict, variant_role: str) -> list[dict]:
    variants_block = patterns_data.get("variants", {})
    variant = variants_block.get(variant_role, {})
    return list(variant.get("cta_pinned", []))


def _select_variant_tail_headlines(
    patterns_data: dict, variant_role: str,
) -> list[dict]:
    """Pattern-pack v3 introduces `tail_headlines` — 1-2 role-specific lines
    used to differentiate H14/H15 per variant. Reviewers flagged that H14/H15
    were universal-copy clones across variants.
    """
    variants_block = patterns_data.get("variants", {})
    variant = variants_block.get(variant_role, {})
    return list(variant.get("tail_headlines", []))


def _select_variant_pattern_interrupt_h4(
    patterns_data: dict, variant_role: str,
) -> list[dict]:
    """Pattern-pack v3: each variant suggests a `pattern_interrupt_h4` line
    we elevate to position H4 so every variant leads with a Flightnetwork-
    specific moat instead of competitor-parity copy.
    """
    variants_block = patterns_data.get("variants", {})
    variant = variants_block.get(variant_role, {})
    return list(variant.get("pattern_interrupt_h4", []))


def _universal_headline_patterns(patterns_data: dict) -> list[dict]:
    return list(patterns_data.get("universal", {}).get("headline_patterns", []))


def _universal_description_patterns(patterns_data: dict) -> list[dict]:
    return list(patterns_data.get("universal", {}).get("description_patterns", []))


def _long_name_headline_patterns(patterns_data: dict) -> list[dict]:
    """Pattern-pack v3 block: SKU-substituted patterns for destinations whose
    full name overflows the headline budget."""
    return list(
        patterns_data
        .get("long_name_fallback_patterns", {})
        .get("headline_patterns", [])
    )


def _long_name_description_patterns(patterns_data: dict) -> list[dict]:
    return list(
        patterns_data
        .get("long_name_fallback_patterns", {})
        .get("description_patterns", [])
    )


# Threshold at which we treat a destination name as "long" — switches the
# generator into the IATA-fallback / short-name path.
_LONG_NAME_THRESHOLD = 18


def _product_has_long_name(product: Product | None) -> bool:
    if product is None or not product.name:
        return False
    return len(product.name) >= _LONG_NAME_THRESHOLD


def generate_headlines_for_variant(
    variant_role: str,
    ad_group_theme: str,
    client: ClientProfile,
    keywords: list[str],
    *,
    llm_headlines: list[str] | None = None,
    target_geo: GeoTarget | None = None,
    product: Product | None = None,
    pinned_cta_text: str | None = None,
    require_discount_mention: bool = False,
) -> list[AdHeadline]:
    """Generate up to 15 headlines anchored to one variant role.

    Pinning layout (model layer pins H1-H3, optionally H4):
      H1 = brand
      H2 = destination
      H3 = variant-specific CTA
      H4 = pattern_interrupt_h4 (Flightnetwork-specific moat)
      H5..H15 = unpinned mix of variant + tail + universal patterns

    Per-variant tail headlines (`tail_headlines`) ensure H14/H15 differ
    between variants — fixes the H14/H15-clone bug Reviewer D flagged.

    For long destination names (>=18 chars), prefer
    `long_name_fallback_patterns` and IATA-substituted variants so headlines
    never truncate to one-word fragments like "Compare" or "Avoid PKC".

    When `require_discount_mention=True` (discount_led variant), at least one
    headline carries the discount percent — but capped at
    `MAX_DISCOUNT_PCT_HEADLINES` to avoid Google's semantic-similarity
    penalty.
    """
    language = client.language
    patterns_data = _load_json("ad_copy_patterns.json", language)

    headlines: list[AdHeadline] = []
    seen_texts: set[str] = set()

    long_name = _product_has_long_name(product)
    pct_str = _format_discount_pct_str(product) if product else ""
    is_discount_variant = require_discount_mention

    def _count_pct_headlines() -> int:
        if not pct_str:
            return 0
        return sum(1 for h in headlines if pct_str in h.text)

    def _would_exceed_pct_cap(text: str) -> bool:
        """Discount_led: refuse to add another %-bearing headline once we've
        hit the cap. The cap-driven slots are filled by universal/tail copy.
        """
        if not is_discount_variant or not pct_str or pct_str not in text:
            return False
        return _count_pct_headlines() >= MAX_DISCOUNT_PCT_HEADLINES

    def _add(text: str) -> bool:
        text = _apply_language_rules(text, language)
        text = _fit_to_limit(text, 30, language)
        if not text or len(text) > 30:
            return False
        # Case-insensitive dedup — see generate_headlines() for the
        # rationale. RSA optimizer treats 'Karpathos Flights' and
        # 'Karpathos flights' as semantic dupes; ship neither side-by-side.
        key = text.casefold()
        if key in seen_texts:
            return False
        if _would_exceed_pct_cap(text):
            return False
        seen_texts.add(key)
        headlines.append(AdHeadline(text=text))
        return True

    # H1 — brand
    _add(client.business_name)

    # H2 — destination / theme. For long names, prefer the resolved display
    # name (short_name → comma-segment → IATA) so H2 doesn't truncate either.
    if product is not None and product.name:
        h2 = _resolve_display_name(product, 30) if long_name else product.name
        _add(h2)
    else:
        _add(ad_group_theme.capitalize())

    # H3 — variant-specific CTA (pinned). When the CTA pattern references
    # {discount_pct} we still want to render it even though it WILL count
    # toward the pct cap; this is the one mandated mention of the percent.
    if pinned_cta_text:
        filled_cta = _fill_pattern(
            pinned_cta_text, client, ad_group_theme, keywords,
            target_geo, product, language,
            pattern_meta={"max_chars": 30},
        )
        _add(filled_cta)

    # H4 — pattern_interrupt_h4 (variant-specific moat headline)
    h4_patterns = _select_variant_pattern_interrupt_h4(patterns_data, variant_role)
    for pat in h4_patterns:
        if len(headlines) >= 15:
            break
        filled = _fill_pattern(
            pat["pattern"], client, ad_group_theme, keywords,
            target_geo, product, language, pattern_meta=pat,
        )
        if _add(filled):
            break  # one H4 is enough

    # H5+ — long-name fallback (only when name is long) — these inject SKU as
    # the destination token because the full name doesn't fit.
    if long_name:
        for pat in _long_name_headline_patterns(patterns_data):
            if len(headlines) >= 15:
                break
            filled = _fill_pattern(
                pat["pattern"], client, ad_group_theme, keywords,
                target_geo, product, language, pattern_meta=pat,
            )
            _add(filled)

    # H4+ — LLM suggestions tagged for this variant
    for llm_text in llm_headlines or []:
        if len(headlines) >= 15:
            break
        _add(llm_text)

    # Variant-specific templated patterns
    variant_patterns = _select_variant_headline_patterns(patterns_data, variant_role)
    for pat in variant_patterns:
        if len(headlines) >= 15:
            break
        filled = _fill_pattern(
            pat["pattern"], client, ad_group_theme, keywords,
            target_geo, product, language, pattern_meta=pat,
        )
        _add(filled)

    # Computed "Was $Y, now $Z" anchor for discount variants (S1-2). The
    # pattern is generated on-the-fly so it stays truthful — was_price is
    # back-calculated from from_price + discount_pct.
    if is_discount_variant and len(headlines) < 15:
        was_now = _compute_was_price(product)
        if was_now is not None:
            was_p, now_p = was_now
            anchor = f"Was ${was_p}, now ${now_p}"
            if len(anchor) <= 30:
                _add(anchor)

    # Variant-specific `tail_headlines` — give H14/H15 a role flavor instead
    # of cloning universals across all variants (S1-14).
    tail_patterns = _select_variant_tail_headlines(patterns_data, variant_role)
    for pat in tail_patterns:
        if len(headlines) >= 15:
            break
        filled = _fill_pattern(
            pat["pattern"], client, ad_group_theme, keywords,
            target_geo, product, language, pattern_meta=pat,
        )
        _add(filled)

    # Universal patterns as filler so each variant still reaches "Excellent"
    # ad strength (15 headlines).
    universal_patterns = _universal_headline_patterns(patterns_data)
    for pat in universal_patterns:
        if len(headlines) >= 15:
            break
        filled = _fill_pattern(
            pat["pattern"], client, ad_group_theme, keywords,
            target_geo, product, language, pattern_meta=pat,
        )
        _add(filled)

    # Final safety net: top up from keywords if we're short. Use title case
    # for English so "cheap flights to hartford" → "Cheap Flights to Hartford"
    # (and avoid the lowercase-trailing-name look the consolidated review
    # flagged on the HFD/H15 sample). v0.3.4: filter banned 'Cheap …' lead-ins.
    for kw in keywords[:5]:
        if len(headlines) >= 15:
            break
        cand = _title_case_keyword(kw)
        if _is_banned_headline(cand, language):
            continue
        _add(cand)

    # Discount-mention contract — only enforced for discount_led variants.
    # v0.3.4 operator brief: at least one headline MUST carry the canonical
    # 'Save up to {pct}% to {name}' shape (with fit-aware fallback to shorter
    # name-bearing variants — NEVER substituting the SKU). On top of that we
    # guarantee at least 3 discount mentions total, capped by
    # MAX_DISCOUNT_PCT_HEADLINES so Google's semantic-similarity check
    # doesn't dampen the ad.
    if require_discount_mention and product is not None and pct_str:
        # 1. Mandatory 'Save up to X% to NAME' (or fit-aware fallback). The
        # candidate list is ordered: canonical first, then progressively
        # shorter while still surfacing the destination by name.
        save_already_present = any(
            h.text.lower().startswith(f"save up to {pct_str}%") for h in headlines
        )
        if not save_already_present:
            # Try a sequence of budgets so we always emit a name-bearing line.
            # Each entry: (template, name_budget). Pick the first that fits 30.
            #
            # name_budget = 30 - len(template_overhead). The generator picks
            # the best-fitting name variant given the budget via
            # `_resolve_customer_display_name`, so e.g. 'West Palm Beach
            # (Florida)' becomes 'West Palm Beach' before composing.
            save_candidates = [
                # Canonical phrasing — keeps the operator's "Save up to X%" hedge.
                ("Save up to {pct}% to {name}", 30 - len("Save up to 99% to ")),
                # "to" → "on" trims one char.
                ("Save up to {pct}% on {name}", 30 - len("Save up to 99% on ")),
                # Drop "up to" (still FTC-safe since discount is the exact pct).
                ("Save {pct}% on {name}", 30 - len("Save 99% on ")),
                # Drop preposition entirely.
                ("Save {pct}% {name}", 30 - len("Save 99% ")),
                # Sale-line composition — destination prefix.
                ("{name} -{pct}%", 30 - len(" -99%")),
                ("{name}: save {pct}%", 30 - len(": save 99%")),
                # Final fallback: name-stripped. Acceptable because the
                # destination is pinned at H2 — the slot still earns its
                # "discount + save" intent without the name. We keep the
                # 'Save up to X%' shape so the canonical phrasing survives.
                ("Save up to {pct}% today", 0),
            ]
            for template, name_budget in save_candidates:
                if "{name}" in template:
                    nm = _resolve_customer_display_name(product, max(8, name_budget))
                    if not nm:
                        continue
                    candidate = template.format(pct=pct_str, name=nm)
                else:
                    nm = ""
                    candidate = template.format(pct=pct_str)
                forced = _fit_to_limit(candidate, 30, language)
                if not forced or pct_str not in forced or forced in seen_texts:
                    continue
                # v0.3.4 orphan guard: if the resolved name is multi-word, all
                # its words must survive truncation. Otherwise we'd ship
                # 'Save up to 46% to Mineralnye' (orphaned first word). Walk
                # the candidate ladder until a fully name-preserving shape
                # fits, or until the no-name fallback ('Save up to {pct}% today').
                if nm and " " in nm:
                    name_words = nm.split()
                    if not all(w in forced for w in name_words):
                        continue
                if len(headlines) < 15:
                    headlines.append(AdHeadline(text=forced))
                else:
                    headlines[-1] = AdHeadline(text=forced)
                seen_texts.add(forced)
                break

        # 2. Top-up to the 3-mention floor. Same name-resolved candidates,
        # never the SKU. The mandatory line above already counts toward the
        # floor when it surfaced.
        attempts = 0
        while _count_pct_headlines() < min(3, MAX_DISCOUNT_PCT_HEADLINES) and attempts < 4:
            attempts += 1
            nm_short = _resolve_customer_display_name(product, 20)
            candidates = [
                f"Save {pct_str}% on {nm_short}",
                f"{pct_str}% off {nm_short}",
                f"{nm_short} -{pct_str}%",
            ]
            added = False
            for cand in candidates:
                forced = _fit_to_limit(cand, 30, language)
                if not forced or pct_str not in forced or forced in seen_texts:
                    continue
                if len(headlines) < 15:
                    headlines.append(AdHeadline(text=forced))
                else:
                    headlines[-1] = AdHeadline(text=forced)
                seen_texts.add(forced)
                added = True
                break
            if not added:
                break

    # Ensure RSA minimum
    while len(headlines) < 3:
        fallback = _fit_to_limit(
            f"{client.business_name} - {ad_group_theme[:18]}", 30, language,
        )
        if not fallback or fallback in seen_texts:
            fallback = f"{client.business_name[:30]}"
        if fallback in seen_texts:
            fallback = ad_group_theme[:30] or client.business_name[:30]
        seen_texts.add(fallback)
        headlines.append(AdHeadline(text=fallback))

    return headlines[:15]


def generate_descriptions_for_variant(
    variant_role: str,
    ad_group_theme: str,
    client: ClientProfile,
    keywords: list[str],
    *,
    llm_descriptions: list[str] | None = None,
    target_geo: GeoTarget | None = None,
    product: Product | None = None,
    require_discount_mention: bool = False,
) -> list[AdDescription]:
    """Generate up to 4 descriptions anchored to one variant role.

    For long destination names (>=18 chars), the long-name fallback block is
    preferred over the variant block — those patterns reference {sku} so they
    fit the budget without truncating "Petropavlovsk-Kamchatsky" mid-word.
    """
    language = client.language
    patterns_data = _load_json("ad_copy_patterns.json", language)
    long_name = _product_has_long_name(product)

    descriptions: list[AdDescription] = []
    seen: set[str] = set()

    def _add(text: str) -> bool:
        text = _apply_language_rules(text, language)
        text = _fit_to_limit(text, 90, language)
        if not text or len(text) > 90:
            return False
        key = text.casefold()
        if key in seen:
            return False
        seen.add(key)
        descriptions.append(AdDescription(text=text))
        return True

    for llm_text in llm_descriptions or []:
        if len(descriptions) >= 4:
            break
        _add(llm_text)

    # Long-name fallback descriptions (SKU-substituted) come first when the
    # full name would overflow the 90-char budget.
    if long_name:
        for pat in _long_name_description_patterns(patterns_data):
            if len(descriptions) >= 4:
                break
            filled = _fill_pattern(
                pat["pattern"], client, ad_group_theme, keywords,
                target_geo, product, language, pattern_meta=pat,
            )
            _add(filled)

    variant_patterns = _select_variant_description_patterns(patterns_data, variant_role)
    for pat in variant_patterns:
        if len(descriptions) >= 4:
            break
        filled = _fill_pattern(
            pat["pattern"], client, ad_group_theme, keywords,
            target_geo, product, language, pattern_meta=pat,
        )
        _add(filled)

    universal_patterns = _universal_description_patterns(patterns_data)
    for pat in universal_patterns:
        if len(descriptions) >= 4:
            break
        filled = _fill_pattern(
            pat["pattern"], client, ad_group_theme, keywords,
            target_geo, product, language, pattern_meta=pat,
        )
        _add(filled)

    # Discount-mention contract for discount_led variants
    if require_discount_mention and product is not None:
        pct_str = _format_discount_pct_str(product)
        if pct_str and not any(pct_str in d.text for d in descriptions):
            # Prefer short-name when the full name would push us over.
            name_for_desc = _resolve_customer_display_name(product, 50)
            forced = _fit_to_limit(
                f"Save {pct_str}% on {name_for_desc} flights. Compare 800+ airlines, book in 60 seconds.",
                90, language,
            )
            if pct_str in forced:
                if len(descriptions) < 4:
                    descriptions.append(AdDescription(text=forced))
                else:
                    descriptions[-1] = AdDescription(text=forced)

    # Ensure RSA minimum
    while len(descriptions) < 2:
        fallback = _fit_to_limit(
            f"{client.business_name} - {ad_group_theme}", 90, language,
        )
        if fallback in seen:
            fallback = (f"Compare flights to {ad_group_theme} from 800+ airlines.")[:90]
        seen.add(fallback)
        descriptions.append(AdDescription(text=fallback))

    return descriptions[:4]


def _pick_variant_cta_text(patterns_data: dict, variant_role: str, idx: int = 0) -> str | None:
    """Pick the H3 CTA for a variant. Falls back to a generic CTA if missing."""
    ctas = _select_variant_cta(patterns_data, variant_role)
    if ctas:
        return ctas[idx % len(ctas)].get("pattern")
    return None


_PATH_GENERIC_GEO_PREFIXES = {
    "san", "santa", "sao", "new", "north", "south", "east", "west",
    "ft", "fort", "port", "saint", "st",
}


def _grow_path_segment(words: list[str], max_chars: int) -> tuple[str, int]:
    """Greedily concat words while staying ≤ max_chars (no internal spaces —
    Google Ads display paths render '-' as separators visually but we use
    the raw word concatenation here for character budget). Returns
    (segment, words_consumed)."""
    if not words:
        return "", 0
    out = words[0]
    consumed = 1
    if len(out) > max_chars:
        # First word alone overflows — use a clean word-boundary slice
        # (no mid-syllable chop). Already a single word, so just truncate
        # to max_chars; this preserves the v0.3.4 behaviour for genuine
        # over-budget tokens. Path columns are display-only.
        return out[:max_chars], 1
    # Try extending with subsequent words.
    while consumed < len(words):
        nxt = words[consumed]
        joined = out + nxt  # no separator — display path is a single token
        if len(joined) > max_chars:
            break
        out = joined
        consumed += 1
    return out, consumed


def _resolve_path1_path2(
    ad_group_theme: str, product: Product | None, language: str,
) -> tuple[str, str]:
    # v0.3.7: replace hyphens with spaces (not empty) so 'Petropavlovsk-
    # Kamchatsky' becomes ['petropavlovsk', 'kamchatsky'] instead of
    # being chopped to 'petropavlovskka' at char 15. Then grow Path 1
    # word-by-word so multi-word names that fit in 15 chars
    # ('westpalmbeach' = 13) stay whole instead of degrading to 'west'.
    if product is not None and product.name:
        cleaned = re.sub(r"[^A-Za-z0-9]+", " ", product.name).strip().lower()
        words = cleaned.split()
    else:
        words = ad_group_theme.lower().split()
    # For generic-prefix destinations (West Palm Beach, San Carlos De
    # Bariloche), the first word alone is too generic for a URL display
    # path. Skip the generic prefix if the rest of the name still has
    # meaningful tokens to grow from.
    if (
        len(words) >= 2
        and words[0] in _PATH_GENERIC_GEO_PREFIXES
        # Don't strip if the second word is also a particle/connector.
        and words[1] not in _PATH_GENERIC_GEO_PREFIXES
    ):
        words = words[1:]
    path1, consumed = _grow_path_segment(words, 15)
    path1 = _fit_to_limit(path1, 15, language)
    remaining = words[consumed:]
    path2_raw, _ = _grow_path_segment(remaining, 15)
    path2 = _fit_to_limit(path2_raw, 15, language)
    if not path1 and product is not None:
        path1 = _fit_to_limit(product.sku.lower(), 15, language)
    return path1, path2


def generate_rsa_variants(
    ad_group_theme: str,
    client: ClientProfile,
    keywords: list[str],
    final_url: str | None = None,
    *,
    target_geo: GeoTarget | None = None,
    product: Product | None = None,
    variant_roles: list[str] | None = None,
    final_url_template: str | None = None,
    text_n_range: tuple[int, int] = (1, 5),
) -> list[ResponsiveSearchAd]:
    """Generate 3-5 distinct RSAs for one ad group.

    Each variant anchors a different psychological lever:
      - `price_led` - specificity + friction removal
      - `discount_led` - loss aversion + scarcity (requires discount_pct>0)
      - `social_proof` - authority + risk reversal
      - `urgency` - scarcity + specificity
      - `loss_aversion` - pain + friction removal

    When `discount_pct == 0` the discount variant is dropped, yielding 4
    variants. Caller can override by passing `variant_roles` explicitly.

    All variants share the same brand/destination pin pair (H1, H2) but
    differ in pinned H3 CTA, lever stack, and unpinned headline mix. Each
    variant guarantees a unique headline-set fingerprint (no two variants
    have identical headline lists) - this is what enables Google's RSA
    optimizer to pick the best combination per query.

    **v0.3.4 URL contract:** when `final_url_template` is provided, each
    variant gets its OWN `text=N` URL — variant index 0 → text=N_low,
    variant 1 → N_low+1, etc., wrapping at `text_n_range[1]`. The operator
    treats `text=N` as the variant identifier in analytics, so two RSAs in
    the same ad group never share the same `text=` value (unless
    `text_n_range` is narrower than the variant count, in which case wrap is
    intentional and the operator accepts the collision).

    When `final_url_template` is omitted, the legacy `final_url` is used for
    every variant (non-catalog code paths and direct test callers).

    **v0.3.4 from_price contract:** when product.from_price is known and no
    rendered variant surfaces the price string, a price-bearing headline +
    description are force-injected into the price_led variant (or the first
    variant present, when price_led is absent).

    Returns 3-5 ResponsiveSearchAd objects.
    """
    if variant_roles is None:
        variant_roles = _variants_for_product(product)

    if len(variant_roles) < MIN_VARIANTS:
        # Defensive: pad with extras from VARIANT_ORDER so we always emit
        # at least MIN_VARIANTS distinct angles.
        for role in VARIANT_ORDER:
            if role not in variant_roles:
                variant_roles.append(role)
            if len(variant_roles) >= MIN_VARIANTS:
                break
    variant_roles = variant_roles[:MAX_VARIANTS]

    patterns_data = _load_json("ad_copy_patterns.json", client.language)
    path1, path2 = _resolve_path1_path2(ad_group_theme, product, client.language)

    # Per-variant URL resolution. When a template is provided we render one
    # URL per variant index so each RSA carries a distinct `text=N`. The
    # range is [low, high]; with 5 variants and range (1,5) you get
    # text=1..text=5. Wrap is intentional when range < variant count.
    low_n, high_n = text_n_range
    n_span = max(1, high_n - low_n + 1)

    def _variant_final_url(variant_idx: int) -> str:
        if final_url_template and product is not None:
            from src.catalog.url_templating import expand_url_template
            n = low_n + (variant_idx % n_span)
            return expand_url_template(final_url_template, product, n=n)
        return final_url or str(client.website_url)

    # LLM is queried once per variant role with the role passed in — gives
    # the LLM a chance to lead with the variant's primary lever. When the
    # LLM is disabled or fails, the deterministic templates still cover.
    rsas: list[ResponsiveSearchAd] = []
    seen_headline_fingerprints: set[tuple[str, ...]] = set()
    for variant_idx, variant_role in enumerate(variant_roles):
        is_discount_variant = variant_role == "discount_led"

        # If the variant requires discount but the product has none, skip
        if is_discount_variant and not _product_has_discount(product):
            continue

        llm_headlines, llm_descriptions = llm_ad_copy.generate_llm_ad_copy(
            client, ad_group_theme, keywords,
            target_geo=target_geo, product=product,
            variant_role=variant_role,
        )

        pinned_cta = _pick_variant_cta_text(patterns_data, variant_role)
        headlines = generate_headlines_for_variant(
            variant_role, ad_group_theme, client, keywords,
            llm_headlines=llm_headlines, target_geo=target_geo, product=product,
            pinned_cta_text=pinned_cta,
            require_discount_mention=is_discount_variant,
        )
        descriptions = generate_descriptions_for_variant(
            variant_role, ad_group_theme, client, keywords,
            llm_descriptions=llm_descriptions, target_geo=target_geo, product=product,
            require_discount_mention=is_discount_variant,
        )

        # Headline fingerprint dedupes accidental identical variants (e.g.
        # when a pattern pack is sparse for one role and falls back to the
        # universal pool only). We replace the last headline with a role-tag
        # to force differentiation.
        fingerprint = tuple(h.text for h in headlines)
        if fingerprint in seen_headline_fingerprints:
            tag = _fit_to_limit(
                f"{variant_role.replace('_', ' ').title()}", 30, client.language,
            )
            if tag and not any(h.text == tag for h in headlines):
                if len(headlines) >= 15:
                    headlines[-1] = AdHeadline(text=tag)
                else:
                    headlines.append(AdHeadline(text=tag))
                fingerprint = tuple(h.text for h in headlines)
        seen_headline_fingerprints.add(fingerprint)

        rsas.append(
            ResponsiveSearchAd(
                headlines=headlines,
                descriptions=descriptions,
                final_url=_variant_final_url(variant_idx),
                path1=path1,
                path2=path2,
            )
        )

    # ----------------------------------------------------------------------
    # From-price guarantee (v0.3.4). When the product has a known from_price
    # but none of the rendered variants surface it (e.g., long-name patterns
    # got rejected by the fit guard), force-inject the operator's example
    # description + a complementary headline into the variant most aligned
    # with price messaging (price_led if present; else the first variant).
    # ----------------------------------------------------------------------
    if product is not None and rsas:
        fp_raw = product.attributes.get("from_price")
        if fp_raw is not None:
            try:
                fp_val = float(fp_raw)
            except (TypeError, ValueError):
                fp_val = None
            if fp_val is not None and fp_val > 0:
                fp_str = _format_number(fp_val, client.language)
                price_token = f"${fp_str}"

                def _rsa_mentions_price(ad: ResponsiveSearchAd) -> bool:
                    if any(price_token in h.text for h in ad.headlines):
                        return True
                    if any(price_token in d.text for d in ad.descriptions):
                        return True
                    return False

                if not any(_rsa_mentions_price(rsa) for rsa in rsas):
                    target_idx = 0
                    for i, role in enumerate(variant_roles[: len(rsas)]):
                        if role == "price_led":
                            target_idx = i
                            break
                    target = rsas[target_idx]

                    nm_for_desc = _resolve_customer_display_name(product, 60)
                    nm_for_head = _resolve_customer_display_name(
                        product, max(8, 30 - len(f" from {price_token}")),
                    )

                    # Force-inject the description even if all 4 slots are
                    # taken (replace the last). Per the operator's brief
                    # this is mandatory copy when from_price is known.
                    desc_candidates = [
                        f"Get a great deal on flights to {nm_for_desc} with prices from {price_token}.",
                        f"Flights to {nm_for_desc} from {price_token}. Compare 800+ airlines.",
                        f"Real-time {nm_for_desc} fares from {price_token}. Free 24h cancellation.",
                    ]
                    desc_seen = {d.text for d in target.descriptions}
                    desc_to_add: str | None = None
                    for cand in desc_candidates:
                        fit = _fit_to_limit(cand, 90, client.language)
                        if fit and price_token in fit and fit not in desc_seen:
                            desc_to_add = fit
                            break
                    if desc_to_add is not None:
                        if len(target.descriptions) < 4:
                            target.descriptions.append(AdDescription(text=desc_to_add))
                        else:
                            target.descriptions[-1] = AdDescription(text=desc_to_add)

                    # Try a headline too, but only if we can fit one cleanly.
                    head_candidates = [
                        f"{nm_for_head} from {price_token}",
                        f"From {price_token} to {nm_for_head}",
                        f"Flights from {price_token}",
                    ]
                    head_seen = {h.text for h in target.headlines}
                    for cand in head_candidates:
                        fit = _fit_to_limit(cand, 30, client.language)
                        if fit and price_token in fit and fit not in head_seen:
                            if len(target.headlines) < 15:
                                target.headlines.append(AdHeadline(text=fit))
                            else:
                                target.headlines[-1] = AdHeadline(text=fit)
                            break

    logger.info(
        "Generated %d RSA variants for ad group '%s' (product=%s)",
        len(rsas), ad_group_theme, product.sku if product else "<none>",
    )
    return rsas
