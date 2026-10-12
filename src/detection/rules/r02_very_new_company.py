"""R2: winner registered fewer than 30 days before the tender closed.

Source: Transparency International (2014) and World Bank Group (2013), as for
R1. Under 30 days leaves almost no time to trade, so this is critical rather
than high.

A registration date after the close date also fires. It means either the
bidder did not exist when bids closed, or the CIPC record was matched to the
wrong company. Both need a human to look, and the evidence says which case it
is through ``registered_after_close``.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, JSONValue, RuleResult, Severity, Tender

RULE_ID = "R2"
TITLE = "Company registered under 30 days before tender close"
SEVERITY = Severity.CRITICAL

MAX_DAYS = 30


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    if tender.close_date is None:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "tender close date not published")
    if company.registration_date is None:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "CIPC registration date unknown")

    days = (tender.close_date - company.registration_date).days
    evidence: dict[str, JSONValue] = {
        "registration_date": company.registration_date.isoformat(),
        "close_date": tender.close_date.isoformat(),
        "days_registered_before_close": days,
        "registered_after_close": days < 0,
    }
    if days < MAX_DAYS:
        return RuleResult.fire(RULE_ID, TITLE, SEVERITY, evidence)
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
