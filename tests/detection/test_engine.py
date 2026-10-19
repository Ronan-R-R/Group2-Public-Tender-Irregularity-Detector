from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from detection.context import DetectionContext, InMemoryContext
from detection.engine import RuleContractError, evaluate_award
from detection.models import Company, Director, RuleResult, Severity, Tender
from detection.rules import RULES, Rule
from detection.scorer import RiskLevel

TF = Callable[..., Tender]
CF = Callable[..., Company]


def test_registry_has_unique_ids_and_one_result_per_rule(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    ids = [r.rule_id for r in RULES]
    assert len(ids) == len(set(ids))

    result = evaluate_award(make_tender(), make_company(), (), empty_ctx)

    assert sorted(r.rule_id for r in result.breakdown) == sorted(ids)


def test_clean_established_supplier_scores_zero(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    result = evaluate_award(make_tender(), make_company(), (), empty_ctx)

    assert result.score == 0
    assert result.level is RiskLevel.NONE
    # With no award history there is nothing to compare prices against.
    # No bidder list (R5) and no history to compare prices against (R10, R11).
    assert {r.rule_id for r in result.not_evaluated} == {"R5", "R10", "R11"}


def test_new_mismatched_company_on_round_award(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    tender = make_tender(close_date=date(2025, 3, 14), award_value=Decimal("142000000"))
    company = make_company(
        registration_date=date(2025, 1, 31),
        industry="Construction of buildings",
        annual_return_dates=(),
    )

    result = evaluate_award(tender, company, (), empty_ctx)

    # Registered 42 days before close: R1, not R2. R3 clears: too young to be dormant.
    assert [r.rule_id for r in result.fired] == ["R1", "R9", "R12"]
    assert result.score == 15 + 8 + 3


def test_missing_cipc_data_reads_as_low_coverage_not_clean(
    make_tender: TF, empty_ctx: InMemoryContext
) -> None:
    company = Company(company_id="sup-001", name="Fictional Unmatched Trading")

    result = evaluate_award(make_tender(), company, (), empty_ctx)

    assert result.score == 0
    assert {r.rule_id for r in result.not_evaluated} == {
        "R1", "R2", "R3", "R4", "R5", "R6", "R9", "R10", "R11"
    }  # fmt: skip
    assert result.coverage == pytest.approx(3 / 12)


def test_rejects_company_that_is_not_the_supplier(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    with pytest.raises(ValueError, match="not the supplier"):
        evaluate_award(make_tender(), make_company(company_id="sup-999"), (), empty_ctx)


def test_stops_on_rule_that_mislabels_its_result(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    def mislabelled(
        tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
    ) -> RuleResult:
        return RuleResult.fire("R7", "wrong rule", Severity.MEDIUM, {})

    rogue = replace(RULES[0], evaluate=mislabelled)

    with pytest.raises(RuleContractError, match="R1"):
        evaluate_award(make_tender(), make_company(), (), empty_ctx, rules=[rogue])


def test_stops_on_rule_that_changes_severity(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    def inflated(
        tender: Tender, company: Company, directors: Sequence[Director], ctx: DetectionContext
    ) -> RuleResult:
        return RuleResult.fire("R12", "round", Severity.CRITICAL, {})

    rule = Rule("R12", "round", Severity.LOW, inflated)

    with pytest.raises(RuleContractError, match="severity critical"):
        evaluate_award(make_tender(), make_company(), (), empty_ctx, rules=[rule])
