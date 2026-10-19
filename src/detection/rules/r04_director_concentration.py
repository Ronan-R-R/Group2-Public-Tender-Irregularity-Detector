"""R4: a director of the winner sits on 3+ companies that won from the same
buyer in the 12 months to close.

Source: World Bank Group (2013) and Transparency International (2014) list
bidders linked through common directors or owners as a collusion red flag:
several "independent" winners controlled by the same people can share one
buyer's work between them.

Counts distinct companies, this supplier included, for which the director
was in office when that company's award closed. Directorships with unknown
dates count as in office.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from detection.context import DetectionContext
from detection.models import Company, Director, JSONValue, RuleResult, Severity, Tender
from detection.rules._dates import months_before
from detection.rules._directors import active_on, cipc_matched

RULE_ID = "R4"
TITLE = "Director on 3+ companies winning from the same buyer in 12 months"
SEVERITY = Severity.HIGH

WINDOW_MONTHS = 12
MIN_COMPANIES = 3
MAX_LISTED = 20


def _in_office(ctx: DetectionContext, company_id: str, director_id: str, day: date) -> bool:
    record = next((d for d in ctx.directors_of(company_id) if d.director_id == director_id), None)
    return record is None or record.active_on(day)


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    if tender.close_date is None:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "tender close date not published")
    if not cipc_matched(company):
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "supplier not matched to CIPC")

    close = tender.close_date
    start = months_before(close, WINDOW_MONTHS)
    award_days: dict[str, list[date]] = defaultdict(list)
    for award in ctx.awards_by_buyer(tender.buyer_id, start, close):
        if award.close_date is not None:
            award_days[award.supplier_id].append(award.close_date)

    in_office = active_on(directors, close)
    best: tuple[Director, set[str]] | None = None
    for director in in_office:
        linked = {tender.supplier_id}
        for other in ctx.companies_of(director.director_id):
            if other in linked:
                continue
            if any(_in_office(ctx, other, director.director_id, day) for day in award_days[other]):
                linked.add(other)
        if best is None or len(linked) > len(best[1]):
            best = (director, linked)

    evidence: dict[str, JSONValue] = {
        "buyer_id": tender.buyer_id,
        "buyer_name": tender.buyer_name,
        "window_start": start.isoformat(),
        "window_end": close.isoformat(),
        "directors_checked": len(in_office),
    }
    if best is None:
        evidence["company_count"] = 1
        return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)

    director, linked = best
    listed: list[JSONValue] = [c for c in sorted(linked)[:MAX_LISTED]]
    evidence.update(
        {"director_id": director.director_id, "company_count": len(linked), "companies": listed}
    )
    if len(linked) >= MIN_COMPANIES:
        return RuleResult.fire(
            RULE_ID,
            TITLE,
            SEVERITY,
            evidence,
            private_evidence={"director_name": director.full_name},
        )
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
