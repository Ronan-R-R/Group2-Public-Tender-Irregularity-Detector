from dataclasses import dataclass
from typing import Iterable, Optional

from .name_match import name_similarity, classify_match

@dataclass
class CompanyMatchResult:
    matched_company_name: Optional[str]
    confidence: float
    status: str  # exact, strong_fuzzy, needs_review, no_match
    source: str  # cipc, opencorporates, sample

def match_supplier_to_company(
    supplier_name: str,
    company_names: Iterable[str],
    *,
    source: str = "sample",
) -> CompanyMatchResult:
    # Score every candidate so we can compare the best match with the runner-up.
    scored = [
        (company_name, name_similarity(supplier_name, company_name))
        for company_name in company_names
    ]

    # An empty candidate list means there is nothing to match against.
    if not scored:
        return CompanyMatchResult(None, 0.0, "no_match", source)

    # Put the strongest candidate first.
    scored.sort(key=lambda item: item[1], reverse=True)
    best_name, best_score = scored[0]

    # If there is only one candidate, there is no runner-up to cause ambiguity.
    second_score = scored[1][1] if len(scored) > 1 else 0.0
    gap = best_score - second_score

    status = classify_match(best_score)

    # Two similar candidates are uncertain, even if the best score is high.
    if len(scored) > 1 and best_score >= 0.60 and gap < 0.05:
        status = "needs_review"

    # Do not return a company suggestion when the name is a poor match.
    if status == "no_match":
        return CompanyMatchResult(None, best_score, status, source)

    # Keep the top suggestion for manual review when the match is ambiguous.
    return CompanyMatchResult(best_name, best_score, status, source)