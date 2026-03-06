#!/usr/bin/env python3
"""Pre-export campaign validation script.

Usage:
    python scripts/validate_campaign.py clients/{name}/campaigns/campaign.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Home service industries that should mention ROT-avdrag
ROT_INDUSTRIES = [
    "bygg", "renovering", "vvs", "el", "malare", "snickare",
    "taklaeggare", "golv", "bygg_renovering", "roermokare",
]

# Placeholder patterns that indicate incomplete content
PLACEHOLDER_PATTERNS = re.compile(r"\[INSERT\]|TODO|\{[^}]+\}|\[.*?\]")

# URL validation pattern
URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:[\w-]+\.)+[a-z]{2,}"
    r"(?:/[^\s]*)?$",
    re.IGNORECASE,
)


class ValidationResult:
    """Stores results for a single validation check."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.passed = True
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def fail(self, message: str) -> None:
        self.passed = False
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def load_campaign_plan(path: str) -> dict:
    """Load campaign plan from JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_headline_lengths(plan: dict) -> ValidationResult:
    """Zero headlines over 30 chars."""
    result = ValidationResult("Headline Length (max 30 chars)")
    for campaign in plan.get("campaigns", []):
        for ag in campaign.get("ad_groups", []):
            for ad in ag.get("ads", []):
                for i, headline in enumerate(ad.get("headlines", []), 1):
                    text = headline.get("text", "")
                    if len(text) > 30:
                        result.fail(
                            f"Campaign '{campaign['name']}' > "
                            f"Ad Group '{ag['name']}' > "
                            f"Headline {i}: '{text}' ({len(text)} chars)"
                        )
    return result


def validate_description_lengths(plan: dict) -> ValidationResult:
    """Zero descriptions over 90 chars."""
    result = ValidationResult("Description Length (max 90 chars)")
    for campaign in plan.get("campaigns", []):
        for ag in campaign.get("ad_groups", []):
            for ad in ag.get("ads", []):
                for i, desc in enumerate(ad.get("descriptions", []), 1):
                    text = desc.get("text", "")
                    if len(text) > 90:
                        result.fail(
                            f"Campaign '{campaign['name']}' > "
                            f"Ad Group '{ag['name']}' > "
                            f"Description {i}: '{text}' ({len(text)} chars)"
                        )
    return result


def validate_ad_group_minimums(plan: dict) -> ValidationResult:
    """Every ad group has min 3 headlines, 2 descriptions, 1+ keywords."""
    result = ValidationResult("Ad Group Minimums (3H, 2D, 1KW)")
    for campaign in plan.get("campaigns", []):
        for ag in campaign.get("ad_groups", []):
            ag_name = f"Campaign '{campaign['name']}' > Ad Group '{ag['name']}'"

            # Check keywords
            kw_count = len(ag.get("keywords", []))
            if kw_count < 1:
                result.fail(f"{ag_name}: has {kw_count} keywords (min 1)")

            # Check ads
            for ad in ag.get("ads", []):
                h_count = len(ad.get("headlines", []))
                d_count = len(ad.get("descriptions", []))
                if h_count < 3:
                    result.fail(f"{ag_name}: has {h_count} headlines (min 3)")
                if d_count < 2:
                    result.fail(f"{ag_name}: has {d_count} descriptions (min 2)")

            if not ag.get("ads"):
                result.fail(f"{ag_name}: has no ads")
    return result


def validate_no_placeholders(plan: dict) -> ValidationResult:
    """No placeholder text like [INSERT], TODO, {variable}."""
    result = ValidationResult("No Placeholder Text")

    def check_text(text: str, location: str) -> None:
        matches = PLACEHOLDER_PATTERNS.findall(text)
        if matches:
            result.fail(f"{location}: found placeholder(s) {matches} in '{text}'")

    for campaign in plan.get("campaigns", []):
        c_name = campaign.get("name", "")
        check_text(c_name, f"Campaign name")

        for ag in campaign.get("ad_groups", []):
            ag_loc = f"Campaign '{c_name}' > Ad Group '{ag.get('name', '')}'"
            for ad in ag.get("ads", []):
                for i, h in enumerate(ad.get("headlines", []), 1):
                    check_text(h.get("text", ""), f"{ag_loc} > Headline {i}")
                for i, d in enumerate(ad.get("descriptions", []), 1):
                    check_text(d.get("text", ""), f"{ag_loc} > Description {i}")
    return result


def validate_negative_keyword_conflicts(plan: dict) -> ValidationResult:
    """Negative keywords don't block target keywords (check for exact overlaps)."""
    result = ValidationResult("Negative Keyword Conflicts")
    for campaign in plan.get("campaigns", []):
        for ag in campaign.get("ad_groups", []):
            target_kws = {kw.get("text", "").lower() for kw in ag.get("keywords", [])}
            neg_kws = {n.lower() for n in ag.get("negative_keywords", [])}

            conflicts = target_kws & neg_kws
            if conflicts:
                result.fail(
                    f"Campaign '{campaign['name']}' > Ad Group '{ag['name']}': "
                    f"negative keywords blocking targets: {conflicts}"
                )
    return result


def validate_budget_allocation(plan: dict) -> ValidationResult:
    """Budget allocations are positive and reasonable."""
    result = ValidationResult("Budget Allocation")
    for campaign in plan.get("campaigns", []):
        budget = campaign.get("budget_sek_daily", 0)
        if budget <= 0:
            result.fail(f"Campaign '{campaign['name']}': budget is {budget} SEK/day (must be > 0)")
        elif budget < 10:
            result.warn(f"Campaign '{campaign['name']}': budget is very low ({budget} SEK/day)")
    return result


def validate_minimum_negatives(plan: dict) -> ValidationResult:
    """Minimum 10 negative keywords per campaign."""
    result = ValidationResult("Minimum Negative Keywords (10/campaign)")
    for campaign in plan.get("campaigns", []):
        # Collect all negatives across ad groups in this campaign
        all_negatives: set[str] = set()
        for ag in campaign.get("ad_groups", []):
            all_negatives.update(ag.get("negative_keywords", []))

        if len(all_negatives) < 10:
            result.fail(
                f"Campaign '{campaign['name']}': only {len(all_negatives)} "
                f"unique negative keywords (min 10)"
            )
    return result


def validate_urls(plan: dict) -> ValidationResult:
    """All URLs are valid format."""
    result = ValidationResult("URL Format Validation")
    for campaign in plan.get("campaigns", []):
        for ag in campaign.get("ad_groups", []):
            for ad in ag.get("ads", []):
                url = ad.get("final_url", "")
                if url and not URL_PATTERN.match(url):
                    result.fail(
                        f"Campaign '{campaign['name']}' > Ad Group '{ag['name']}': "
                        f"invalid URL '{url}'"
                    )

    # Check sitelink URLs
    for sl in plan.get("sitelinks", []):
        url = sl.get("final_url", "")
        if url and not URL_PATTERN.match(url):
            result.fail(f"Sitelink '{sl.get('text', '')}': invalid URL '{url}'")

    return result


def validate_rot_avdrag(plan: dict) -> ValidationResult:
    """ROT-avdrag mention check for home service industries."""
    result = ValidationResult("ROT-avdrag Mention (home services)")

    # Try to detect industry from campaign names or keywords
    all_text = ""
    for campaign in plan.get("campaigns", []):
        all_text += campaign.get("name", "").lower() + " "
        for ag in campaign.get("ad_groups", []):
            for kw in ag.get("keywords", []):
                all_text += kw.get("text", "").lower() + " "

    is_home_service = any(ind in all_text for ind in ROT_INDUSTRIES)

    if is_home_service:
        # Check if ROT is mentioned in any ad copy
        rot_mentioned = False
        for campaign in plan.get("campaigns", []):
            for ag in campaign.get("ad_groups", []):
                for ad in ag.get("ads", []):
                    for h in ad.get("headlines", []):
                        if "rot" in h.get("text", "").lower():
                            rot_mentioned = True
                    for d in ad.get("descriptions", []):
                        if "rot" in d.get("text", "").lower():
                            rot_mentioned = True

        # Check callouts too
        for co in plan.get("callouts", []):
            if "rot" in co.get("text", "").lower():
                rot_mentioned = True

        if not rot_mentioned:
            result.warn(
                "Home service industry detected but ROT-avdrag is not mentioned "
                "in any ad copy. Consider adding it as a selling point."
            )

    return result


def validate_path_lengths(plan: dict) -> ValidationResult:
    """Path1 and Path2 max 15 chars."""
    result = ValidationResult("URL Path Length (max 15 chars)")
    for campaign in plan.get("campaigns", []):
        for ag in campaign.get("ad_groups", []):
            for ad in ag.get("ads", []):
                path1 = ad.get("path1", "")
                path2 = ad.get("path2", "")
                if len(path1) > 15:
                    result.fail(
                        f"Campaign '{campaign['name']}' > Ad Group '{ag['name']}': "
                        f"Path1 '{path1}' is {len(path1)} chars (max 15)"
                    )
                if len(path2) > 15:
                    result.fail(
                        f"Campaign '{campaign['name']}' > Ad Group '{ag['name']}': "
                        f"Path2 '{path2}' is {len(path2)} chars (max 15)"
                    )
    return result


def validate_sitelink_text(plan: dict) -> ValidationResult:
    """Sitelink text max 25 chars."""
    result = ValidationResult("Sitelink Text Length (max 25 chars)")
    for sl in plan.get("sitelinks", []):
        text = sl.get("text", "")
        if len(text) > 25:
            result.fail(f"Sitelink '{text}' is {len(text)} chars (max 25)")
    return result


def run_all_validations(plan: dict) -> list[ValidationResult]:
    """Run all validation checks and return results."""
    validators = [
        validate_headline_lengths,
        validate_description_lengths,
        validate_ad_group_minimums,
        validate_no_placeholders,
        validate_negative_keyword_conflicts,
        validate_budget_allocation,
        validate_minimum_negatives,
        validate_urls,
        validate_rot_avdrag,
        validate_path_lengths,
        validate_sitelink_text,
    ]
    return [v(plan) for v in validators]


def print_report(results: list[ValidationResult]) -> bool:
    """Print colorful pass/fail report. Returns True if all passed."""
    passed_count = sum(1 for r in results if r.passed)
    total = len(results)
    all_passed = passed_count == total

    print(f"\n{BOLD}{'=' * 60}")
    print(f"  Campaign Validation Report")
    print(f"{'=' * 60}{RESET}\n")

    for result in results:
        if result.passed:
            status = f"{GREEN}PASS{RESET}"
        else:
            status = f"{RED}FAIL{RESET}"

        print(f"  [{status}] {result.name}")

        for error in result.errors:
            print(f"       {RED}ERROR:{RESET} {error}")

        for warning in result.warnings:
            print(f"       {YELLOW}WARN:{RESET} {warning}")

    print(f"\n{BOLD}{'=' * 60}")
    if all_passed:
        print(f"  {GREEN}All {total} checks passed!{RESET}")
    else:
        failed = total - passed_count
        print(f"  {RED}{failed}/{total} checks failed{RESET}")
    print(f"{'=' * 60}{RESET}\n")

    return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a Google Ads campaign plan JSON file before export.",
    )
    parser.add_argument(
        "campaign_file",
        help="Path to campaign plan JSON file (e.g., clients/acme/campaigns/campaign.json)",
    )
    args = parser.parse_args()

    campaign_path = Path(args.campaign_file)
    if not campaign_path.exists():
        print(f"{RED}Error: File not found: {campaign_path}{RESET}")
        sys.exit(1)

    print(f"Validating: {campaign_path}")
    plan = load_campaign_plan(str(campaign_path))

    results = run_all_validations(plan)
    all_passed = print_report(results)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
