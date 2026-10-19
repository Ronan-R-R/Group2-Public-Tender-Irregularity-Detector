"""Read-only history lookups for rules that need more than one award.

Rules depend on the ``DetectionContext`` protocol, not on a database, so they
stay testable without Postgres. The scoring job loads the award history once
(about 10k awards fit easily in memory) and serves every rule from
``InMemoryContext``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Protocol

from detection.models import Company, Director, PepMatch, Tender


class DetectionContext(Protocol):
    def awards_by_buyer(self, buyer_id: str, start: date, end: date) -> Sequence[Tender]:
        """Awards by one procuring entity whose close date is in [start, end]."""
        ...

    def awards_in_category(self, category: str, start: date, end: date) -> Sequence[Tender]:
        """Awards in one tender category whose close date is in [start, end]."""
        ...

    def directors_of(self, company_id: str) -> Sequence[Director]: ...

    def companies_of(self, director_id: str) -> Sequence[str]: ...

    def company(self, company_id: str) -> Company | None:
        """The company record, or None when it is not known at all."""
        ...

    def pep_matches(self, director_id: str) -> Sequence[PepMatch] | None:
        """PEP matches for a director, or None when PEP screening was not run."""
        ...


class InMemoryContext:
    def __init__(
        self,
        awards: Iterable[Tender],
        company_directors: Mapping[str, Iterable[Director]] | None = None,
        companies: Iterable[Company] | None = None,
        pep_matches: Iterable[PepMatch] | None = None,
    ) -> None:
        self._awards = tuple(awards)
        self._by_buyer: dict[str, list[Tender]] = defaultdict(list)
        self._by_category: dict[str, list[Tender]] = defaultdict(list)
        for award in self._awards:
            self._by_buyer[award.buyer_id].append(award)
            if award.category is not None:
                self._by_category[award.category].append(award)

        self._directors: dict[str, tuple[Director, ...]] = {}
        self._companies: dict[str, list[str]] = defaultdict(list)
        for company_id, directors in (company_directors or {}).items():
            self._directors[company_id] = tuple(directors)
            for director in self._directors[company_id]:
                self._companies[director.director_id].append(company_id)

        self._company_records = {c.company_id: c for c in companies or ()}
        # None means screening was not run, which rules must not read as "no match".
        self._peps: dict[str, list[PepMatch]] | None = None
        if pep_matches is not None:
            self._peps = defaultdict(list)
            for match in pep_matches:
                self._peps[match.director_id].append(match)

    def awards_by_buyer(self, buyer_id: str, start: date, end: date) -> Sequence[Tender]:
        return _within(self._by_buyer.get(buyer_id, ()), start, end)

    def awards_in_category(self, category: str, start: date, end: date) -> Sequence[Tender]:
        return _within(self._by_category.get(category, ()), start, end)

    def directors_of(self, company_id: str) -> Sequence[Director]:
        return self._directors.get(company_id, ())

    def companies_of(self, director_id: str) -> Sequence[str]:
        return tuple(self._companies.get(director_id, ()))

    def company(self, company_id: str) -> Company | None:
        return self._company_records.get(company_id)

    def pep_matches(self, director_id: str) -> Sequence[PepMatch] | None:
        if self._peps is None:
            return None
        return tuple(self._peps.get(director_id, ()))


def _within(awards: Iterable[Tender], start: date, end: date) -> tuple[Tender, ...]:
    if end < start:
        raise ValueError(f"window end {end} is before start {start}")
    # Awards without a close date cannot be placed in a time window, so they
    # never count towards one.
    return tuple(a for a in awards if a.close_date is not None and start <= a.close_date <= end)
