"""R7: supplier won 5+ awards from the same buyer in the 24 months to close.

Source: Fazekas, Toth and King (2016) treat concentration of a buyer's
contracts on one supplier as a corruption-risk signal; Transparency
International (2014) lists repeated awards to the same supplier among its
red flags for favouritism.

Counts distinct contracting processes (OCIDs), so one panel tender with
several award lines to the same supplier counts once. Only awards closing on
or before this award's close date count: the rule asks what was known at the
time, not what happened later.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, JSONValue, RuleResult, Severity, Tender
from detection.rules._dates import months_before

RULE_ID = "R7"
TITLE = "Repeat winner: 5+ awards from the same buyer in 24 months"
SEVERITY = Severity.MEDIUM

WINDOW_MONTHS = 24
MIN_AWARDS = 5
MAX_LISTED = 20


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    if tender.close_date is None:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "tender close date not published")

    start = months_before(tender.close_date, WINDOW_MONTHS)
    history = ctx.awards_by_buyer(tender.buyer_id, start, tender.close_date)
    ocids = sorted({a.ocid for a in history if a.supplier_id == tender.supplier_id} | {tender.ocid})
    listed: list[JSONValue] = [o for o in ocids[:MAX_LISTED]]
    evidence: dict[str, JSONValue] = {
        "buyer_id": tender.buyer_id,
        "buyer_name": tender.buyer_name,
        "window_start": start.isoformat(),
        "window_end": tender.close_date.isoformat(),
        "award_count": len(ocids),
        "ocids": listed,
    }
    if len(ocids) >= MIN_AWARDS:
        return RuleResult.fire(RULE_ID, TITLE, SEVERITY, evidence)
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
