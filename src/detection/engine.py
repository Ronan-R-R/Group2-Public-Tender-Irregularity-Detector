from __future__ import annotations

from collections.abc import Sequence

from detection.context import DetectionContext
from detection.models import Company, Director, Tender
from detection.rules import RULES, Rule
from detection.scorer import CompositeRiskScore, score


class RuleContractError(RuntimeError):
    """A rule returned a result that does not describe itself."""


def evaluate_award(
    tender: Tender,
    company: Company,
    directors: Sequence[Director],
    ctx: DetectionContext,
    rules: Sequence[Rule] = RULES,
) -> CompositeRiskScore:
    if company.company_id != tender.supplier_id:
        raise ValueError(
            f"company {company.company_id} is not the supplier {tender.supplier_id} "
            f"on {tender.tender_id}"
        )
    results = []
    for rule in rules:
        result = rule.evaluate(tender, company, directors, ctx)
        # A mislabelled result would put points against the wrong rule in the
        # published breakdown, so it stops the run instead of being scored.
        if (result.rule_id, result.severity) != (rule.rule_id, rule.severity):
            raise RuleContractError(
                f"rule {rule.rule_id} returned a result for {result.rule_id} "
                f"with severity {result.severity.value}"
            )
        results.append(result)
    return score(results)
