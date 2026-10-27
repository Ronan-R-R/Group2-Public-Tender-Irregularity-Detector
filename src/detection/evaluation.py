"""Evaluation of a scoring run: what fired, what could not run, and why.

Feeds Chapter 5. There is no labelled ground truth for South African tender
irregularities, so this measures behaviour rather than accuracy: firing and
coverage rates per rule, the score distribution, and how the Isolation Forest
signal relates to the price rules.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from detection.export import ScoredAward
from detection.scorer import RiskLevel

# Bands for the score histogram: the flag line is 50 and the alert line 75.
SCORE_BANDS: tuple[tuple[str, int, int], ...] = (
    ("0", 0, 0),
    ("1-24", 1, 24),
    ("25-49", 25, 49),
    ("50-74", 50, 74),
    ("75-100", 75, 100),
)
# The top share of the anomaly ranking examined against the price rules.
TOP_ANOMALY_SHARE = 0.01
# A value this many times its category median is probably a capture error.
CAPTURE_ERROR_RATIO = 100.0


@dataclass(frozen=True, slots=True)
class RuleStats:
    rule_id: str
    title: str
    severity: str
    evaluated: int
    fired: int
    not_evaluated: int
    reasons: tuple[tuple[str, int], ...]

    @property
    def fire_rate(self) -> float | None:
        """Share of evaluated awards on which the rule fired."""
        return self.fired / self.evaluated if self.evaluated else None


@dataclass(frozen=True, slots=True)
class AnomalyStats:
    scored: int
    top_n: int
    top_with_price_flag: int
    top_capture_errors: int


@dataclass(frozen=True, slots=True)
class Evaluation:
    awards: int
    rules: tuple[RuleStats, ...]
    levels: dict[str, int]
    score_bands: dict[str, int]
    max_score: int
    mean_coverage: float
    coverage_counts: dict[float, int]
    awards_with_a_flag: int
    anomaly: AnomalyStats | None
    rule_pairs: dict[tuple[str, str], int] = field(default_factory=dict)


def evaluate(scored: Sequence[ScoredAward]) -> Evaluation:
    if not scored:
        raise ValueError("nothing to evaluate")

    evaluated: Counter[str] = Counter()
    fired: Counter[str] = Counter()
    reasons: dict[str, Counter[str]] = {}
    meta: dict[str, tuple[str, str]] = {}
    pairs: Counter[tuple[str, str]] = Counter()
    for s in scored:
        fired_here = sorted((r.rule_id for r in s.score.breakdown if r.fired), key=_rule_key)
        for i, a in enumerate(fired_here):
            for b in fired_here[i + 1 :]:
                pairs[(a, b)] += 1
        for r in s.score.breakdown:
            meta.setdefault(r.rule_id, (r.title, r.severity.value))
            if r.evaluated:
                evaluated[r.rule_id] += 1
                fired[r.rule_id] += r.fired
            else:
                reason = str(r.evidence.get("reason", "no reason given"))
                reasons.setdefault(r.rule_id, Counter())[reason] += 1

    rules = tuple(
        RuleStats(
            rule_id=rule_id,
            title=meta[rule_id][0],
            severity=meta[rule_id][1],
            evaluated=evaluated[rule_id],
            fired=fired[rule_id],
            not_evaluated=sum(reasons.get(rule_id, Counter()).values()),
            reasons=tuple(reasons.get(rule_id, Counter()).most_common()),
        )
        for rule_id in sorted(meta, key=_rule_key)
    )

    levels = Counter(s.score.level.value for s in scored)
    bands = {
        label: sum(low <= s.score.score <= high for s in scored) for label, low, high in SCORE_BANDS
    }
    coverage = Counter(round(s.score.coverage, 3) for s in scored)

    return Evaluation(
        awards=len(scored),
        rules=rules,
        levels={level.value: levels[level.value] for level in RiskLevel},
        score_bands=bands,
        max_score=max(s.score.score for s in scored),
        mean_coverage=sum(s.score.coverage for s in scored) / len(scored),
        coverage_counts=dict(sorted(coverage.items())),
        awards_with_a_flag=sum(bool(s.score.fired) for s in scored),
        anomaly=_anomaly_stats(scored),
        rule_pairs=dict(pairs.most_common()),
    )


def _anomaly_stats(scored: Sequence[ScoredAward]) -> AnomalyStats | None:
    ranked = sorted(
        (s for s in scored if s.anomaly is not None),
        key=lambda s: s.anomaly.percentile if s.anomaly else 0.0,
        reverse=True,
    )
    if not ranked:
        return None
    top = ranked[: max(1, math.ceil(len(ranked) * TOP_ANOMALY_SHARE))]
    price_rules = {"R10", "R11"}
    return AnomalyStats(
        scored=len(ranked),
        top_n=len(top),
        top_with_price_flag=sum(
            any(r.fired and r.rule_id in price_rules for r in s.score.breakdown) for s in top
        ),
        top_capture_errors=sum(
            s.anomaly is not None
            and abs(s.anomaly.log_vs_category) >= math.log10(CAPTURE_ERROR_RATIO)
            for s in top
        ),
    )


def _rule_key(rule_id: str) -> int:
    return int(rule_id.removeprefix("R"))
