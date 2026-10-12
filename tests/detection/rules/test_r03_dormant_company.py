from collections.abc import Callable
from datetime import date

import pytest

from detection.context import InMemoryContext
from detection.models import Company, Tender
from detection.rules import r03_dormant_company as r3

CLOSE = date(2025, 3, 14)  # 24 months earlier is 2023-03-14

TF = Callable[..., Tender]
CF = Callable[..., Company]


@pytest.mark.parametrize(
    ("last_filing", "fires"),
    [
        (date(2023, 3, 13), True),
        (date(2023, 3, 14), False),
        (date(2024, 6, 28), False),
        (date(2019, 1, 1), True),
    ],
)
def test_dormancy_measured_from_last_filing_before_close(
    make_tender: TF,
    make_company: CF,
    empty_ctx: InMemoryContext,
    last_filing: date,
    fires: bool,
) -> None:
    company = make_company(annual_return_dates=(date(2018, 6, 1), last_filing))

    result = r3.evaluate(make_tender(close_date=CLOSE), company, (), empty_ctx)

    assert result.evaluated
    assert result.fired is fires
    assert result.evidence["last_annual_return"] == last_filing.isoformat()


def test_filings_after_close_do_not_count(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    # Filing after winning is exactly the "resurrected" pattern; it must not
    # hide the dormant period before the award.
    company = make_company(annual_return_dates=(date(2020, 5, 1), date(2025, 4, 1)))

    result = r3.evaluate(make_tender(close_date=CLOSE), company, (), empty_ctx)

    assert result.fired
    assert result.evidence["last_annual_return"] == "2020-05-01"


def test_never_filed_old_company_fires(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    company = make_company(annual_return_dates=(), registration_date=date(2020, 1, 10))

    result = r3.evaluate(make_tender(close_date=CLOSE), company, (), empty_ctx)

    assert result.fired
    assert result.evidence["last_annual_return"] is None


def test_never_filed_young_company_clears(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    company = make_company(annual_return_dates=(), registration_date=date(2024, 2, 1))

    result = r3.evaluate(make_tender(close_date=CLOSE), company, (), empty_ctx)

    assert result.evaluated
    assert not result.fired


@pytest.mark.parametrize(
    ("tender_kw", "company_kw", "reason"),
    [
        ({"close_date": None}, {}, "close date"),
        ({}, {"annual_return_dates": None}, "filing history"),
        ({}, {"annual_return_dates": (), "registration_date": None}, "registration date"),
    ],
)
def test_not_evaluated_when_data_missing(
    make_tender: TF,
    make_company: CF,
    empty_ctx: InMemoryContext,
    tender_kw: dict[str, object],
    company_kw: dict[str, object],
    reason: str,
) -> None:
    result = r3.evaluate(make_tender(**tender_kw), make_company(**company_kw), (), empty_ctx)

    assert not result.evaluated
    assert reason in str(result.evidence["reason"])
