from collections.abc import Callable
from decimal import Decimal

import pytest

from detection.context import InMemoryContext
from detection.models import Company, Tender
from detection.rules import r12_round_value as r12

TF = Callable[..., Tender]
CF = Callable[..., Company]


@pytest.mark.parametrize(
    ("value", "fires", "multiple_of"),
    [
        ("142500000", True, 100_000),
        ("142500000.00", True, 100_000),
        ("142537250", False, None),
        ("142000000", True, 1_000_000),
        ("142100000.00", True, 100_000),
        ("100000", True, 100_000),
        ("1287450.36", False, None),
        ("99999.99", False, None),
        ("50000", False, None),
        ("142100000.50", False, None),
        ("0", False, None),
    ],
)
def test_fires_on_multiples_of_100k(
    make_tender: TF,
    make_company: CF,
    empty_ctx: InMemoryContext,
    value: str,
    fires: bool,
    multiple_of: int | None,
) -> None:
    result = r12.evaluate(make_tender(award_value=Decimal(value)), make_company(), (), empty_ctx)

    assert result.evaluated
    assert result.fired is fires
    assert result.evidence["multiple_of"] == multiple_of
    assert result.evidence["award_value"] == value


def test_contributes_low_weight(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    result = r12.evaluate(
        make_tender(award_value=Decimal("3000000")), make_company(), (), empty_ctx
    )

    assert result.score_contribution == 3


def test_not_evaluated_without_value(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    result = r12.evaluate(make_tender(award_value=None), make_company(), (), empty_ctx)

    assert not result.evaluated
