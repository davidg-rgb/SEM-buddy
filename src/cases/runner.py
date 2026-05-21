"""End-to-end case orchestrator.

`run_case(slug, ...)` walks a client's `case.yaml` from data files to ready-to-
import Google Ads Editor CSVs. Designed to be the only command the operator
needs to run after dropping data + writing the YAML configs.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.cases.config import CaseConfig, load_case_config
from src.catalog import Catalog, load_catalog_from_yaml
from src.catalog.cleaners import (
    apply_proposal,
    load_proposal,
    propose_cleanings,
    write_cleaning_artifacts,
)
from src.catalog.validators import CatalogSchema, validate_catalog
from src.generators.campaign_builder import (
    build_campaigns_from_catalog,
    catalog_row_to_product,
)
from src.generators.csv_exporter import export_campaign_plan
from src.models.client import CampaignGoal, ClientProfile
from src.utils.config import CLIENTS_DIR

logger = logging.getLogger(__name__)


CASE_FILE_NAME = "case.yaml"


@dataclass
class CaseRunResult:
    slug: str
    catalog: Catalog
    products_count: int
    campaign_count: int
    ad_group_count: int
    promotions_count: int
    lead_forms_count: int
    bid_schedules_count: int
    export_dir: Path
    validation_summary: str
    cleaning_applied: bool


def _resolve_case_path(slug: str) -> Path:
    base = CLIENTS_DIR / slug
    case_path = base / CASE_FILE_NAME
    if not case_path.exists():
        raise FileNotFoundError(
            f"Case config not found: {case_path}. "
            f"Create {CASE_FILE_NAME} in clients/{slug}/."
        )
    return case_path


def _load_client_profile(slug: str, case: CaseConfig) -> ClientProfile:
    """Build a `ClientProfile` from case-level overrides + the `account.yaml`."""
    from src.accounts.manager import get_account

    try:
        account = get_account(slug)
    except FileNotFoundError:
        account = None

    business_name = (
        case.business_name
        or (account.display_name if account else slug.replace("-", " ").title())
    )
    website_url = case.website_url or (account.website_url if account else None) or "https://example.com/"
    industry = case.industry or (account.industry if account else "general")
    budget = (
        case.monthly_budget_sek
        or (account.monthly_budget_sek if account else None)
        or 10_000
    )

    campaign_goals: list[CampaignGoal] = []
    if case.campaign_goals.goal_type:
        campaign_goals.append(
            CampaignGoal(
                goal_type=case.campaign_goals.goal_type,
                target_cpa_sek=case.campaign_goals.target_cpa_sek,
            )
        )

    return ClientProfile(
        business_name=business_name,
        website_url=website_url,
        industry=industry,
        products_services=[],
        language=case.language,
        monthly_budget_sek=budget,
        campaign_goals=campaign_goals,
    )


def _maybe_clean_catalog(slug: str, catalog: Catalog) -> tuple[Catalog, bool]:
    """If a previously accepted cleaning proposal exists, apply it.

    Looks for `clients/<slug>/catalog/cleaning_log.json`. If present, applies
    those diffs. If not present, returns the catalog as-is.
    """
    accepted = CLIENTS_DIR / slug / "catalog" / "accepted_proposal.json"
    if not accepted.exists():
        return catalog, False
    proposal = load_proposal(accepted)
    cleaned = apply_proposal(catalog, proposal)
    logger.info(
        "Applied %d cleaning diffs from %s", len(proposal.diffs), accepted,
    )
    return cleaned, True


def run_case(
    slug: str,
    *,
    output_subdir: str = "exports",
    validate: bool = True,
    max_products: int | None = None,
) -> CaseRunResult:
    """Run the full case pipeline.

    `max_products` truncates the catalog to the first N rows — handy for
    iterating on the case fast before scaling to 1,000.
    """
    case_path = _resolve_case_path(slug)
    case = load_case_config(case_path)
    client = _load_client_profile(slug, case)

    catalog_path = (case_path.parent / case.catalog).resolve()
    catalog = load_catalog_from_yaml(catalog_path)
    catalog, cleaning_applied = _maybe_clean_catalog(slug, catalog)

    # Validation report (non-blocking — errors are surfaced but we still build)
    schema = CatalogSchema()
    report = validate_catalog(catalog, schema)
    validation_summary = report.summary()
    if validate and report.has_errors:
        logger.warning("Catalog has %d validation errors", len(report.errors))

    products = [catalog_row_to_product(row) for row in catalog]
    if max_products is not None:
        products = products[:max_products]

    build_config = case.to_build_config()
    plan = build_campaigns_from_catalog(
        client, products, build_config,
        lead_form_config=(
            case.extensions.lead_form.model_dump() if case.extensions.lead_form else None
        ),
        promotion_start_date=case.extensions.promotions.start_date,
        promotion_end_date=case.extensions.promotions.end_date,
        promotion_occasion=case.extensions.promotions.occasion,
        money_currency=case.extensions.promotions.money_currency,
    )

    out_dir = CLIENTS_DIR / slug / output_subdir / "catalog"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Clear stale CSVs but tolerate Windows file locks on individual files
    for child in out_dir.iterdir():
        if child.is_file():
            try:
                child.unlink()
            except OSError as exc:
                logger.warning("Could not remove %s (file locked?): %s", child, exc)
    export_campaign_plan(plan, str(out_dir))

    return CaseRunResult(
        slug=slug,
        catalog=catalog,
        products_count=len(products),
        campaign_count=len(plan.campaigns),
        ad_group_count=sum(len(c.ad_groups) for c in plan.campaigns),
        promotions_count=len(plan.promotions),
        lead_forms_count=len(plan.lead_forms),
        bid_schedules_count=len(plan.bid_schedules),
        export_dir=out_dir,
        validation_summary=validation_summary,
        cleaning_applied=cleaning_applied,
    )


def run_clean(slug: str) -> tuple[Path, Path]:
    """Phase 1 of the cleaning workflow: propose fixes, write artifacts.

    Caller reviews `cleaning_diff.md` then runs `run_accept_fixes` to apply.
    """
    case_path = _resolve_case_path(slug)
    case = load_case_config(case_path)
    catalog_path = (case_path.parent / case.catalog).resolve()
    catalog = load_catalog_from_yaml(catalog_path)
    proposal = propose_cleanings(catalog)
    out_dir = CLIENTS_DIR / slug / "catalog"
    return write_cleaning_artifacts(proposal, out_dir)


def run_accept_fixes(slug: str) -> Path:
    """Phase 2 of the cleaning workflow: promote the proposal to accepted_proposal.json.

    Subsequent `run_case` calls will automatically apply these diffs.
    """
    out_dir = CLIENTS_DIR / slug / "catalog"
    log_path = out_dir / "cleaning_log.json"
    accepted_path = out_dir / "accepted_proposal.json"
    if not log_path.exists():
        raise FileNotFoundError(
            f"No cleaning proposal found at {log_path}. "
            "Run `sem catalog clean <slug>` first."
        )
    shutil.copyfile(log_path, accepted_path)
    return accepted_path


__all__ = ["run_case", "run_clean", "run_accept_fixes", "CaseRunResult"]
