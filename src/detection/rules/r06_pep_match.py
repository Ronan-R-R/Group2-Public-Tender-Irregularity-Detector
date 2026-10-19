"""R6: a director of the winner matches a politically exposed persons list.

Source: Fazekas and Kocsis (2020) show politically connected suppliers as a
high-level corruption risk; Transparency International (2014) lists
undeclared political connections of bidders as a conflict-of-interest flag.

Always marked for human review: a name match is not proof of identity, and
being politically exposed is not wrongdoing. Only the count of matched
directors is public; who matched, the list and the match score stay in
private evidence. Matches below MIN_MATCH_SCORE are ignored.
"""

from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, JSONValue, RuleResult, Severity, Tender
from detection.rules._directors import active_on, cipc_matched

RULE_ID = "R6"
TITLE = "Director matches a politically exposed persons list"
SEVERITY = Severity.CRITICAL

MIN_MATCH_SCORE = 0.9


def evaluate(
    tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
) -> RuleResult:
    if not cipc_matched(company):
        return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "supplier not matched to CIPC")

    in_office = active_on(directors, tender.close_date)
    matches: list[JSONValue] = []
    matched_directors = 0
    for director in in_office:
        found = ctx.pep_matches(director.director_id)
        if found is None:
            return RuleResult.not_evaluated(RULE_ID, TITLE, SEVERITY, "PEP screening not run")
        strong = [m for m in found if m.match_score >= MIN_MATCH_SCORE]
        if strong:
            matched_directors += 1
        matches.extend(
            {
                "director_id": director.director_id,
                "director_name": director.full_name,
                "source": m.source,
                "source_ref": m.source_ref,
                "match_score": m.match_score,
            }
            for m in strong
        )

    evidence: dict[str, JSONValue] = {
        "directors_checked": len(in_office),
        "matched_directors": matched_directors,
    }
    if matched_directors:
        return RuleResult.fire(
            RULE_ID,
            TITLE,
            SEVERITY,
            evidence,
            private_evidence={"matches": matches},
            needs_review=True,
        )
    return RuleResult.clear(RULE_ID, TITLE, SEVERITY, evidence)
