"""R10 and R11 share one comparison, so they are tested together."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from detection.context import InMemoryContext
from detection.models import Company, Tender
from detection.rules import r10_price_high as r10
from detection.rules import r11_price_low as r11

TF = Callable[..., Tender]
CF = Callable[..., Company]

CLOSE = date(2025, 3, 14)
CATEGORY = "Supplies: Medical"
# Twelve comparables spread around R1m, so log10 median is 6.
BASELINE = [
    "800000", "850000", "900000", "950000", "980000", "1000000",
    "1000000", "1020000", "1050000", "1100000", "1150000", "1200000",
]  # fmt: skip


def history(make_tender: TF, values: list[str], **overrides: object) -> list[Tender]:
    awards = []
    for n, value in enumerate(values, start=1):
        fields: dict[str, object] = {
            "tender_id": f"ocds-9t57fa-{n}/award-1",
            "ocid": f"ocds-9t57fa-{n}",
            "close_date": date(2024, 1 + n % 12, 10),
            "category": CATEGORY,
            "award_value": Decimal(value),
        }
        fields.update(overrides)
        awards.append(make_tender(**fields))
    return awards


def both(tender: Tender, company: Company, ctx: InMemoryContext) -> tuple[bool, bool]:
    return (
        r10.evaluate(tender, company, (), ctx).fired,
        r11.evaluate(tender, company, (), ctx).fired,
    )


@pytest.mark.parametrize(
    ("value", "high", "low"),
    [
        ("1000000", False, False),
        ("1100000", False, False),
        ("2500000", True, False),
        ("142500000", True, False),
        ("400000", False, True),
        ("5000", False, True),
    ],
)
def test_flags_values_far_from_comparables(
    make_tender: TF, make_company: CF, value: str, high: bool, low: bool
) -> None:
    current = make_tender(category=CATEGORY, close_date=CLOSE, award_value=Decimal(value))
    ctx = InMemoryContext([*history(make_tender, BASELINE), current])

    assert both(current, make_company(), ctx) == (high, low)


def test_evidence_supports_the_comparison_chart(make_tender: TF, make_company: CF) -> None:
    current = make_tender(category=CATEGORY, close_date=CLOSE, award_value=Decimal("2500000"))
    ctx = InMemoryContext([*history(make_tender, BASELINE), current])

    evidence = r10.evaluate(current, make_company(), (), ctx).evidence

    assert evidence["comparable_count"] == 12
    assert evidence["comparable_median"] == "1000000.00"
    assert evidence["percent_vs_median"] == 150.0
    comparables = evidence["comparables"]
    assert isinstance(comparables, list)
    assert len(comparables) == 12
    assert all(isinstance(c, dict) and c["tender_id"] != current.tender_id for c in comparables)


def test_absurd_values_in_history_do_not_move_the_baseline(
    make_tender: TF, make_company: CF
) -> None:
    junk = history(make_tender, ["370817849750", "999999999999"])
    junk = [
        make_tender(
            tender_id=f"junk-{i}/a", ocid=f"junk-{i}", category=CATEGORY,
            close_date=date(2024, 6, 1), award_value=a.award_value,
        )
        for i, a in enumerate(junk)
    ]  # fmt: skip
    current = make_tender(category=CATEGORY, close_date=CLOSE, award_value=Decimal("2500000"))
    ctx = InMemoryContext([*history(make_tender, BASELINE), *junk, current])

    assert both(current, make_company(), ctx) == (True, False)


def test_placeholder_values_are_not_comparables(make_tender: TF, make_company: CF) -> None:
    placeholders = [
        make_tender(
            tender_id=f"p-{i}/a", ocid=f"p-{i}", category=CATEGORY,
            close_date=date(2024, 6, 1), award_value=Decimal(v),
        )
        for i, v in enumerate(["0", "1", "999"])
    ]  # fmt: skip
    current = make_tender(category=CATEGORY, close_date=CLOSE, award_value=Decimal("1000000"))
    ctx = InMemoryContext([*history(make_tender, BASELINE), *placeholders, current])

    assert r10.evaluate(current, make_company(), (), ctx).evidence["comparable_count"] == 12


def test_same_process_and_other_categories_are_excluded(make_tender: TF, make_company: CF) -> None:
    sibling = make_tender(
        tender_id="ocds-9t57fa-100001/award-2", category=CATEGORY,
        close_date=CLOSE, award_value=Decimal("1000000"),
    )  # fmt: skip
    other = history(make_tender, ["1000000"] * 5, category="Construction")
    other = [
        make_tender(
            tender_id=f"o-{i}/a", ocid=f"o-{i}", category="Construction",
            close_date=date(2024, 6, 1), award_value=Decimal("1000000"),
        )
        for i in range(len(other))
    ]  # fmt: skip
    current = make_tender(category=CATEGORY, close_date=CLOSE, award_value=Decimal("1000000"))
    ctx = InMemoryContext([*history(make_tender, BASELINE), sibling, *other, current])

    assert r10.evaluate(current, make_company(), (), ctx).evidence["comparable_count"] == 12


@pytest.mark.parametrize(
    ("tender_kw", "reason"),
    [
        ({"award_value": None}, "not published"),
        ({"award_value": Decimal("1")}, "placeholder"),
        ({"close_date": None}, "close date"),
        ({"category": None}, "category not published"),
        ({"category": "Services: General"}, "too broad"),
    ],
)
def test_not_evaluated_when_comparison_impossible(
    make_tender: TF, make_company: CF, tender_kw: dict[str, object], reason: str
) -> None:
    fields: dict[str, object] = {
        "category": CATEGORY,
        "close_date": CLOSE,
        "award_value": Decimal("1000000"),
    }
    fields.update(tender_kw)
    current = make_tender(**fields)
    ctx = InMemoryContext([*history(make_tender, BASELINE), current])

    for rule in (r10, r11):
        result = rule.evaluate(current, make_company(), (), ctx)
        assert not result.evaluated
        assert reason in str(result.evidence["reason"])


def test_not_evaluated_with_too_few_comparables(make_tender: TF, make_company: CF) -> None:
    current = make_tender(category=CATEGORY, close_date=CLOSE, award_value=Decimal("1000000"))
    ctx = InMemoryContext([*history(make_tender, BASELINE[:9]), current])

    result = r10.evaluate(current, make_company(), (), ctx)

    assert not result.evaluated
    assert "only 9 comparable" in str(result.evidence["reason"])


def test_not_evaluated_when_comparables_have_no_spread(make_tender: TF, make_company: CF) -> None:
    current = make_tender(category=CATEGORY, close_date=CLOSE, award_value=Decimal("2000000"))
    ctx = InMemoryContext([*history(make_tender, ["1000000"] * 12), current])

    result = r11.evaluate(current, make_company(), (), ctx)

    assert not result.evaluated
    assert "no price spread" in str(result.evidence["reason"])
