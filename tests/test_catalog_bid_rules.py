"""Tests for the bid-rules engine (C10) and scheduled adjustments (C11)."""

from __future__ import annotations

from datetime import date

import pytest

from src.catalog.bid_rules import (
    BidRule,
    BidRuleSet,
    apply_rules,
    parse_expression,
    parse_rules,
)
from src.models.catalog import Product


def _p(**attrs) -> Product:
    base = dict(sku="BKK", name="Bangkok", attributes={})
    if "attributes" in attrs:
        base["attributes"] = attrs.pop("attributes")
    base.update(attrs)
    return Product(**base)


def test_parse_expression_ge() -> None:
    pe = parse_expression("discount_pct >= 30")
    assert pe.attribute == "discount_pct"
    assert pe.op_name == ">="
    assert pe.value == 30
    p = _p(attributes={"discount_pct": 35})
    assert pe.evaluate(p) is True


def test_parse_expression_lt_with_float() -> None:
    pe = parse_expression("from_price < 100.0")
    p1 = _p(attributes={"from_price": 50})
    p2 = _p(attributes={"from_price": 200})
    assert pe.evaluate(p1) is True
    assert pe.evaluate(p2) is False


def test_parse_expression_string_eq() -> None:
    pe = parse_expression('region == "europe"')
    p1 = _p(attributes={"region": "europe"})
    p2 = _p(attributes={"region": "asia"})
    assert pe.evaluate(p1) is True
    assert pe.evaluate(p2) is False


def test_parse_expression_missing_attribute_evaluates_false() -> None:
    pe = parse_expression("nonexistent > 0")
    assert pe.evaluate(_p()) is False


def test_parse_expression_invalid_syntax_raises() -> None:
    with pytest.raises(ValueError, match="Could not parse"):
        parse_expression("discount_pct foo 30")


def test_first_matching_rule_wins() -> None:
    rules = parse_rules([
        {"if": "discount_pct >= 30", "then": {"modifier": 1.5}},
        {"if": "discount_pct >= 15", "then": {"modifier": 1.25}},
        {"if": "from_price < 100", "then": {"modifier": 1.1}},
    ])
    p = _p(attributes={"discount_pct": 35, "from_price": 50})
    result = apply_rules(p, rules, "C1", "AG1")
    assert result.applied_rule_index == 0
    assert result.immediate_modifier == 1.5
    assert result.schedules == []


def test_no_rule_matches_returns_neutral() -> None:
    rules = parse_rules([
        {"if": "discount_pct >= 30", "then": {"modifier": 1.5}},
    ])
    p = _p(attributes={"discount_pct": 0})
    result = apply_rules(p, rules, "C1", "AG1")
    assert result.applied_rule_index is None
    assert result.immediate_modifier == 1.0


def test_missing_attribute_does_not_match_or_crash() -> None:
    rules = parse_rules([
        {"if": "region == \"europe\"", "then": {"modifier": 1.5}},
    ])
    p = _p()  # no region
    result = apply_rules(p, rules, "C1", "AG1")
    assert result.applied_rule_index is None


def test_during_clause_produces_bid_schedule() -> None:
    """Outside the window: schedule still emitted (documentation), immediate
    modifier stays neutral so a downstream rule (if any) can win."""
    rules = parse_rules([
        {
            "if": "discount_pct >= 25",
            "during": {"start": "2026-06-01", "end": "2026-08-31"},
            "then": {"modifier": 2.0, "reason": "Summer sale"},
        },
    ])
    p = _p(attributes={"discount_pct": 30})
    # Explicitly outside the window so the test is date-independent.
    result = apply_rules(
        p, rules, "Flightnetwork - All", "Bangkok (BKK)",
        today=date(2026, 5, 1),
    )
    assert result.applied_rule_index is None  # no rule won immediate
    assert result.immediate_modifier == 1.0
    assert len(result.schedules) == 1
    sched = result.schedules[0]
    assert sched.start_date == date(2026, 6, 1)
    assert sched.end_date == date(2026, 8, 31)
    assert sched.modifier == 2.0
    assert sched.reason == "Summer sale"
    assert sched.ad_group_name == "Bangkok (BKK)"


def test_during_clause_fires_immediately_when_today_in_window() -> None:
    """Inside the window: the during-rule wins first-match — same as if it
    were a base rule — AND the schedule is still emitted for documentation."""
    rules = parse_rules([
        {
            "if": "discount_pct >= 0.30",
            "during": {"start": "2026-05-20", "end": "2026-08-31"},
            "then": {"modifier": 2.5, "reason": "Summer sale — strong"},
        },
        {"if": "discount_pct >= 0.30", "then": {"modifier": 1.80, "reason": "Base"}},
    ])
    p = _p(attributes={"discount_pct": 0.35})
    result = apply_rules(
        p, rules, "Flightnetwork - All", "Bangkok (BKK)",
        today=date(2026, 6, 15),  # inside the summer window
    )
    assert result.applied_rule_index == 0
    assert result.immediate_modifier == 2.5
    assert len(result.schedules) == 1
    assert result.schedules[0].reason == "Summer sale — strong"


def test_during_clause_falls_through_to_base_when_outside_window() -> None:
    """Outside the window: overlay is skipped for the immediate decision,
    and the base rule beneath it wins instead. Schedule still emitted."""
    rules = parse_rules([
        {
            "if": "discount_pct >= 0.30",
            "during": {"start": "2026-05-20", "end": "2026-08-31"},
            "then": {"modifier": 2.5, "reason": "Summer overlay"},
        },
        {"if": "discount_pct >= 0.30", "then": {"modifier": 1.80, "reason": "Base"}},
    ])
    p = _p(attributes={"discount_pct": 0.35})
    result = apply_rules(
        p, rules, "Flightnetwork - All", "Bangkok (BKK)",
        today=date(2026, 9, 15),  # AFTER summer
    )
    assert result.applied_rule_index == 1  # base rule won
    assert result.immediate_modifier == 1.80
    assert len(result.schedules) == 1  # overlay still documented
    assert result.schedules[0].reason == "Summer overlay"


def test_during_overlay_does_not_block_other_base_rule_for_lower_bands() -> None:
    """A 12%-discount product should fall through both the >=30% overlay and
    its base twin, landing on the base 15% rule (when one exists)."""
    rules = parse_rules([
        {
            "if": "discount_pct >= 0.30",
            "during": {"start": "2026-05-20", "end": "2026-08-31"},
            "then": {"modifier": 2.5},
        },
        {"if": "discount_pct >= 0.30", "then": {"modifier": 1.80}},
        {"if": "discount_pct >= 0.15", "then": {"modifier": 1.30}},
        {"if": "discount_pct >= 0.10", "then": {"modifier": 1.15}},
    ])
    p = _p(attributes={"discount_pct": 0.12})
    result = apply_rules(
        p, rules, "C1", "AG1", today=date(2026, 6, 15),
    )
    assert result.applied_rule_index == 3
    assert result.immediate_modifier == 1.15
    assert result.schedules == []  # overlay's if didn't match this product


def test_multiple_overlays_emit_all_schedules() -> None:
    """A product crossing two DIFFERENT seasonality windows gets BOTH
    documented; only the active one wins the immediate decision (if any)."""
    rules = parse_rules([
        {
            "if": "discount_pct >= 0.50",
            "during": {"start": "2026-05-20", "end": "2026-08-31"},
            "then": {"modifier": 3.0, "reason": "Summer"},
        },
        {
            "if": "discount_pct >= 0.50",
            "during": {"start": "2026-11-20", "end": "2027-01-05"},
            "then": {"modifier": 3.5, "reason": "Winter"},
        },
        {"if": "discount_pct >= 0.50", "then": {"modifier": 2.25, "reason": "Base"}},
    ])
    p = _p(attributes={"discount_pct": 0.55})
    # Outside both windows — base wins immediate; both overlays documented.
    result = apply_rules(
        p, rules, "C1", "AG1", today=date(2026, 10, 1),
    )
    assert result.applied_rule_index == 2  # base rule
    assert result.immediate_modifier == 2.25
    assert {s.reason for s in result.schedules} == {"Summer", "Winter"}

    # Inside summer — summer wins immediate; both overlays still documented.
    result_summer = apply_rules(
        p, rules, "C1", "AG1", today=date(2026, 6, 15),
    )
    assert result_summer.applied_rule_index == 0
    assert result_summer.immediate_modifier == 3.0
    assert {s.reason for s in result_summer.schedules} == {"Summer", "Winter"}


def test_cascading_overlays_in_same_window_emit_only_first_match() -> None:
    """Three cascading overlays in the SAME window (50%+ then 40-49% then
    30-39%) where the if-conditions are cumulative (>= threshold) — a 55%
    product should match ALL three but only emit the FIRST schedule (the
    50%+ tier). Stops cascading schedules from polluting 10_bid_schedules.csv
    with duplicates for the same product/window."""
    same_window = {"start": "2026-05-20", "end": "2026-08-31"}
    rules = parse_rules([
        {
            "if": "discount_pct >= 0.50",
            "during": same_window,
            "then": {"modifier": 3.00, "reason": "Summer 50%+"},
        },
        {
            "if": "discount_pct >= 0.40",
            "during": same_window,
            "then": {"modifier": 2.75, "reason": "Summer 40-49%"},
        },
        {
            "if": "discount_pct >= 0.30",
            "during": same_window,
            "then": {"modifier": 2.50, "reason": "Summer 30-39%"},
        },
        {"if": "discount_pct >= 0.30", "then": {"modifier": 1.80, "reason": "Base 30%+"}},
    ])
    # 55% discount — matches all three overlays' if conditions
    p = _p(attributes={"discount_pct": 0.55})
    result = apply_rules(
        p, rules, "C1", "AG1", today=date(2026, 6, 15),  # active window
    )
    assert result.immediate_modifier == 3.00  # the 50%+ overlay won
    # Only ONE schedule emitted (the first matching one in the window).
    assert len(result.schedules) == 1
    assert result.schedules[0].reason == "Summer 50%+"

    # A 35% product (matches only the 30-39% overlay's if) gets that tier.
    p_mid = _p(attributes={"discount_pct": 0.35})
    result_mid = apply_rules(
        p_mid, rules, "C1", "AG1", today=date(2026, 6, 15),
    )
    assert result_mid.immediate_modifier == 2.50
    assert len(result_mid.schedules) == 1
    assert result_mid.schedules[0].reason == "Summer 30-39%"


def test_modifier_out_of_range_rejected() -> None:
    with pytest.raises(ValueError):
        BidRule.model_validate({"if": "x > 0", "then": {"modifier": 15.0}})


def test_during_end_before_start_rejected() -> None:
    with pytest.raises(ValueError):
        BidRule.model_validate({
            "if": "x > 0",
            "during": {"start": "2026-06-01", "end": "2026-05-01"},
            "then": {"modifier": 1.5},
        })


def test_string_value_with_single_quotes() -> None:
    pe = parse_expression("region == 'europe'")
    p = _p(attributes={"region": "europe"})
    assert pe.evaluate(p) is True


def test_sku_attribute_accessible() -> None:
    pe = parse_expression("sku == 'BKK'")
    assert pe.evaluate(_p(sku="BKK")) is True
    assert pe.evaluate(_p(sku="SFO")) is False


def test_type_mismatch_does_not_crash() -> None:
    pe = parse_expression("from_price > 100")
    # Pass a string where a number is expected
    p = _p(attributes={"from_price": "cheap"})
    assert pe.evaluate(p) is False
