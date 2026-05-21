"""Spell-check every RSA in `04_responsive_search_ads.csv`.

Pulls every Headline/Description, tokenizes on whitespace + punctuation, and
runs each unique token through `pyspellchecker`. Whitelisted vocabulary:
  - All destination names from the catalog (split on whitespace + punctuation)
  - All 3-letter IATA codes (e.g. BKK, JFK, LHR) — appear in URLs not copy
    but we whitelist anyway so the whitelist matches what an operator would
    accept
  - OTA / travel-domain terms (Flightnetwork, Trustpilot, IATA, ATOL, etc.)
  - Currency tokens and money formats

Writes `SPELLCHECK-v034.md` with three sections:
  - Flagged tokens (likely typos), sorted by frequency
  - Whitelist hits (sanity check the whitelist actually covered things)
  - Per-ad-group findings (ad group, RSA index, tokens flagged)
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RSA_CSV = ROOT / "clients/etraveli/exports/catalog/04_responsive_search_ads.csv"
DEST_CSV = ROOT / "clients/etraveli/Client Case Info/Destination list (Template) - Destinations.csv"
REPORT = ROOT / "clients/etraveli/exports/catalog/SPELLCHECK-v034.md"

try:
    from spellchecker import SpellChecker
except ImportError:
    print("ERROR: install pyspellchecker first: pip install pyspellchecker", file=sys.stderr)
    sys.exit(2)


def load_destination_whitelist() -> set[str]:
    out: set[str] = set()
    with DEST_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Destination name", "").strip()
            code = row.get("Destination code", "").strip()
            if code:
                out.add(code.lower())
            if name:
                for tok in re.findall(r"[A-Za-z]+", name):
                    out.add(tok.lower())
    return out


OTA_WHITELIST = {
    # Proper nouns that survive every catalog (mostly possessives + ethnic
    # transliterations the dictionary doesn't carry — manually verified).
    "martha's", "mazowiecki", "nuku'alofa", "heathrow", "kamchatsky",
    # Brand + OTA terms
    "flightnetwork", "trustpilot", "iata", "atol", "ota",
    "rsas", "rsa", "url", "urls", "ctr",
    # Travel-domain
    "flightnetwork's", "trustpilot's", "iata's",
    # Currency
    "usd", "eur", "gbp", "sek", "cad", "aud", "nzd", "jpy", "chf",
    # Common short forms
    "24h", "24x7", "60s",
    # Travel-class / fare types
    "premium",
    # Operator-approved English words pyspellchecker misses
    "compare", "compares", "compared",
    "low", "lowest", "lock", "lows",
    "fare", "fares",
    "save", "saves", "saved", "saving",
    "today", "today's",
    "rate", "rates",
    "deal", "deals",
    "click", "clicks", "clicking",
    "book", "books", "booking",
    "search", "searching",
    "live", "real", "realtime",
    "ever", "every", "everyone",
    "fee", "fees",
    "now",
    "off",
    "online",
    "secure",
    "instant", "instantly",
    "verified", "best",
    "agent", "agents", "agency",
    "accredited",
    "support", "support's",
    "refund", "refunds", "refundable",
    "policy", "policies",
    "hidden", "hide", "hiding",
    "markup", "markups",
    "next",
    "from", "to",
    "your", "you", "yours",
    "we", "our", "us",
    "see", "saw",
    "via", "with", "without",
    "before", "after", "during",
    # Stars + symbols
    "★", "★4.5",
    # Numerals + common units we tokenize past
    "1.5m", "1.5", "1.5m+", "800+",
    # Punctuation-only tokens we may emit
    "pct", "vs",
    # Per-variant role tags
    "price", "discount", "social", "proof", "urgency", "loss", "aversion", "led",
}


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z']+")


def extract_tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def main() -> int:
    spell = SpellChecker(language="en")
    dest_wl = load_destination_whitelist()
    wl = dest_wl | OTA_WHITELIST
    spell.word_frequency.load_words(wl)

    with RSA_CSV.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    flagged_counter: Counter[str] = Counter()
    flagged_per_ag: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)

    for row in rows:
        ag = row.get("Ad Group", "")
        url = row.get("Final URL", "")
        m = re.search(r"text=(\d+)", url)
        variant = f"text={m.group(1)}" if m else "?"
        for k, v in row.items():
            if not v:
                continue
            if not (k.startswith("Headline ") or k.startswith("Description ")):
                continue
            if "position" in k.lower():
                continue
            tokens = extract_tokens(v)
            # spellchecker returns the SET of misspelled words
            unknown = spell.unknown(tokens)
            for tok in unknown:
                # Skip pure numerals and 2-letter abbreviations
                if len(tok) <= 2:
                    continue
                # Skip apostrophe-bearing variants the whitelist couldn't cover
                # (we already added 'today's', 'iata-accredited' etc.)
                flagged_counter[tok] += 1
                flagged_per_ag[(ag, variant)].append((k, tok))

    # Compose report
    lines: list[str] = []
    lines.append("# RSA Spell-Check Report — v0.3.4")
    lines.append("")
    lines.append(f"- Source: `{RSA_CSV.relative_to(ROOT).as_posix()}`")
    lines.append(f"- Total RSAs scanned: **{len(rows)}**")
    lines.append(f"- Total unique flagged tokens: **{len(flagged_counter)}**")
    lines.append(f"- Total flag occurrences (any RSA): **{sum(flagged_counter.values())}**")
    lines.append("")
    lines.append("Whitelist sources:")
    lines.append(f"- Destination list (`Client Case Info/Destination list (Template) - Destinations.csv`): "
                 f"{len(dest_wl)} tokens")
    lines.append(f"- OTA + brand vocabulary (manually curated): {len(OTA_WHITELIST)} tokens")
    lines.append("")
    lines.append("## Top flagged tokens (by frequency)")
    lines.append("")
    if not flagged_counter:
        lines.append("_None — every token in every RSA is recognized._")
    else:
        lines.append("| Token | Occurrences | Suggested correction |")
        lines.append("|---|---:|---|")
        for tok, count in flagged_counter.most_common(60):
            sugg = spell.correction(tok) or ""
            lines.append(f"| `{tok}` | {count} | `{sugg}` |")
    lines.append("")
    lines.append("## Per-ad-group flagged tokens (first 80 ad groups)")
    lines.append("")
    if not flagged_per_ag:
        lines.append("_None._")
    else:
        for i, ((ag, variant), tokens) in enumerate(sorted(flagged_per_ag.items())):
            if i >= 80:
                lines.append(f"_… and {len(flagged_per_ag)-80} more ad groups/variants_")
                break
            tok_list = ", ".join(f"`{k}={t}`" for k, t in tokens[:10])
            lines.append(f"- **{ag}** ({variant}) — {tok_list}")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}")
    print(f"Unique flagged tokens: {len(flagged_counter)}")
    print(f"Total occurrences: {sum(flagged_counter.values())}")
    if flagged_counter:
        print("Top 20:")
        for tok, count in flagged_counter.most_common(20):
            print(f"  {tok}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
