from collections.abc import Callable

import pytest

from detection.context import InMemoryContext
from detection.models import Company, Tender
from detection.rules import r08_non_competitive as r8

TF = Callable[..., Tender]
CF = Callable[..., Company]


# Every procurement method seen on awarded eTenders processes, 2017-2026.
@pytest.mark.parametrize(
    ("method", "fires"),
    [
        ("Request for Bid(Open-Tender)", False),
        ("Request for Quotation", False),
        ("Request for Proposal", False),
        ("Request for Bid(Limited-Tender", True),
        ("Single source bidding", True),
        ("Deviation", True),
        ("Transversal contract", False),
        ("SITA contract", False),
        ("Sole source bidding", True),
        ("Expression of interest", False),
        ("Request for Information", False),
        ("Procurement from other OoS", False),
        ("Restricted Bidding", True),
        ("Emergency Procurement", True),
        ("Participation", False),
        ("RFQ Above Threshold", False),
    ],
)
def test_method_classification(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext, method: str, fires: bool
) -> None:
    result = r8.evaluate(make_tender(procurement_method=method), make_company(), (), empty_ctx)

    assert result.evaluated
    assert result.fired is fires


def test_single_recorded_tenderer_fires_on_open_tender(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    tender = make_tender(procurement_method="Request for Bid(Open-Tender)", tenderer_ids=("t-1",))

    result = r8.evaluate(tender, make_company(), (), empty_ctx)

    assert result.fired
    assert result.evidence["basis"] == ["single recorded tenderer"]
    assert result.evidence["recorded_tenderers"] == 1


def test_both_grounds_are_reported(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    tender = make_tender(procurement_method="Deviation", tenderer_ids=("t-1",))

    result = r8.evaluate(tender, make_company(), (), empty_ctx)

    assert result.evidence["basis"] == ["single recorded tenderer", "non-open procedure"]
    assert result.score_contribution == 8


@pytest.mark.parametrize("tenderers", [("t-1", "t-2"), ()])
def test_multiple_or_empty_bidder_list_on_open_tender_clears(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext, tenderers: tuple[str, ...]
) -> None:
    tender = make_tender(procurement_method="Request for Proposal", tenderer_ids=tenderers)

    result = r8.evaluate(tender, make_company(), (), empty_ctx)

    assert result.evaluated
    assert not result.fired


def test_bidder_list_alone_is_enough_to_evaluate(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    result = r8.evaluate(
        make_tender(procurement_method=None, tenderer_ids=("t-1",)), make_company(), (), empty_ctx
    )

    assert result.fired
    assert result.evidence["procurement_method"] is None


@pytest.mark.parametrize("method", [None, "", "   "])
def test_not_evaluated_without_method_or_bidders(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext, method: str | None
) -> None:
    result = r8.evaluate(
        make_tender(procurement_method=method, tenderer_ids=None), make_company(), (), empty_ctx
    )

    assert not result.evaluated
