"""Stratified RSA sampler for the v0.3.4 QA review.

Picks 40 ad groups across five buckets:
  - long-name (>= 18 char destination name)
  - short-name (< 7 char destination name)
  - high-discount (>= 40%)
  - low-discount (15-25%)
  - no-price-no-discount (genuinely sparse data)

Writes a markdown sample file with every variant's headlines + descriptions
so a reviewer can scan without context-switching.
"""

from __future__ import annotations

import csv
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RSA_CSV = ROOT / "clients/etraveli/exports/catalog/04_responsive_search_ads.csv"
SAMPLE_OUT = ROOT / "clients/etraveli/exports/catalog/QA-SAMPLE-v034.md"

os.environ.setdefault("SEM_DISABLE_LLM", "1")
sys.path.insert(0, str(ROOT))

from src.catalog import load_catalog_from_yaml  # noqa: E402


def _sku_from_ag_name(ag: str) -> str | None:
    m = re.match(r".*\(([A-Z0-9]{2,5})\)$", ag)
    return m.group(1) if m else None


def main() -> int:
    catalog = load_catalog_from_yaml(ROOT / "clients/etraveli/catalog.yaml")
    products = {row.key: row for row in catalog}

    with RSA_CSV.open(encoding="utf-8-sig") as f:
        rsa_rows = list(csv.DictReader(f))

    by_ag: dict[str, list[dict]] = defaultdict(list)
    for r in rsa_rows:
        by_ag[r["Ad Group"]].append(r)

    long_name: list[str] = []
    short_name: list[str] = []
    high_disc: list[str] = []
    low_disc: list[str] = []
    sparse: list[str] = []

    for ag_name in by_ag:
        sku = _sku_from_ag_name(ag_name)
        if not sku or sku not in products:
            continue
        p = products[sku]
        name_len = len(p.name)
        dp_raw = p.attributes.get("discount_pct") or 0
        dp = float(dp_raw or 0)
        if dp > 1:
            dp /= 100.0
        fp = p.attributes.get("from_price")

        if name_len >= 18:
            long_name.append(ag_name)
        elif name_len < 7:
            short_name.append(ag_name)
        if dp >= 0.40:
            high_disc.append(ag_name)
        elif 0.15 <= dp < 0.25:
            low_disc.append(ag_name)
        if fp is None and dp == 0:
            sparse.append(ag_name)

    rng = random.Random(42)
    picked: list[tuple[str, str]] = []
    for label, pool in [
        ("long-name (>=18 chars)", long_name),
        ("short-name (<7 chars)", short_name),
        ("high-discount (>=40%)", high_disc),
        ("low-discount (15-25%)", low_disc),
        ("no-price-no-discount", sparse),
    ]:
        sample = rng.sample(pool, min(8, len(pool)))
        for ag in sample:
            picked.append((label, ag))

    lines: list[str] = []
    lines.append("# Stratified QA Sample — v0.3.4")
    lines.append("")
    lines.append("Each sampled ad group below shows all its RSA variants so a")
    lines.append("reviewer can scan headlines + descriptions inline.")
    lines.append("")
    lines.append(f"- Total ad groups: {len(by_ag)}")
    lines.append(f"- Sampled: {len(picked)} ad groups across 5 buckets")
    lines.append("")
    cur_label: str | None = None
    for label, ag_name in picked:
        if label != cur_label:
            lines.append(f"## {label}")
            lines.append("")
            cur_label = label
        sku = _sku_from_ag_name(ag_name)
        p = products.get(sku) if sku else None
        attrs = dict(p.attributes) if p else {}
        lines.append(f"### `{ag_name}`")
        lines.append("")
        lines.append(
            f"- **SKU** `{sku}`, **name** `{p.name if p else '?'}`, "
            f"**from_price** `{attrs.get('from_price')}`, "
            f"**discount_pct** `{attrs.get('discount_pct')}`"
        )
        lines.append("")
        for ad_row in by_ag[ag_name]:
            url = ad_row["Final URL"]
            tm = re.search(r"text=(\d+)", url)
            tn = f"text={tm.group(1)}" if tm else "?"
            lines.append(f"**Variant `{tn}`** — `{url}`")
            lines.append("")
            lines.append("Headlines:")
            for i in range(1, 16):
                h = ad_row.get(f"Headline {i}", "")
                if h:
                    pos = ad_row.get(f"Headline {i} position", "")
                    pos_tag = f" *[pinned H{pos}]*" if pos else ""
                    lines.append(f"- {h}{pos_tag}")
            lines.append("")
            lines.append("Descriptions:")
            for i in range(1, 5):
                d = ad_row.get(f"Description {i}", "")
                if d:
                    pos = ad_row.get(f"Description {i} position", "")
                    pos_tag = f" *[pinned D{pos}]*" if pos else ""
                    lines.append(f"- {d}{pos_tag}")
            lines.append("")
    SAMPLE_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {SAMPLE_OUT}")
    print(f"Sampled {len(picked)} ad groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
