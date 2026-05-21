"""v0.3.4 audit script.

Reads the freshly-exported `04_responsive_search_ads.csv` and validates the
four ship-blocker contracts from the v0.3.4 missions:
  1. text=N rotates per variant within each ad group (no duplicates).
  2. Every discounted destination (>= 15%) has a 'Save up to X%' headline.
  3. Customer copy NEVER contains the SKU/IATA code.
  4. Every priced destination surfaces from_price in at least one variant.

Prints a punch list. Exit code is non-zero if any contract fails so this
can also gate CI.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RSA_CSV = ROOT / "clients/etraveli/exports/catalog/04_responsive_search_ads.csv"
DEST_CSV = ROOT / "clients/etraveli/Client Case Info/Destination list (Template) - Destinations.csv"
ACCEPTED = ROOT / "clients/etraveli/catalog/accepted_proposal.json"


def load_destinations() -> dict[str, str]:
    out: dict[str, str] = {}
    with DEST_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out[row["Destination code"].strip()] = row["Destination name"].strip()
    return out


def load_attributes() -> dict[str, dict]:
    """Pull from_price + discount_pct per SKU from the accepted_proposal."""
    if not ACCEPTED.exists():
        return {}
    data = json.loads(ACCEPTED.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for row in data.get("rows", []):
        sku = row.get("sku") or row.get("primary_key")
        if sku:
            out[sku] = row.get("attributes", {})
    return out


def load_rsa_rows() -> list[dict]:
    with RSA_CSV.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def parse_text_n(url: str) -> int | None:
    m = re.search(r"[?&]text=(\d+)", url)
    return int(m.group(1)) if m else None


def main() -> int:
    rows = load_rsa_rows()
    dests = load_destinations()
    # In case the accepted_proposal has a different shape, pull attrs from the
    # case-runner's live products as a fallback.
    attrs = load_attributes()
    if not attrs:
        import os
        os.environ["SEM_DISABLE_LLM"] = "1"
        from src.catalog import load_catalog_from_yaml
        catalog = load_catalog_from_yaml(ROOT / "clients/etraveli/catalog.yaml")
        for cat_row in catalog:
            attrs[cat_row.key] = dict(cat_row.attributes)

    # Index rows by ad group → list of rows
    by_ag: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_ag[row["Ad Group"]].append(row)

    # Track findings
    sku_leaks: list[str] = []
    duplicate_text_ns: list[str] = []
    missing_save_headline: list[str] = []
    missing_from_price: list[str] = []

    # Whitelist of OTA + IATA tokens that may appear in copy without being a
    # destination SKU leak (e.g. 'IATA-accredited' uses the word 'IATA').
    safe_tokens = {"IATA", "OTA", "USD", "EUR", "GBP", "SEK"}

    for ag_name, ag_rows in by_ag.items():
        m = re.match(r".*\(([A-Z]{2,3})\)$", ag_name)
        sku = m.group(1) if m else None

        # Mission 3: text=N uniqueness within ad group
        text_ns = [parse_text_n(row["Final URL"]) for row in ag_rows]
        text_ns_set = [n for n in text_ns if n is not None]
        if len(text_ns_set) != len(set(text_ns_set)) and len(ag_rows) > 1:
            duplicate_text_ns.append(f"{ag_name}: text_ns={text_ns}")

        # Mission 4a: no SKU in customer copy (3-letter IATA codes only)
        if sku and sku not in safe_tokens and re.fullmatch(r"[A-Z]{3}", sku):
            sku_re = re.compile(rf"\b{re.escape(sku)}\b")
            for row in ag_rows:
                for k, v in row.items():
                    if k.startswith("Headline ") and v:
                        # Skip the position columns
                        if "position" in k.lower():
                            continue
                        if sku_re.search(v):
                            sku_leaks.append(f"{ag_name}: {k}={v!r}")
                    if k.startswith("Description ") and v:
                        if "position" in k.lower():
                            continue
                        if sku_re.search(v):
                            sku_leaks.append(f"{ag_name}: {k}={v!r}")

        # Mission 2: 'Save up to X%' headline for discounted destinations
        product_attrs = attrs.get(sku, {}) if sku else {}
        dp = product_attrs.get("discount_pct")
        if dp is not None:
            try:
                dp_val = float(dp)
            except (TypeError, ValueError):
                dp_val = 0.0
            if dp_val > 1:
                dp_val /= 100.0
            if dp_val >= 0.15:
                pct_str = str(int(round(dp_val * 100)))
                # Look across all variants for a 'Save up to X%' headline OR
                # a 'Save' + pct + name token combination.
                dest_name = dests.get(sku, "").lower() if sku else ""
                name_tokens = [t for t in re.findall(r"[A-Za-z]+", dest_name) if len(t) >= 4]
                found = False
                for row in ag_rows:
                    for k, v in row.items():
                        if not k.startswith("Headline ") or "position" in k.lower() or not v:
                            continue
                        if v.lower().startswith(f"save up to {pct_str}%"):
                            found = True
                            break
                        if (
                            "save" in v.lower()
                            and pct_str in v
                            and any(tok in v.lower() for tok in name_tokens)
                        ):
                            found = True
                            break
                    if found:
                        break
                if not found:
                    missing_save_headline.append(
                        f"{ag_name} (discount={dp_val:.2f})"
                    )

        # Mission 4b: from_price surfaced in at least one variant
        fp = product_attrs.get("from_price")
        if fp is not None:
            try:
                fp_val = float(fp)
            except (TypeError, ValueError):
                fp_val = 0.0
            if fp_val > 0:
                fp_int = int(fp_val) if float(fp_val).is_integer() else None
                price_str = f"${fp_int:,}" if fp_int is not None else f"${fp_val:,.2f}"
                found = False
                for row in ag_rows:
                    for k, v in row.items():
                        if (k.startswith("Headline ") or k.startswith("Description ")) \
                                and v and "position" not in k.lower():
                            if price_str in v:
                                found = True
                                break
                    if found:
                        break
                if not found:
                    missing_from_price.append(
                        f"{ag_name} (from_price={fp_val}, expected={price_str})"
                    )

    print(f"=== v0.3.4 Audit ===")
    print(f"Total ad groups: {len(by_ag)}")
    print(f"Total RSA rows: {len(rows)}")
    print()
    print(f"--- Mission 3: per-variant text=N uniqueness ---")
    print(f"Ad groups with duplicate text=N: {len(duplicate_text_ns)}")
    for x in duplicate_text_ns[:10]:
        print(f"  {x}")
    if len(duplicate_text_ns) > 10:
        print(f"  ... +{len(duplicate_text_ns)-10} more")
    print()
    print(f"--- Mission 4a: no SKU in customer copy ---")
    print(f"SKU leaks: {len(sku_leaks)}")
    for x in sku_leaks[:15]:
        print(f"  {x}")
    if len(sku_leaks) > 15:
        print(f"  ... +{len(sku_leaks)-15} more")
    print()
    print(f"--- Mission 2: 'Save up to X%' headline for discount>=15% ---")
    print(f"Discounted destinations missing canonical headline: {len(missing_save_headline)}")
    for x in missing_save_headline[:15]:
        print(f"  {x}")
    if len(missing_save_headline) > 15:
        print(f"  ... +{len(missing_save_headline)-15} more")
    print()
    print(f"--- Mission 4b: from_price guarantee ---")
    print(f"Priced destinations missing from_price in copy: {len(missing_from_price)}")
    for x in missing_from_price[:15]:
        print(f"  {x}")
    if len(missing_from_price) > 15:
        print(f"  ... +{len(missing_from_price)-15} more")

    failures = (
        len(duplicate_text_ns) + len(sku_leaks)
        + len(missing_save_headline) + len(missing_from_price)
    )
    print()
    print(f"=== TOTAL FAILURES: {failures} ===")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
