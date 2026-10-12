from collections.abc import Callable

import pytest

from detection.context import InMemoryContext
from detection.models import Company, Tender
from detection.rules import r09_sector_mismatch as r9

TF = Callable[..., Tender]
CF = Callable[..., Company]


@pytest.mark.parametrize(
    ("category", "industry", "fires"),
    [
        ("Supplies: Medical", "Human health activities", False),
        ("Supplies: Medical", "Wholesale and retail trade", False),
        ("Supplies: Medical", "Construction of buildings", True),
        ("Civil engineering", "Construction", False),
        ("Civil engineering", "Food and beverage service activities", True),
        (
            "Services: Functional (Including Cleaning and Security Services)",
            "Security and investigation activities",
            False,
        ),
        ("Computer programming, consultancy and related activities", "Telecommunications", False),
        ("Services: Professional", "Accommodation", True),
        ("  SUPPLIES:  medical ", "human health ACTIVITIES", False),
    ],
)
def test_matches_on_shared_sector_group(
    make_tender: TF,
    make_company: CF,
    empty_ctx: InMemoryContext,
    category: str,
    industry: str,
    fires: bool,
) -> None:
    result = r9.evaluate(
        make_tender(category=category), make_company(industry=industry), (), empty_ctx
    )

    assert result.evaluated
    assert result.fired is fires
    assert result.evidence["tender_category"] == category


def test_wholesaler_does_not_match_a_works_tender(
    make_tender: TF, make_company: CF, empty_ctx: InMemoryContext
) -> None:
    result = r9.evaluate(
        make_tender(category="Construction"),
        make_company(industry="Wholesale and retail trade"),
        (),
        empty_ctx,
    )

    assert result.fired


@pytest.mark.parametrize(
    ("category", "industry", "reason"),
    [
        (None, "Construction", "category not published"),
        ("Construction", None, "industry unknown"),
        ("Services: General", "Construction", "too broad"),
        ("goods", "Construction", "too broad"),
        ("Underwater basket weaving", "Construction", "not mapped"),
        ("Construction", "Other service activities", "too broad"),
        ("Construction", "Unknown sector", "not mapped"),
    ],
)
def test_not_evaluated_for_missing_generic_or_unmapped_labels(
    make_tender: TF,
    make_company: CF,
    empty_ctx: InMemoryContext,
    category: str | None,
    industry: str | None,
    reason: str,
) -> None:
    result = r9.evaluate(
        make_tender(category=category), make_company(industry=industry), (), empty_ctx
    )

    assert not result.evaluated
    assert reason in str(result.evidence["reason"])
