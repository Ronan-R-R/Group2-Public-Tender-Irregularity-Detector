from collections.abc import Callable
from datetime import date

import pytest

from detection.context import InMemoryContext
from detection.models import Director, Tender

TF = Callable[..., Tender]


def test_awards_by_buyer_filters_buyer_and_inclusive_window(make_tender: TF) -> None:
    inside_start = make_tender(tender_id="a1", close_date=date(2024, 1, 1))
    inside_end = make_tender(tender_id="a2", close_date=date(2024, 12, 31))
    outside = make_tender(tender_id="a3", close_date=date(2025, 1, 1))
    other_buyer = make_tender(tender_id="a4", buyer_id="dept-999", close_date=date(2024, 6, 1))
    undated = make_tender(tender_id="a5", close_date=None)
    ctx = InMemoryContext([inside_start, inside_end, outside, other_buyer, undated])

    found = ctx.awards_by_buyer("dept-001", date(2024, 1, 1), date(2024, 12, 31))

    assert [a.tender_id for a in found] == ["a1", "a2"]


def test_awards_in_category_skips_uncategorised(make_tender: TF) -> None:
    medical = make_tender(tender_id="a1", category="Supplies: Medical")
    blank = make_tender(tender_id="a2", category=None)
    ctx = InMemoryContext([medical, blank])

    found = ctx.awards_in_category("Supplies: Medical", date(2020, 1, 1), date(2030, 1, 1))

    assert [a.tender_id for a in found] == ["a1"]


def test_unknown_keys_return_empty(make_tender: TF) -> None:
    ctx = InMemoryContext([make_tender()])

    assert ctx.awards_by_buyer("nobody", date(2020, 1, 1), date(2030, 1, 1)) == ()
    assert ctx.awards_in_category("nothing", date(2020, 1, 1), date(2030, 1, 1)) == ()
    assert ctx.directors_of("no-company") == ()
    assert ctx.companies_of("no-director") == ()


def test_rejects_inverted_window(make_tender: TF) -> None:
    ctx = InMemoryContext([make_tender()])

    with pytest.raises(ValueError, match="before start"):
        ctx.awards_by_buyer("dept-001", date(2025, 1, 1), date(2024, 1, 1))


def test_director_links_both_directions() -> None:
    shared = Director("dir-1", "A. Person")
    ctx = InMemoryContext(
        awards=(),
        company_directors={
            "sup-001": [shared, Director("dir-2", "B. Person")],
            "sup-002": [shared],
        },
    )

    assert [d.director_id for d in ctx.directors_of("sup-001")] == ["dir-1", "dir-2"]
    assert ctx.companies_of("dir-1") == ("sup-001", "sup-002")
    assert ctx.companies_of("dir-2") == ("sup-001",)


def test_company_and_pep_lookups() -> None:
    from detection.models import Company, PepMatch

    known = Company(company_id="sup-001", name="Fictional Supplies")
    match = PepMatch("dir-1", "opensanctions", "ref-1", 0.95)
    screened = InMemoryContext([], companies=[known], pep_matches=[match])
    unscreened = InMemoryContext([])

    assert screened.company("sup-001") == known
    assert screened.company("sup-999") is None
    assert screened.pep_matches("dir-1") == (match,)
    assert screened.pep_matches("dir-2") == ()
    assert unscreened.pep_matches("dir-1") is None
