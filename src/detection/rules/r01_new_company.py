"""R1: winner registered 30 to 89 days before the tender closed.

Source: Transparency International (2014) and World Bank Group (2013) both
treat a recently incorporated winner as a bidder-qualification red flag: a
company formed shortly before a tender has no trading history and may exist
only to receive that award.

R2 covers registrations under 30 days. The two bands do not overlap, so one
registration date can fire at most one of them.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, JSONValue, RuleResult, Severity, Tender

RULE_ID = "R1"
TITLE = "Company registered 30-89 days before tender close"
SEVERITY = Severity.HIGH

MIN_DAYS = 30
MAX_DAYS = 90


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
    }
    if MIN_DAYS <= days < MAX_DAYS:
        return RuleResult.fire(RULE_ID, TITLE, SEVERITY, evidence)
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
