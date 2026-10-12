"""R10: award value more than 2 robust SDs above comparable awards.

Source: Transparency International (2014) and World Bank Group (2013) both
list prices well above market or comparable contracts as a red flag for
inflated pricing and kickbacks.

How "comparable" and "standard deviation" are computed on real eTenders data
is explained in ``detection.rules._pricing``.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, RuleResult, Severity, Tender
from detection.rules._pricing import compare_price

RULE_ID = "R10"
TITLE = "Award value far above comparable awards"
SEVERITY = Severity.HIGH

THRESHOLD = 2.0


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    comparison = compare_price(tender, ctx)
    if isinstance(comparison, str):
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, comparison)
    if comparison.robust_z > THRESHOLD:
        return RuleResult.fire(RULE_ID, TITLE, SEVERITY, comparison.evidence)
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, comparison.evidence)
