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
    rules = parse_rules([
        {
            "if": "discount_pct >= 25",
            "during": {"start": "2026-06-01", "end": "2026-08-31"},
            "then": {"modifier": 2.0, "reason": "Summer sale"},
        },
    ])
    p = _p(attributes={"discount_pct": 30})
    result = apply_rules(p, rules, "Flightnetwork - All", "Bangkok (BKK)")
    assert result.applied_rule_index == 0
    # Immediate stays neutral when 'during' present
    assert result.immediate_modifier == 1.0
    assert len(result.schedules) == 1
    sched = result.schedules[0]
    assert sched.start_date == date(2026, 6, 1)
    assert sched.end_date == date(2026, 8, 31)
    assert sched.modifier == 2.0
    assert sched.reason == "Summer sale"
    assert sched.ad_group_name == "Bangkok (BKK)"


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
