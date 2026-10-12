"""R9: winner's registered industry shares no sector with the tender.

Source: World Bank Group (2013) and Transparency International (2014) both
flag awards to bidders without relevant experience or capacity for the work,
a pattern consistent with front companies and subcontracted-out awards.

Matching goes through sector groups in ``detection.sectors`` rather than
exact labels. Generic or unmapped labels on either side are not evaluated,
so a vague category never counts as a mismatch.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, JSONValue, RuleResult, Severity, Tender
from detection.sectors import company_sectors, is_generic, tender_sectors

RULE_ID = "R9"
TITLE = "Company industry does not match tender category"
SEVERITY = Severity.MEDIUM


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    if not tender.category:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "tender category not published")
    if not company.industry:
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "CIPC industry unknown")

    tender_groups = tender_sectors(tender.category)
    if tender_groups is None:
        reason = "too broad to compare" if is_generic(tender.category) else "not mapped"
        return RuleResult.not_evaluated(
            RULE_ID, TITLE, SEVERITY, f"tender category {reason}: {tender.category}"
        )
    company_groups = company_sectors(company.industry)
    if company_groups is None:
        reason = "too broad to compare" if is_generic(company.industry) else "not mapped"
        return RuleResult.not_evaluated(
            RULE_ID, TITLE, SEVERITY, f"company industry {reason}: {company.industry}"
        )

    tender_list: list[JSONValue] = [g for g in sorted(tender_groups)]
    company_list: list[JSONValue] = [g for g in sorted(company_groups)]
    evidence: dict[str, JSONValue] = {
        "tender_category": tender.category,
        "company_industry": company.industry,
        "tender_sectors": tender_list,
        "company_sectors": company_list,
    }
    if tender_groups.isdisjoint(company_groups):
        return RuleResult.fire(RULE_ID, TITLE, SEVERITY, evidence)
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
