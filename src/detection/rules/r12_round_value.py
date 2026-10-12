"""R12: award value is an exact multiple of R100 000.

Source: none of the three core frameworks (Transparency International 2014,
World Bank Group 2013, Fazekas, Toth and King 2016) define this indicator.
It comes from forensic analytics, where round-number testing is a standard
check for negotiated or fabricated amounts (Nigrini, 2012, Benford's Law:
Applications for Forensic Accounting, Auditing, and Fraud Detection, Wiley).

Base rate on the eTenders OCDS feed (2017-2026): 9.9% of awards with a value
are multiples of R100 000 and 6.4% of R1 000 000. Many of those will be
officials capturing rounded figures, which is why this rule is low severity.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from detection.context import DetectionContext
from detection.models import Company, Director, RuleResult, Severity, Tender

RULE_ID = "R12"
TITLE = "Award value is a suspiciously round number"
SEVERITY = Severity.LOW

ROUND_UNITS = (Decimal(1_000_000), Decimal(100_000))


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    value = tender.award_value
    if value is None:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "award value not published")

    evidence: dict[str, str | int | None] = {"award_value": str(value), "multiple_of": None}
    if value <= 0:
        return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
    for unit in ROUND_UNITS:
        if value % unit == 0:
            evidence["multiple_of"] = int(unit)
            return RuleResult.fire(RULE_ID, TITLE, SEVERITY, evidence)
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
