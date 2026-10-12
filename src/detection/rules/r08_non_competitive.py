"""R8: award made without effective competition.

Fires when exactly one tenderer is recorded, or when the procurement method
is single-source, sole-source, deviation, limited, restricted or emergency.

Source: Fazekas, Toth and King (2016). Single-bidder outcomes and non-open
procedure types are both inputs to their Corruption Risk Index.

The method check exists because eTenders rarely publishes bidder lists: only
1,361 of 9,209 awarded processes list tenderers, so a bidder count alone
would leave this rule unevaluated almost everywhere. Transversal, SITA and
other-organ-of-state contracts are call-offs from contracts competed
elsewhere and do not fire.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, JSONValue, RuleResult, Severity, Tender
from detection.sectors import normalise

RULE_ID = "R8"
TITLE = "Non-competitive award: single bidder or non-open procedure"
SEVERITY = Severity.MEDIUM

NON_COMPETITIVE_MARKERS = (
    "single source",
    "sole source",
    "deviation",
    "limited",
    "restricted",
    "emergency",
)


def non_competitive_method(method: str) -> bool:
    key = normalise(method)
    return any(marker in key for marker in NON_COMPETITIVE_MARKERS)


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    method = (tender.procurement_method or "").strip() or None
    bidders = tender.tenderer_ids
    if method is None and bidders is None:
        return RuleResult.not_evaluated(
            RULE_ID, TITLE, SEVERITY, "neither procurement method nor bidder list published"
        )

    single_bidder = bidders is not None and len(bidders) == 1
    non_open = method is not None and non_competitive_method(method)
    basis: list[JSONValue] = []
    if single_bidder:
        basis.append("single recorded tenderer")
    if non_open:
        basis.append("non-open procedure")
    evidence: dict[str, JSONValue] = {
        "procurement_method": method,
        "recorded_tenderers": None if bidders is None else len(bidders),
        "basis": basis,
    }
    if basis:
        return RuleResult.fire(RULE_ID, TITLE, SEVERITY, evidence)
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
