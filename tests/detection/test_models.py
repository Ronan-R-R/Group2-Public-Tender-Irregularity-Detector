from collections.abc import Callable
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from detection.models import Company, Director, RuleResult, Severity, Tender


class TestSeverity:
    @pytest.mark.parametrize(
        ("severity", "weight"),
        [(Severity.CRITICAL, 25), (Severity.HIGH, 15), (Severity.MEDIUM, 8), (Severity.LOW, 3)],
    )
    def test_weight_matches_agreed_scale(self, severity: Severity, weight: int) -> None:
        assert severity.weight == weight


class TestTender:
    def test_valid_tender_constructs(self, make_tender: Callable[..., Tender]) -> None:
        tender = make_tender()

        assert tender.currency == "ZAR"
        assert tender.tenderer_ids is None

    @pytest.mark.parametrize("field_name", ["tender_id", "ocid", "buyer_id", "supplier_id"])
    def test_rejects_blank_identifier(
        self, make_tender: Callable[..., Tender], field_name: str
    ) -> None:
        with pytest.raises(ValueError, match=field_name):
            make_tender(**{field_name: "  "})

    @pytest.mark.parametrize("field_name", ["supplier_id", "buyer_id"])
    @pytest.mark.parametrize("placeholder", ["0", "-1", " 0 "])
    def test_rejects_placeholder_party_ids(
        self, make_tender: Callable[..., Tender], field_name: str, placeholder: str
    ) -> None:
        # eTenders uses supplier id "0" for 37% of awards, across unrelated companies.
        with pytest.raises(ValueError, match="placeholder"):
            make_tender(**{field_name: placeholder})

    @pytest.mark.parametrize("value", [Decimal("-1"), Decimal("NaN"), Decimal("Infinity")])
    def test_rejects_invalid_award_value(
        self, make_tender: Callable[..., Tender], value: Decimal
    ) -> None:
        with pytest.raises(ValueError, match="award_value"):
            make_tender(award_value=value)

    def test_allows_zero_and_missing_award_value(self, make_tender: Callable[..., Tender]) -> None:
        assert make_tender(award_value=Decimal("0")).award_value == 0
        assert make_tender(award_value=None).award_value is None

    @pytest.mark.parametrize("currency", ["zar", "RAND", "", "R1"])
    def test_rejects_non_iso_currency(
        self, make_tender: Callable[..., Tender], currency: str
    ) -> None:
        with pytest.raises(ValueError, match="currency"):
            make_tender(currency=currency)

    @pytest.mark.parametrize("field_name", ["close_date", "award_date"])
    @pytest.mark.parametrize("bad", [date(1, 1, 1), date(1999, 12, 31)])
    def test_rejects_sentinel_and_implausible_dates(
        self, make_tender: Callable[..., Tender], field_name: str, bad: date
    ) -> None:
        # eTenders exports .NET's default 0001-01-01 for "no date".
        with pytest.raises(ValueError, match=field_name):
            make_tender(**{field_name: bad})

    def test_keeps_award_dated_before_close_date(self, make_tender: Callable[..., Tender]) -> None:
        tender = make_tender(close_date=date(2025, 3, 14), award_date=date(2025, 3, 1))

        assert tender.award_date is not None
        assert tender.close_date is not None
        assert tender.award_date < tender.close_date

    def test_distinguishes_unpublished_from_empty_bidder_list(
        self, make_tender: Callable[..., Tender]
    ) -> None:
        assert make_tender(tenderer_ids=None).tenderer_ids is None
        assert make_tender(tenderer_ids=()).tenderer_ids == ()

    def test_is_immutable(self, make_tender: Callable[..., Tender]) -> None:
        tender = make_tender()

        with pytest.raises(AttributeError):
            tender.award_value = Decimal("1")  # type: ignore[misc]


class TestCompany:
    def test_rejects_blank_id(self) -> None:
        with pytest.raises(ValueError, match="company_id"):
            Company(company_id="", name="Fictional Trading (Pty) Ltd")

    def test_unknown_cipc_data_is_none(self) -> None:
        company = Company(company_id="sup-001", name="Fictional Trading (Pty) Ltd")

        assert company.registration_date is None
        assert company.annual_return_dates is None


class TestDirector:
    def test_rejects_blank_id(self) -> None:
        with pytest.raises(ValueError, match="director_id"):
            Director(" ", "A. Person")

    def test_rejects_resignation_before_appointment(self) -> None:
        with pytest.raises(ValueError, match="resigned"):
            Director("dir-1", "A. Person", appointed=date(2024, 5, 1), resigned=date(2024, 4, 1))

    @pytest.mark.parametrize(
        ("day", "active"),
        [
            (date(2024, 4, 30), False),
            (date(2024, 5, 1), True),
            (date(2025, 5, 31), True),
            (date(2025, 6, 1), False),
        ],
    )
    def test_active_on_is_inclusive_of_appointment_exclusive_of_resignation(
        self, day: date, active: bool
    ) -> None:
        director = Director(
            "dir-1", "A. Person", appointed=date(2024, 5, 1), resigned=date(2025, 6, 1)
        )

        assert director.active_on(day) is active

    def test_open_ended_directorship_is_active(self) -> None:
        assert Director("dir-1", "A. Person").active_on(date(2030, 1, 1))


class TestRuleResult:
    def test_fire_sets_contribution_from_severity(self) -> None:
        result = RuleResult.fire("R2", "Company registered under 30 days", Severity.CRITICAL, {})

        assert result.fired
        assert result.evaluated
        assert result.score_contribution == 25

    def test_clear_contributes_nothing(self) -> None:
        result = RuleResult.clear("R8", "Non-competitive award", Severity.MEDIUM)

        assert not result.fired
        assert result.evaluated
        assert result.score_contribution == 0

    def test_not_evaluated_records_reason(self) -> None:
        result = RuleResult.not_evaluated(
            "R5", "Director overlap with losing bidders", Severity.CRITICAL, "no bidder list"
        )

        assert not result.fired
        assert not result.evaluated
        assert result.score_contribution == 0
        assert result.evidence == {"reason": "no bidder list"}

    def test_rejects_blank_rule_id(self) -> None:
        with pytest.raises(ValueError, match="rule_id"):
            RuleResult.clear("", "t", Severity.LOW)

    def test_rejects_fired_but_not_evaluated(self) -> None:
        with pytest.raises(ValueError, match="cannot fire"):
            RuleResult(
                "R1",
                "t",
                fired=True,
                evaluated=False,
                severity=Severity.HIGH,
                score_contribution=15,
            )

    @pytest.mark.parametrize(("fired", "contribution"), [(True, 8), (False, 15), (True, 0)])
    def test_rejects_contribution_that_disagrees_with_severity(
        self, fired: bool, contribution: int
    ) -> None:
        with pytest.raises(ValueError, match="score_contribution"):
            RuleResult(
                "R1",
                "t",
                fired=fired,
                evaluated=True,
                severity=Severity.HIGH,
                score_contribution=contribution,
            )

    def test_rejects_review_flag_on_rule_that_did_not_fire(self) -> None:
        base = RuleResult.clear("R6", "Director matches PEP list", Severity.CRITICAL)

        with pytest.raises(ValueError, match="needs_review"):
            replace(base, needs_review=True)

    def test_private_evidence_kept_apart_from_public_evidence(self) -> None:
        result = RuleResult.fire(
            "R6",
            "Director matches PEP list",
            Severity.CRITICAL,
            {"director_id": "dir-9f2c"},
            private_evidence={"director_name": "A. Person", "pep_source": "opensanctions"},
            needs_review=True,
        )

        assert "director_name" not in result.evidence
        assert result.private_evidence["director_name"] == "A. Person"
        assert result.needs_review
