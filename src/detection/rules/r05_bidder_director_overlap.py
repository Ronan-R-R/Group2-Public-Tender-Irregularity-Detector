"""R5: the winner shares a director with a losing bidder on the same tender.

Source: World Bank Group (2013) and Transparency International (2014) treat
common directors across competing bidders as a primary indicator of bid
rigging: "competing" bids from companies under the same control give the
appearance of competition without its substance.

Needs a genuine bid list. eTenders rarely publishes one (the loader treats
its tenderer lists as unpublished, see ingestion.ocds), so this rule is not
evaluated on that feed until another source supplies bidders. Directors are
compared as in office on the tender close date, when bids were submitted.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, JSONValue, RuleResult, Severity, Tender
from detection.rules._directors import active_on, cipc_matched

RULE_ID = "R5"
TITLE = "Director overlap between winner and losing bidders"
SEVERITY = Severity.CRITICAL


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    if tender.tenderer_ids is None:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "bidder list not published")
    if not cipc_matched(company):
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "supplier not matched to CIPC")

    losers = sorted(set(tender.tenderer_ids) - {tender.supplier_id})
    day = tender.close_date
    winner = {d.director_id: d for d in active_on(directors, day)}

    checked: list[str] = []
    overlaps: dict[str, list[str]] = {}
    for bidder in losers:
        record = ctx.company(bidder)
        if record is None or not cipc_matched(record):
            continue
        checked.append(bidder)
        theirs = {d.director_id for d in active_on(ctx.directors_of(bidder), day)}
        shared = sorted(winner.keys() & theirs)
        if shared:
            overlaps[bidder] = shared

    if losers and not checked:
        return RuleResult.not_evaluated(
            RULE_ID, TITLE, SEVERITY, "no losing bidder matched to CIPC"
        )

    shared_ids = sorted({d for ids in overlaps.values() for d in ids})
    overlapping: list[JSONValue] = [b for b in sorted(overlaps)]
    shared_public: list[JSONValue] = [d for d in shared_ids]
    evidence: dict[str, JSONValue] = {
        "losing_bidders": len(losers),
        "bidders_checked": len(checked),
        "overlapping_bidders": overlapping,
        "shared_director_ids": shared_public,
    }
    if overlaps:
        names: list[JSONValue] = [winner[d].full_name for d in shared_ids]
        return RuleResult.fire(
            RULE_ID, TITLE, SEVERITY, evidence, private_evidence={"director_names": names}
        )
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
