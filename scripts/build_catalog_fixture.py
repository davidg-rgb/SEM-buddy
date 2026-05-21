"""Generate the sanitized test fixture XLSX at tests/fixtures/catalog_sample.xlsx.

Replays the real schema (3 sheets: Destinations / From Prices / Discounts)
with synthetic, deterministic values. 10 rows covering: clean names,
backtick-quote names, missing-price rows, missing-discount rows.

Run: `python scripts/build_catalog_fixture.py`
"""

from __future__ import annotations

import random
from pathlib import Path

import openpyxl


FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "catalog_sample.xlsx"


# 10 rows: mix of clean, typo'd, backtick, missing-data
DESTINATIONS = [
    ("Bangkok, Thailand", "BKK"),
    ("Petropavlovsk-Kamchats, Russian Federation", "PKC"),  # truncated name
    ("Mazow`iecki, Poland", "WMI"),  # backtick instead of apostrophe
    ("San Francisco, USA", "SFO"),
    ("Tokyo, Japan", "TYO"),
    ("Reykjavik, Iceland", "REK"),
    ("Vinyard Haven, USA", "MVY"),  # typo: Vineyard
    ("Singapore", "SIN"),
    ("New York, USA", "NYC"),
    ("Buenos Aires, Argentina", "EZE"),  # no price/discount in this fixture
]

# 9 rows of prices (NYC + EZE missing on purpose to exercise the gap path)
PRICES = [
    ("BKK", 450.0),
    ("PKC", 380.0),
    ("WMI", 120.0),
    ("SFO", 320.0),
    ("TYO", 510.0),
    ("REK", 280.0),
    ("MVY", 95.0),
    ("SIN", 470.0),
    # NYC and EZE intentionally absent
]

# 8 rows of discounts
DISCOUNTS = [
    ("BKK", 0.25),
    ("PKC", 0.0),
    ("WMI", 0.40),
    ("SFO", 0.10),
    ("TYO", 0.30),
    ("REK", 0.15),
    ("MVY", 0.0),
    ("SIN", 0.20),
    # NYC + EZE absent
]


def build() -> Path:
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active
    wb.remove(default_sheet)

    dest = wb.create_sheet("Destinations")
    dest.append(["Destination name", "Destination code"])
    for name, code in DESTINATIONS:
        dest.append([name, code])

    prices = wb.create_sheet("From Prices")
    prices.append(["Destination code", "From price"])
    for code, price in PRICES:
        prices.append([code, price])

    discounts = wb.create_sheet("Discounts")
    discounts.append(["Destination code", "Discount"])
    for code, disc in DISCOUNTS:
        discounts.append([code, disc])

    wb.save(FIXTURE_PATH)
    return FIXTURE_PATH


def build_large_fixture(num_rows: int = 1000) -> Path:
    """Generate a synthetic large-scale fixture for the scale-validation test."""
    rng = random.Random(42)
    out_path = FIXTURE_PATH.parent / "catalog_sample_large.xlsx"

    wb = openpyxl.Workbook()
    default_sheet = wb.active
    wb.remove(default_sheet)

    # Build deterministic 3-letter codes: AAA..ZZZ rotation
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    codes: list[str] = []
    for i in range(num_rows):
        a = alphabet[(i // 676) % 26]
        b = alphabet[(i // 26) % 26]
        c = alphabet[i % 26]
        codes.append(f"{a}{b}{c}")

    dest = wb.create_sheet("Destinations")
    dest.append(["Destination name", "Destination code"])
    for i, code in enumerate(codes):
        dest.append([f"Destination {i+1} ({code})", code])

    prices = wb.create_sheet("From Prices")
    prices.append(["Destination code", "From price"])
    # 95% have prices
    for code in codes:
        if rng.random() < 0.95:
            prices.append([code, float(rng.randint(50, 800))])

    discounts = wb.create_sheet("Discounts")
    discounts.append(["Destination code", "Discount"])
    # 70% have discounts (some 0)
    for code in codes:
        if rng.random() < 0.70:
            discounts.append([code, round(rng.uniform(0.0, 0.6), 2)])

    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    p = build()
    print(f"Wrote fixture: {p}")
    p2 = build_large_fixture()
    print(f"Wrote large fixture: {p2}")
