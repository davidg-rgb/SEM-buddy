"""Scale validation (C14): 1,000-row catalog must build in <60s and stay under 500MB."""

from __future__ import annotations

import gc
import os
import time
from pathlib import Path

import pytest

# Heavy test — skip unless explicitly enabled or running CI suites.
pytestmark = pytest.mark.skipif(
    os.getenv("SEM_RUN_SCALE_TESTS") != "1",
    reason="Set SEM_RUN_SCALE_TESTS=1 to run the 1k-row scale test (takes ~30s).",
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"
LARGE_YAML = FIXTURE_DIR / "catalog_sample_large.yaml"
LARGE_XLSX = FIXTURE_DIR / "catalog_sample_large.xlsx"


def _resident_mb() -> float | None:
    """Return RSS in MB if psutil is available; else None."""
    try:
        import psutil  # type: ignore
    except ImportError:
        return None
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


def test_large_fixture_exists() -> None:
    assert LARGE_XLSX.exists(), (
        "Run `python scripts/build_catalog_fixture.py` to generate the 1k-row fixture."
    )


def test_load_1000_row_catalog_under_5_seconds() -> None:
    from src.catalog import load_catalog_from_yaml

    start = time.perf_counter()
    catalog = load_catalog_from_yaml(LARGE_YAML)
    elapsed = time.perf_counter() - start
    assert len(catalog) == 1000
    assert elapsed < 5.0, f"Loading 1k rows took {elapsed:.2f}s, budget 5s"


def test_full_catalog_pipeline_within_60_seconds(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    from src.catalog import load_catalog_from_yaml
    from src.generators.campaign_builder import (
        build_campaigns_from_catalog,
        catalog_row_to_product,
    )
    from src.generators.csv_exporter import export_campaign_plan
    from src.models.catalog import CampaignBuildConfig
    from src.models.client import ClientProfile

    catalog = load_catalog_from_yaml(LARGE_YAML)
    products = [catalog_row_to_product(row) for row in catalog]

    client = ClientProfile(
        business_name="Flightnetwork",
        website_url="https://www.flightnetwork.com/",
        industry="travel",
        language="en",
        monthly_budget_sek=2_000_000,
    )
    build_config = CampaignBuildConfig(
        structure_mode="sku",
        campaign_name_template="Flightnetwork - All Destinations",
        ad_group_name_template="{name} ({sku})",
        language="en",
        url_templates={
            "primary": "https://www.flightnetwork.com/from/google/rf/destination?to={sku}&text={N}"
        },
        keyword_templates=["flights to {name}", "{name} flights"],
        keyword_match_types=["PHRASE"],
        promotion_enabled=True,
        bid_rules=[
            {"if": "discount_pct >= 0.30", "then": {"modifier": 1.5}},
            {"if": "discount_pct >= 0.15", "then": {"modifier": 1.25}},
        ],
    )

    gc.collect()
    rss_before = _resident_mb()
    start = time.perf_counter()
    plan = build_campaigns_from_catalog(
        client, products, build_config,
        lead_form_config={
            "form_name": "Get Flight Quote",
            "headline": "Get cheap flights",
            "description": "Enter your details and we will send you the best fares.",
            "business_name": "Flightnetwork",
            "cta": "GET_QUOTE",
            "privacy_url": "https://www.flightnetwork.com/privacy",
            "fields": ["EMAIL", "FIRST_NAME"],
        },
    )
    build_elapsed = time.perf_counter() - start

    assert len(plan.campaigns) == 1
    assert len(plan.campaigns[0].ad_groups) == 1000
    assert build_elapsed < 60.0, f"Build took {build_elapsed:.2f}s; budget 60s"

    # Memory check (best-effort: skip if psutil missing)
    rss_after = _resident_mb()
    if rss_before is not None and rss_after is not None:
        peak_added = rss_after - rss_before
        assert peak_added < 500, f"Pipeline added {peak_added:.1f} MB RSS; budget 500 MB"


def test_full_catalog_emits_three_to_five_variants_per_ag(monkeypatch) -> None:
    """Variant contract holds at the 1k-destination scale."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    from src.catalog import load_catalog_from_yaml
    from src.generators.ad_copy_generator import MAX_VARIANTS, MIN_VARIANTS
    from src.generators.campaign_builder import (
        build_campaigns_from_catalog,
        catalog_row_to_product,
    )
    from src.models.catalog import CampaignBuildConfig
    from src.models.client import ClientProfile

    catalog = load_catalog_from_yaml(LARGE_YAML)
    products = [catalog_row_to_product(row) for row in catalog]
    client = ClientProfile(
        business_name="Flightnetwork",
        website_url="https://www.flightnetwork.com/",
        industry="travel",
        language="en",
        monthly_budget_sek=2_000_000,
    )
    build_config = CampaignBuildConfig(
        structure_mode="sku",
        ad_group_name_template="{name} ({sku})",
        language="en",
        url_templates={
            "primary": "https://www.flightnetwork.com/?to={sku}&text={N}"
        },
        keyword_templates=["flights to {name}"],
        keyword_match_types=["PHRASE"],
        promotion_enabled=True,
    )
    plan = build_campaigns_from_catalog(client, products, build_config)
    total_rsas = 0
    discount_coverage_failures: list[str] = []
    by_sku = {p.sku: p for p in products}
    for ag in plan.campaigns[0].ad_groups:
        assert MIN_VARIANTS <= len(ag.ads) <= MAX_VARIANTS, (
            f"Ad group {ag.name} has {len(ag.ads)} variants"
        )
        total_rsas += len(ag.ads)
        # Discount-surface contract at scale
        sku = ag.name.rsplit("(", 1)[-1].rstrip(")")
        product = by_sku.get(sku)
        if product is None:
            continue
        dp = product.attributes.get("discount_pct")
        if not dp or float(dp) <= 0:
            continue
        pct_str = str(int(round(float(dp) * 100 if dp <= 1 else dp)))
        found = any(
            pct_str in (" | ".join(h.text for h in ad.headlines) + " | " +
                        " | ".join(d.text for d in ad.descriptions))
            for ad in ag.ads
        )
        if not found:
            discount_coverage_failures.append(f"{sku} ({dp})")

    assert not discount_coverage_failures, (
        f"{len(discount_coverage_failures)} destinations missing discount surface"
    )
    # 1,000 products × 3–5 variants = 3,000–5,000 RSAs
    assert total_rsas >= 3_000
    assert total_rsas <= 5_000


def test_csv_export_at_scale_produces_sane_file_sizes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    from src.catalog import load_catalog_from_yaml
    from src.generators.campaign_builder import (
        build_campaigns_from_catalog,
        catalog_row_to_product,
    )
    from src.generators.csv_exporter import export_campaign_plan
    from src.models.catalog import CampaignBuildConfig
    from src.models.client import ClientProfile

    catalog = load_catalog_from_yaml(LARGE_YAML)
    products = [catalog_row_to_product(row) for row in catalog]
    client = ClientProfile(
        business_name="Flightnetwork",
        website_url="https://www.flightnetwork.com/",
        industry="travel",
        language="en",
        monthly_budget_sek=2_000_000,
    )
    build_config = CampaignBuildConfig(
        structure_mode="sku",
        ad_group_name_template="{name} ({sku})",
        language="en",
        url_templates={
            "primary": "https://www.flightnetwork.com/?to={sku}&text={N}"
        },
        keyword_templates=["flights to {name}"],
        keyword_match_types=["PHRASE"],
        promotion_enabled=True,
    )
    plan = build_campaigns_from_catalog(client, products, build_config)
    export_dir = Path(export_campaign_plan(plan, str(tmp_path)))

    # Per-file size sanity
    sizes = {p.name: p.stat().st_size for p in export_dir.glob("*.csv")}
    # Promotions ~1 row per discounted product → ~700 rows × ~250 chars ≈ 175 KB max
    assert sizes.get("08_promotions.csv", 0) < 500_000, f"Promotions too big: {sizes['08_promotions.csv']}"
    # Ad groups ~1000 rows × ~100 chars ≈ 100 KB
    assert sizes.get("02_ad_groups.csv", 0) < 500_000
