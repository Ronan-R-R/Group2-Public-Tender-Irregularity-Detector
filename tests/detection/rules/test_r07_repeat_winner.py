from collections.abc import Callable
from datetime import date

import pytest

from detection.context import InMemoryContext
from detection.models import Company, Tender
from detection.rules import r07_repeat_winner as r7

TF = Callable[..., Tender]
CF = Callable[..., Company]

CLOSE = date(2025, 3, 14)  # window starts 2023-03-14


def past_award(make_tender: TF, n: int, close: date, **overrides: object) -> Tender:
    fields: dict[str, object] = {
        "tender_id": f"ocds-9t57fa-{n}/award-1",
        "ocid": f"ocds-9t57fa-{n}",
        "close_date": close,
    }
    fields.update(overrides)
    return make_tender(**fields)


def test_fires_on_fifth_award_from_same_buyer(make_tender: TF, make_company: CF) -> None:
    history = [past_award(make_tender, n, date(2024, n, 1)) for n in range(1, 5)]
    current = make_tender(close_date=CLOSE)
    ctx = InMemoryContext([*history, current])

    result = r7.evaluate(current, make_company(), (), ctx)

    assert result.fired
    assert result.evidence["award_count"] == 5
    assert result.score_contribution == 8


def test_four_awards_clear(make_tender: TF, make_company: CF) -> None:
    history = [past_award(make_tender, n, date(2024, n, 1)) for n in range(1, 4)]
    current = make_tender(close_date=CLOSE)

    result = r7.evaluate(current, make_company(), (), InMemoryContext([*history, current]))

    assert result.evaluated
    assert not result.fired
    assert result.evidence["award_count"] == 4


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        ({"close_date": date(2023, 3, 13)}, "before the 24-month window"),
        ({"close_date": date(2025, 3, 15)}, "after this award closed"),
        ({"buyer_id": "dept-999"}, "a different buyer"),
        ({"supplier_id": "sup-999"}, "a different supplier"),
    ],
)
def test_ignores_awards_outside_scope(
    make_tender: TF, make_company: CF, overrides: dict[str, object], why: str
) -> None:
    inside = [past_award(make_tender, n, date(2024, n, 1)) for n in range(1, 4)]
    outside = past_award(make_tender, 99, date(2024, 6, 1), **overrides)
    current = make_tender(close_date=CLOSE)

    result = r7.evaluate(current, make_company(), (), InMemoryContext([*inside, outside, current]))

    assert not result.fired, why
    assert result.evidence["award_count"] == 4


def test_window_start_is_inclusive(make_tender: TF, make_company: CF) -> None:
    history = [past_award(make_tender, n, date(2024, n, 1)) for n in range(1, 4)]
    edge = past_award(make_tender, 50, date(2023, 3, 14))
    current = make_tender(close_date=CLOSE)

    result = r7.evaluate(current, make_company(), (), InMemoryContext([*history, edge, current]))

    assert result.fired


def test_panel_award_lines_count_once(make_tender: TF, make_company: CF) -> None:
    lines = [
        past_award(make_tender, 7, date(2024, 5, 1), tender_id=f"ocds-9t57fa-7/award-{i}")
        for i in range(1, 6)
    ]
    current = make_tender(close_date=CLOSE)

    result = r7.evaluate(current, make_company(), (), InMemoryContext([*lines, current]))

    assert result.evidence["award_count"] == 2
    assert not result.fired


def test_counts_current_award_even_if_context_lacks_it(make_tender: TF, make_company: CF) -> None:
    history = [past_award(make_tender, n, date(2024, n, 1)) for n in range(1, 5)]

    result = r7.evaluate(
        make_tender(close_date=CLOSE), make_company(), (), InMemoryContext(history)
    )

    assert result.evidence["award_count"] == 5


def test_not_evaluated_without_close_date(make_tender: TF, make_company: CF) -> None:
    result = r7.evaluate(make_tender(close_date=None), make_company(), (), InMemoryContext([]))

    assert not result.evaluated
