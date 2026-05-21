"""Declarative bid-rules engine.

Rules are first-match-wins, mirroring Google Ads behavior. Each rule has an
`if` clause that's a simple comparison against product attributes, plus
either an immediate `then.modifier` or a time-windowed `during` clause that
generates a `BidSchedule`.

Example YAML:
    bid_rules:
      - if: discount_pct >= 30
        then: { modifier: 1.5 }
      - if: discount_pct >= 15
        then: { modifier: 1.25 }
      - if: from_price < 100
        then: { modifier: 1.1 }
      - if: discount_pct >= 25
        during: { start: 2026-06-01, end: 2026-08-31 }
        then: { modifier: 2.0, reason: "Summer sale" }

This is intentionally a tiny DSL — full arithmetic is YAGNI for v0.3
(decided in §8 of the planning doc).
"""

from __future__ import annotations

import logging
import operator
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from pydantic import BaseModel, Field, model_validator

from src.models.campaign import BidSchedule
from src.models.catalog import Product

logger = logging.getLogger(__name__)


# Supported comparison operators
_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
}

# Order longest-first so ">=" is matched before ">"
_OPERATOR_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|==|!=|>|<)\s*(.+?)\s*$"
)


@dataclass
class _ParsedExpression:
    attribute: str
    op_name: str
    op: Callable[[Any, Any], bool]
    value: Any

    def evaluate(self, product: Product) -> bool:
        if self.attribute == "sku":
            attr_val: Any = product.sku
        elif self.attribute == "name":
            attr_val = product.name
        else:
            attr_val = product.attributes.get(self.attribute)
        if attr_val is None:
            return False
        try:
            return bool(self.op(attr_val, self.value))
        except TypeError:
            # E.g. comparing str to int — not a match, don't crash
            return False


def _coerce_value(raw: str) -> Any:
    """Parse a string RHS into the right Python type."""
    s = raw.strip()
    # Strip wrapping quotes if present
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    # Boolean
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    # None
    if s.lower() == "none" or s.lower() == "null":
        return None
    # Numeric
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def parse_expression(expr: str) -> _ParsedExpression:
    m = _OPERATOR_RE.match(expr)
    if not m:
        raise ValueError(
            f"Could not parse bid-rule expression {expr!r}. "
            "Expected: 'attribute OPERATOR value' (e.g. 'discount_pct >= 30')"
        )
    attr, op_str, raw_val = m.group(1), m.group(2), m.group(3)
    op = _OPERATORS[op_str]
    val = _coerce_value(raw_val)
    return _ParsedExpression(attribute=attr, op_name=op_str, op=op, value=val)


class _DuringClause(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self) -> "_DuringClause":
        if self.end < self.start:
            raise ValueError("during.end must be >= during.start")
        return self


class _ThenClause(BaseModel):
    modifier: float = Field(ge=0.1, le=10.0)
    reason: str = ""


class BidRule(BaseModel):
    """One declarative bid rule."""

    if_: str = Field(alias="if")
    then: _ThenClause
    during: _DuringClause | None = None

    model_config = {"populate_by_name": True}


class BidRuleSet(BaseModel):
    rules: list[BidRule] = Field(default_factory=list)


def parse_rules(raw: list[dict]) -> BidRuleSet:
    """Validate + parse a YAML/JSON list of rule dicts."""
    return BidRuleSet(rules=[BidRule.model_validate(r) for r in raw])


@dataclass
class BidApplicationResult:
    immediate_modifier: float = 1.0  # what was applied to the ad group right now
    schedules: list[BidSchedule] | None = None
    applied_rule_index: int | None = None  # which rule won (None ⇒ none)

    def __post_init__(self) -> None:
        if self.schedules is None:
            self.schedules = []


def apply_rules(
    product: Product,
    rules: BidRuleSet,
    campaign_name: str,
    ad_group_name: str,
) -> BidApplicationResult:
    """Evaluate rules against a product. First match wins.

    Rules with a `during` clause emit a `BidSchedule` and the immediate
    modifier stays at 1.0. Rules without `during` apply the modifier directly
    to the ad group.
    """
    result = BidApplicationResult()
    for idx, rule in enumerate(rules.rules):
        try:
            parsed = parse_expression(rule.if_)
        except ValueError as exc:
            logger.warning("Skipping malformed rule %d: %s", idx, exc)
            continue
        if not parsed.evaluate(product):
            continue
        # Match
        result.applied_rule_index = idx
        if rule.during is not None:
            result.schedules.append(
                BidSchedule(
                    campaign_name=campaign_name,
                    ad_group_name=ad_group_name,
                    start_date=rule.during.start,
                    end_date=rule.during.end,
                    modifier=rule.then.modifier,
                    reason=rule.then.reason,
                )
            )
        else:
            result.immediate_modifier = rule.then.modifier
        return result
    return result


__all__ = [
    "BidRule",
    "BidRuleSet",
    "parse_rules",
    "parse_expression",
    "apply_rules",
    "BidApplicationResult",
]
