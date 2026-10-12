"""R1 and R2: registration age bands. Tests both rules together because the
bands must partition the timeline without overlap."""

from collections.abc import Callable
from datetime import date, timedelta

import pytest

from detection.context import InMemoryContext
from detection.models import Company, Tender
from detection.rules import r01_new_company as r1
from detection.rules import r02_very_new_company as r2

CLOSE = date(2025, 3, 14)

TF = Callable[..., Tender]
CF = Callable[..., Company]


def registered(days_before_close: int) -> date:
    return CLOSE - timedelta(days=days_before_close)


@pytest.mark.parametrize(
    ("days", "r1_fires", "r2_fires"),
    [
        (-5, False, True),
        (0, False, True),
        (29, False, True),
        (30, True, False),
        (89, True, False),
        (90, False, False),
        (2000, False, False),
    ],
)
def test_bands_partition_registration_age(
    make_tender: TF,
    make_company: CF,
    empty_ctx: InMemoryContext,
    days: int,
    r1_fires: bool,
    r2_fires: bool,
) -> None:
    tender = make_tender(close_date=CLOSE)
    company = make_company(registration_date=registered(days))

    result1 = r1.evaluate(tender, company, (), empty_ctx)
    result2 = r2.evaluate(tender, company, (), empty_ctx)

    assert result1.fired is r1_fires
    assert result2.fired is r2_fires
    assert not (result1.fired and result2.fired)
    assert result1.evidence["days_registered_before_close"] == days


def test_r2_marks_registration_after_close(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    result = r2.evaluate(
        make_tender(close_date=CLOSE), make_company(registration_date=registered(-5)), (), empty_ctx
    )

    assert result.fired
    assert result.evidence["registered_after_close"] is True
    assert result.score_contribution == 25


def test_r1_contributes_high_weight(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    result = r1.evaluate(
        make_tender(), make_company(registration_date=registered(45)), (), empty_ctx
    )

    assert result.score_contribution == 15


@pytest.mark.parametrize("rule", [r1, r2])
def test_not_evaluated_without_close_date(
    rule: object, make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    result = rule.evaluate(make_tender(close_date=None), make_company(), (), empty_ctx)  # type: ignore[attr-defined]

    assert not result.evaluated
    assert "close date" in str(result.evidence["reason"])


@pytest.mark.parametrize("rule", [r1, r2])
def test_not_evaluated_without_registration_date(
    rule: object, make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    result = rule.evaluate(make_tender(), make_company(registration_date=None), (), empty_ctx)  # type: ignore[attr-defined]

    assert not result.evaluated
    assert "registration date" in str(result.evidence["reason"])
