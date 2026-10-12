"""R11: award value more than 2 robust SDs below comparable awards.

Source: World Bank Group (2013) and Transparency International (2014) flag
abnormally low winning prices: a bidder may underbid to win and recover the
difference through variation orders and contract extensions.

How "comparable" and "standard deviation" are computed on real eTenders data
is explained in ``detection.rules._pricing``.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, RuleResult, Severity, Tender
from detection.rules._pricing import compare_price

RULE_ID = "R11"
TITLE = "Award value far below comparable awards"
SEVERITY = Severity.MEDIUM

THRESHOLD = -2.0


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    comparison = compare_price(tender, ctx)
    if isinstance(comparison, str):
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, comparison)
    if comparison.robust_z < THRESHOLD:
        return RuleResult.fire(RULE_ID, TITLE, SEVERITY, comparison.evidence)
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, comparison.evidence)
