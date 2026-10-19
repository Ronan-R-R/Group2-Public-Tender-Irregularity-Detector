"""Helpers shared by the director rules (R4, R5, R6)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from detection.models import Company, Director


def cipc_matched(company: Company) -> bool:
    """Whether the supplier was matched to a CIPC record.

    An unmatched supplier has no director list at all, which must read as
    "not evaluated", while a matched one with no directors on record is a
    genuine, checkable empty list.
    """
    return company.registration_number is not None


def active_on(directors: Iterable[Director], day: date | None) -> list[Director]:
    """Directors in office on ``day``; every director when the day is unknown."""
    if day is None:
        return list(directors)
    return [d for d in directors if d.active_on(day)]
