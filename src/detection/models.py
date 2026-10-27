"""Inputs and outputs of the detection engine.

Field choices follow what the eTenders OCDS feed and CIPC actually provide.
Anything a source may not publish is Optional, so a rule can tell "not
published" apart from "published and empty" and report itself as not
evaluated instead of silently passing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import TypeAlias

JSONValue: TypeAlias = str | int | float | bool | list["JSONValue"] | dict[str, "JSONValue"] | None
Evidence: TypeAlias = Mapping[str, JSONValue]

# eTenders exports .NET's default 0001-01-01 for a missing date. Anything this
# old is a sentinel or a capture error, never a real procurement date.
EARLIEST_PLAUSIBLE_DATE = date(2000, 1, 1)

# eTenders gives unlinked suppliers the id "0": 37% of awards, across unrelated
# companies. Accepting it would merge them into one "repeat winner" (R7).
PLACEHOLDER_IDS = frozenset({"0", "-1"})


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def weight(self) -> int:
        return _SEVERITY_WEIGHTS[self]


_SEVERITY_WEIGHTS: dict[Severity, int] = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 15,
    Severity.MEDIUM: 8,
    Severity.LOW: 3,
}


@dataclass(frozen=True, slots=True)
class Tender:
    """One award as it is scored.

    An OCDS process can award several suppliers (panels), and every red flag
    is about a specific winner, so a multi-award process yields one Tender
    per award. ``tender_id`` is unique per award; ``ocid`` is shared.
    """

    tender_id: str
    ocid: str
    title: str
    buyer_id: str
    buyer_name: str
    supplier_id: str
    category: str | None = None
    procurement_method: str | None = None
    close_date: date | None = None
    award_date: date | None = None
    award_value: Decimal | None = None
    currency: str = "ZAR"
    # None: the source did not publish a bidder list. (): published, empty.
    tenderer_ids: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        for name in ("tender_id", "ocid", "buyer_id", "supplier_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be blank")
        for name in ("buyer_id", "supplier_id"):
            if getattr(self, name).strip() in PLACEHOLDER_IDS:
                raise ValueError(f"{name} is a placeholder id; resolve the party before scoring")
        if self.award_value is not None and (
            not self.award_value.is_finite() or self.award_value < 0
        ):
            raise ValueError(f"award_value must be a non-negative amount, got {self.award_value}")
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise ValueError(f"currency must be an ISO 4217 code, got {self.currency!r}")
        for name in ("close_date", "award_date"):
            value = getattr(self, name)
            if value is not None and value < EARLIEST_PLAUSIBLE_DATE:
                raise ValueError(f"{name} {value} is implausible; map sentinels to None")
        # An award dated before the close date is not rejected: in source data
        # it is either a capture error or a red flag, and both should surface.


@dataclass(frozen=True, slots=True)
class Company:
    company_id: str
    name: str
    registration_number: str | None = None
    registration_date: date | None = None
    status: str | None = None
    industry: str | None = None
    # CIPC annual return filing dates, used for dormancy (R3). None means
    # CIPC data was not available for this company.
    annual_return_dates: tuple[date, ...] | None = None

    def __post_init__(self) -> None:
        if not self.company_id.strip():
            raise ValueError("company_id must not be blank")


@dataclass(frozen=True, slots=True)
class Director:
    """A natural person on the CIPC register.

    ``director_id`` is a stable pseudonymous key and is the only director
    field that may appear in published output. ``full_name`` and
    ``birth_date`` are personal information under POPIA and stay in the
    private store. The birth date exists only to tell apart two people with
    the same name when screening against PEP lists; the ID number it is read
    from is never stored.
    """

    director_id: str
    full_name: str
    appointed: date | None = None
    resigned: date | None = None
    birth_date: date | None = None

    def __post_init__(self) -> None:
        if not self.director_id.strip():
            raise ValueError("director_id must not be blank")
        if self.appointed and self.resigned and self.resigned < self.appointed:
            raise ValueError("resigned is before appointed")

    def active_on(self, day: date) -> bool:
        if self.appointed is not None and day < self.appointed:
            return False
        return self.resigned is None or day < self.resigned


@dataclass(frozen=True, slots=True)
class PepMatch:
    """A director matched to a politically exposed persons list.

    Matching names against the list happens at ingestion; rules only see the
    result. Everything here is private: it never reaches the public export.
    """

    director_id: str
    source: str
    source_ref: str
    match_score: float

    def __post_init__(self) -> None:
        if not 0 <= self.match_score <= 1:
            raise ValueError(f"match_score must be between 0 and 1, got {self.match_score}")


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Outcome of one rule against one award.

    Build these with ``fire``, ``clear`` or ``not_evaluated`` rather than the
    constructor, so ``score_contribution`` always agrees with ``fired``.

    ``evidence`` is safe to publish. ``private_evidence`` holds anything that
    identifies a natural person (director names, PEP match details) and is
    never exported to the public JSON.
    """

    rule_id: str
    title: str
    fired: bool
    evaluated: bool
    severity: Severity
    score_contribution: int
    evidence: Evidence = field(default_factory=dict)
    private_evidence: Evidence = field(default_factory=dict)
    needs_review: bool = False

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("rule_id must not be blank")
        if self.fired and not self.evaluated:
            raise ValueError(f"{self.rule_id}: a rule that was not evaluated cannot fire")
        expected = self.severity.weight if self.fired else 0
        if self.score_contribution != expected:
            raise ValueError(
                f"{self.rule_id}: score_contribution {self.score_contribution} "
                f"does not match severity {self.severity.value} (expected {expected})"
            )
        if self.needs_review and not self.fired:
            raise ValueError(f"{self.rule_id}: needs_review is only meaningful when fired")

    @classmethod
    def fire(
        cls,
        rule_id: str,
        title: str,
        severity: Severity,
        evidence: Evidence,
        *,
        private_evidence: Evidence | None = None,
        needs_review: bool = False,
    ) -> RuleResult:
        return cls(
            rule_id=rule_id,
            title=title,
            fired=True,
            evaluated=True,
            severity=severity,
            score_contribution=severity.weight,
            evidence=evidence,
            private_evidence=private_evidence or {},
            needs_review=needs_review,
        )

    @classmethod
    def clear(
        cls, rule_id: str, title: str, severity: Severity, evidence: Evidence | None = None
    ) -> RuleResult:
        return cls(
            rule_id=rule_id,
            title=title,
            fired=False,
            evaluated=True,
            severity=severity,
            score_contribution=0,
            evidence=evidence or {},
        )

    @classmethod
    def not_evaluated(cls, rule_id: str, title: str, severity: Severity, reason: str) -> RuleResult:
        return cls(
            rule_id=rule_id,
            title=title,
            fired=False,
            evaluated=False,
            severity=severity,
            score_contribution=0,
            evidence={"reason": reason},
        )
