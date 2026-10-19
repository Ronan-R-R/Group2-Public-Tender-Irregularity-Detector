"""R4, R5 and R6 on fictional companies and directors."""

from collections.abc import Callable
from datetime import date

import pytest

from detection.context import InMemoryContext
from detection.models import Company, Director, PepMatch, RuleResult, Tender
from detection.rules import r04_director_concentration as r4
from detection.rules import r05_bidder_director_overlap as r5
from detection.rules import r06_pep_match as r6

TF = Callable[..., Tender]
CF = Callable[..., Company]

CLOSE = date(2025, 3, 14)  # R4 window starts 2024-03-14
SHARED = Director("dir-shared", "A. Fictional Person")
OTHER = Director("dir-other", "B. Fictional Person")
TWO_LINKED_WINS = [
    ("sup-002", date(2024, 6, 1), "dept-001"),
    ("sup-003", date(2025, 1, 1), "dept-001"),
]


def win(make_tender: TF, n: int, supplier: str, close: date, buyer: str = "dept-001") -> Tender:
    return make_tender(
        tender_id=f"ocds-9t57fa-{n}/award-1", ocid=f"ocds-9t57fa-{n}",
        supplier_id=supplier, buyer_id=buyer, close_date=close,
    )  # fmt: skip


# ---------------------------------------------------------------- R4


def r4_case(
    make_tender: TF, make_company: CF, *, other_wins: list[tuple[str, date, str]],
    links: dict[str, list[Director]] | None = None,
) -> RuleResult:  # fmt: skip
    current = make_tender(close_date=CLOSE)
    history = [win(make_tender, i, s, d, b) for i, (s, d, b) in enumerate(other_wins, start=10)]
    company_links = links or {"sup-001": [SHARED], "sup-002": [SHARED], "sup-003": [SHARED]}
    ctx = InMemoryContext([*history, current], company_directors=company_links)
    return r4.evaluate(current, make_company(), company_links["sup-001"], ctx)


def test_r4_fires_on_three_linked_winners_at_one_buyer(make_tender: TF, make_company: CF) -> None:
    result = r4_case(
        make_tender, make_company,
        other_wins=TWO_LINKED_WINS,
    )  # fmt: skip

    assert result.fired
    assert result.score_contribution == 15
    assert result.evidence["company_count"] == 3
    assert result.evidence["director_id"] == "dir-shared"
    assert "director_name" not in result.evidence
    assert result.private_evidence["director_name"] == "A. Fictional Person"


@pytest.mark.parametrize(
    "third",
    [
        ("sup-003", date(2024, 3, 13), "dept-001"),  # before the 12-month window
        ("sup-003", date(2025, 3, 15), "dept-001"),  # after this award closed
        ("sup-003", date(2025, 1, 1), "dept-999"),  # a different buyer
        ("sup-004", date(2025, 1, 1), "dept-001"),  # a company the director is not on
    ],
)
def test_r4_ignores_wins_outside_scope(
    make_tender: TF, make_company: CF, third: tuple[str, date, str]
) -> None:
    result = r4_case(
        make_tender, make_company,
        other_wins=[("sup-002", date(2024, 6, 1), "dept-001"), third],
    )  # fmt: skip

    assert result.evaluated
    assert not result.fired
    assert result.evidence["company_count"] == 2


def test_r4_requires_the_director_in_office_when_the_other_award_closed(
    make_tender: TF, make_company: CF
) -> None:
    resigned_early = Director("dir-shared", "A. Fictional Person", resigned=date(2024, 12, 1))
    links = {"sup-001": [SHARED], "sup-002": [SHARED], "sup-003": [resigned_early]}

    result = r4_case(
        make_tender, make_company, links=links,
        other_wins=TWO_LINKED_WINS,
    )  # fmt: skip

    assert not result.fired
    assert result.evidence["company_count"] == 2


def test_r4_clears_when_the_supplier_has_no_directors_on_record(
    make_tender: TF, make_company: CF
) -> None:
    ctx = InMemoryContext([make_tender(close_date=CLOSE)])

    result = r4.evaluate(make_tender(close_date=CLOSE), make_company(), (), ctx)

    assert result.evaluated
    assert not result.fired


@pytest.mark.parametrize(
    ("tender_kw", "company_kw", "reason"),
    [
        ({"close_date": None}, {}, "close date"),
        ({}, {"registration_number": None}, "not matched to CIPC"),
    ],
)
def test_r4_not_evaluated_without_data(
    make_tender: TF, make_company: CF, tender_kw: dict[str, object],
    company_kw: dict[str, object], reason: str,
) -> None:  # fmt: skip
    result = r4.evaluate(
        make_tender(**tender_kw), make_company(**company_kw), (SHARED,), InMemoryContext([])
    )

    assert not result.evaluated
    assert reason in str(result.evidence["reason"])


# ---------------------------------------------------------------- R5


def bidders_ctx(
    directors_by_company: dict[str, list[Director]], unmatched: tuple[str, ...] = ()
) -> InMemoryContext:
    companies = [
        Company(company_id=c, name=f"Fictional {c}",
                registration_number=None if c in unmatched else f"2020/{i:06d}/07")
        for i, c in enumerate(directors_by_company)
    ]  # fmt: skip
    return InMemoryContext([], company_directors=directors_by_company, companies=companies)


def test_r5_fires_when_winner_and_loser_share_a_director(make_tender: TF, make_company: CF) -> None:
    ctx = bidders_ctx({"sup-001": [SHARED], "sup-002": [SHARED, OTHER], "sup-003": [OTHER]})
    tender = make_tender(close_date=CLOSE, tenderer_ids=("sup-001", "sup-002", "sup-003"))

    result = r5.evaluate(tender, make_company(), [SHARED], ctx)

    assert result.fired
    assert result.score_contribution == 25
    assert result.evidence["overlapping_bidders"] == ["sup-002"]
    assert result.evidence["shared_director_ids"] == ["dir-shared"]
    assert result.evidence["bidders_checked"] == 2
    assert result.private_evidence["director_names"] == ["A. Fictional Person"]


def test_r5_clears_when_no_director_is_shared(make_tender: TF, make_company: CF) -> None:
    ctx = bidders_ctx({"sup-001": [SHARED], "sup-002": [OTHER]})
    tender = make_tender(close_date=CLOSE, tenderer_ids=("sup-001", "sup-002"))

    result = r5.evaluate(tender, make_company(), [SHARED], ctx)

    assert result.evaluated
    assert not result.fired


def test_r5_ignores_a_shared_director_who_had_resigned_before_close(
    make_tender: TF, make_company: CF
) -> None:
    gone = Director("dir-shared", "A. Fictional Person", resigned=date(2025, 1, 1))
    ctx = bidders_ctx({"sup-001": [SHARED], "sup-002": [gone]})
    tender = make_tender(close_date=CLOSE, tenderer_ids=("sup-001", "sup-002"))

    assert not r5.evaluate(tender, make_company(), [SHARED], ctx).fired


def test_r5_with_only_the_winner_bidding_clears(make_tender: TF, make_company: CF) -> None:
    tender = make_tender(close_date=CLOSE, tenderer_ids=("sup-001",))

    result = r5.evaluate(tender, make_company(), [SHARED], bidders_ctx({"sup-001": [SHARED]}))

    assert result.evaluated
    assert result.evidence["losing_bidders"] == 0


@pytest.mark.parametrize(
    ("tenderers", "company_kw", "unmatched", "reason"),
    [
        (None, {}, (), "bidder list not published"),
        (("sup-001", "sup-002"), {"registration_number": None}, (), "not matched to CIPC"),
        (("sup-001", "sup-002"), {}, ("sup-002",), "no losing bidder matched"),
        (("sup-001", "sup-009"), {}, (), "no losing bidder matched"),
    ],
)
def test_r5_not_evaluated_without_data(
    make_tender: TF, make_company: CF, tenderers: tuple[str, ...] | None,
    company_kw: dict[str, object], unmatched: tuple[str, ...], reason: str,
) -> None:  # fmt: skip
    ctx = bidders_ctx({"sup-001": [SHARED], "sup-002": [SHARED]}, unmatched=unmatched)
    tender = make_tender(close_date=CLOSE, tenderer_ids=tenderers)

    result = r5.evaluate(tender, make_company(**company_kw), [SHARED], ctx)

    assert not result.evaluated
    assert reason in str(result.evidence["reason"])


# ---------------------------------------------------------------- R6


def pep(director_id: str, score: float) -> PepMatch:
    return PepMatch(director_id, "opensanctions", f"ref-{director_id}", score)


def test_r6_fires_for_review_and_keeps_details_private(make_tender: TF, make_company: CF) -> None:
    ctx = InMemoryContext([], pep_matches=[pep("dir-shared", 0.95)])

    result = r6.evaluate(make_tender(close_date=CLOSE), make_company(), [SHARED, OTHER], ctx)

    assert result.fired
    assert result.needs_review
    assert result.score_contribution == 25
    assert result.evidence == {"directors_checked": 2, "matched_directors": 1}
    matches = result.private_evidence["matches"]
    assert isinstance(matches, list) and len(matches) == 1


@pytest.mark.parametrize("score", [0.0, 0.89])
def test_r6_ignores_weak_matches(make_tender: TF, make_company: CF, score: float) -> None:
    ctx = InMemoryContext([], pep_matches=[pep("dir-shared", score)])

    result = r6.evaluate(make_tender(close_date=CLOSE), make_company(), [SHARED], ctx)

    assert result.evaluated
    assert not result.fired


def test_r6_ignores_a_director_no_longer_in_office(make_tender: TF, make_company: CF) -> None:
    gone = Director("dir-shared", "A. Fictional Person", resigned=date(2025, 1, 1))
    ctx = InMemoryContext([], pep_matches=[pep("dir-shared", 0.99)])

    assert not r6.evaluate(make_tender(close_date=CLOSE), make_company(), [gone], ctx).fired


@pytest.mark.parametrize(
    ("company_kw", "screened", "reason"),
    [
        ({"registration_number": None}, True, "not matched to CIPC"),
        ({}, False, "screening not run"),
    ],
)
def test_r6_not_evaluated_without_data(
    make_tender: TF, make_company: CF, company_kw: dict[str, object], screened: bool, reason: str
) -> None:
    ctx = InMemoryContext([], pep_matches=[] if screened else None)

    result = r6.evaluate(make_tender(close_date=CLOSE), make_company(**company_kw), [SHARED], ctx)

    assert not result.evaluated
    assert reason in str(result.evidence["reason"])


def test_pep_match_score_must_be_a_probability() -> None:
    with pytest.raises(ValueError, match="match_score"):
        PepMatch("dir-1", "opensanctions", "ref", 1.5)


def test_r5_compares_all_directors_when_the_close_date_is_unknown(
    make_tender: TF, make_company: CF
) -> None:
    resigned = Director("dir-shared", "A. Fictional Person", resigned=date(2020, 1, 1))
    ctx = bidders_ctx({"sup-001": [SHARED], "sup-002": [resigned]})
    tender = make_tender(close_date=None, tenderer_ids=("sup-001", "sup-002"))

    assert r5.evaluate(tender, make_company(), [SHARED], ctx).fired
