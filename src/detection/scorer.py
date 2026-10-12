"""Composite risk score: severity-weighted sum of fired rules, capped at 100.

The Isolation Forest output is deliberately not an input here. It is a
separate signal reported next to this score, because R10/R11 already score
price outliers and adding both would count one price twice.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from detection.models import RuleResult

MAX_SCORE = 100
FLAG_THRESHOLD = 50
ALERT_THRESHOLD = 75


class RiskLevel(Enum):
    NONE = "none"
    FLAG = "flag"
    ALERT = "alert"


@dataclass(frozen=True, slots=True)
class CompositeRiskScore:
    score: int
    uncapped_score: int
    level: RiskLevel
    # Fired rules first, highest contribution first, so a dashboard can render
    # the list in order without re-sorting.
    breakdown: tuple[RuleResult, ...]
    needs_review: bool

    @property
    def fired(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.breakdown if r.fired)

    @property
    def not_evaluated(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.breakdown if not r.evaluated)

    @property
    def coverage(self) -> float:
        """Share of rules that could be evaluated.

        A score of 0 with coverage 0.3 means "not enough data", not "clean".
        """
        if not self.breakdown:
            return 0.0
        return sum(r.evaluated for r in self.breakdown) / len(self.breakdown)


def risk_level(score: int) -> RiskLevel:
    if score >= ALERT_THRESHOLD:
        return RiskLevel.ALERT
    if score >= FLAG_THRESHOLD:
        return RiskLevel.FLAG
    return RiskLevel.NONE


def _rule_order(rule_id: str) -> tuple[str, int]:
    """Sort R2 before R10."""
    prefix = rule_id.rstrip("0123456789")
    digits = rule_id[len(prefix) :]
    return prefix, int(digits) if digits else -1


def score(results: Iterable[RuleResult]) -> CompositeRiskScore:
    results = tuple(results)
    duplicates = sorted(rid for rid, n in Counter(r.rule_id for r in results).items() if n > 1)
    if duplicates:
        raise ValueError(f"duplicate rule results: {', '.join(duplicates)}")

    uncapped = sum(r.score_contribution for r in results)
    capped = min(uncapped, MAX_SCORE)
    breakdown = tuple(
        sorted(results, key=lambda r: (not r.fired, -r.score_contribution, _rule_order(r.rule_id)))
    )
    return CompositeRiskScore(
        score=capped,
        uncapped_score=uncapped,
        level=risk_level(capped),
        breakdown=breakdown,
        needs_review=any(r.needs_review for r in results),
    )
