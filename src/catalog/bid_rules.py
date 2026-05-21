"""Declarative bid-rules engine.

Rules are first-match-wins, mirroring Google Ads behavior. Each rule has an
`if` clause that's a simple comparison against product attributes, plus
either an immediate `then.modifier` or a time-windowed `during` clause.

A `during` rule acts as a SEASONALITY OVERLAY:
  - When `today ∈ [start, end]` the rule wins immediately exactly as if it
    were a non-during rule, AND a `BidSchedule` is emitted for documentation.
  - When `today` is outside the window the rule is skipped for the immediate
    decision (next rule evaluated), but a `BidSchedule` is STILL emitted so
    the operator/auditor can see the full year's plan.

Place during-rules FIRST in the YAML to use them as overlays on top of a
base ladder — outside the window they fall through cleanly to the base.

Example YAML:
    bid_rules:
      # Summer-sale overlay — overrides the base ladder while active.
      - if: discount_pct >= 0.50
        during: { start: 2026-05-20, end: 2026-08-31 }
        then: { modifier: 3.0, reason: "Summer sale — top tier" }
      - if: discount_pct >= 0.30
        during: { start: 2026-05-20, end: 2026-08-31 }
        then: { modifier: 2.5, reason: "Summer sale — strong discounts" }
      # Base ladder — always-on.
      - if: discount_pct >= 0.50
        then: { modifier: 2.25 }
      - if: discount_pct >= 0.30
        then: { modifier: 1.80 }

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
    *,
    today: date | None = None,
) -> BidApplicationResult:
    """Evaluate rules against a product. First match wins for the IMMEDIATE
    modifier; BidSchedules are collected for documentation.

    v0.3.5 seasonality semantics:

    - Rules WITHOUT a `during:` clause fire normally when matched: the
      modifier is applied immediately and rule evaluation stops.

    - Rules WITH a `during:` clause act as SEASONALITY OVERLAYS:
        * They ALWAYS emit a `BidSchedule` when their `if:` matches, so the
          full year's plan is captured in `10_bid_schedules.csv` regardless
          of when the build runs.
        * They fire IMMEDIATELY (winning the first-match contest) only when
          `today ∈ [start, end]`. Outside the window they are transparent —
          the next matching rule wins for the immediate decision.

    This means a YAML where overlays are placed FIRST behaves correctly both
    inside and outside the sale window:
        in-window  → overlay wins → boosted modifier applied
        out-window → overlay skipped → base ladder applies normally

    `today` defaults to `date.today()`. Tests pass an explicit date to
    deterministically exercise either branch.
    """
    if today is None:
        today = date.today()
    result = BidApplicationResult()
    immediate_locked = False
    # Track which `during:` windows have already emitted a schedule for this
    # product. Same-window cascading rules (e.g. summer/50%+, summer/40-49%,
    # summer/30-39%) are first-match-wins per window — a 55% product only
    # emits the 50%+ summer schedule, not all three. DIFFERENT windows
    # (summer + winter) each get their own emission.
    emitted_windows: set[tuple[date, date]] = set()
    for idx, rule in enumerate(rules.rules):
        try:
            parsed = parse_expression(rule.if_)
        except ValueError as exc:
            logger.warning("Skipping malformed rule %d: %s", idx, exc)
            continue
        if not parsed.evaluate(product):
            continue
        # The `if` matched. Branch on whether this is an overlay or a base
        # rule.
        if rule.during is not None:
            window_key = (rule.during.start, rule.during.end)
            if window_key not in emitted_windows:
                # First rule to match for this window — record the schedule.
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
                emitted_windows.add(window_key)
                # If the window is active today AND no overlay has locked
                # the immediate decision yet, this overlay wins first-match.
                if not immediate_locked and rule.during.start <= today <= rule.during.end:
                    result.immediate_modifier = rule.then.modifier
                    result.applied_rule_index = idx
                    immediate_locked = True
            # Either way, keep scanning — a different window or a base rule
            # may still need to fire.
            continue
        # Non-during rule. Wins first-match on the immediate side iff no
        # active overlay already locked it. Either way, we stop scanning:
        # the base ladder is mutually exclusive at the immediate level.
        if not immediate_locked:
            result.immediate_modifier = rule.then.modifier
            result.applied_rule_index = idx
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
