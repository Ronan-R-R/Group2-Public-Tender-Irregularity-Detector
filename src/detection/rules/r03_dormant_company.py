"""R3: winner filed no CIPC annual return in the 24 months before close.

Source: World Bank Group (2013) and Transparency International (2014) list
shell and dormant entities among bidder-qualification red flags. A company
that stopped filing and then wins a public contract may be a dormant shell
reactivated for the award.

A company younger than 24 months with no filings yet is not dormant, so it
clears. A company with no filings and an unknown registration date cannot be
judged and is not evaluated.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, JSONValue, RuleResult, Severity, Tender
from detection.rules._dates import months_before

RULE_ID = "R3"
TITLE = "Company dormant for over 24 months before winning"
SEVERITY = Severity.MEDIUM

DORMANT_MONTHS = 24


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    if tender.close_date is None:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "tender close date not published")
    if company.annual_return_dates is None:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "CIPC filing history unknown")

    close = tender.close_date
    cutoff = months_before(close, DORMANT_MONTHS)
    filed_before_close = [d for d in company.annual_return_dates if d <= close]

    if filed_before_close:
        last = max(filed_before_close)
        evidence: dict[str, JSONValue] = {
            "close_date": close.isoformat(),
            "last_annual_return": last.isoformat(),
            "days_since_last_annual_return": (close - last).days,
        }
        if last < cutoff:
            return RuleResult.fire(RULE_ID, TITLE, SEVERITY, evidence)
        return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)

    if company.registration_date is None:
        return RuleResult.not_evaluated(
            RULE_ID, TITLE, SEVERITY, "no annual returns on record and registration date unknown"
        )
    evidence = {
        "close_date": close.isoformat(),
        "last_annual_return": None,
        "registration_date": company.registration_date.isoformat(),
    }
    if company.registration_date < cutoff:
        return RuleResult.fire(RULE_ID, TITLE, SEVERITY, evidence)
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
