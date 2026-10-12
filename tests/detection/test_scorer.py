import pytest

from detection.models import RuleResult, Severity
from detection.scorer import RiskLevel, risk_level, score


def fired(rule_id: str, severity: Severity) -> RuleResult:
    return RuleResult.fire(rule_id, f"{rule_id} title", severity, {})


def clear(rule_id: str, severity: Severity = Severity.MEDIUM) -> RuleResult:
    return RuleResult.clear(rule_id, f"{rule_id} title", severity)


def unevaluated(rule_id: str, severity: Severity = Severity.CRITICAL) -> RuleResult:
    return RuleResult.not_evaluated(rule_id, f"{rule_id} title", severity, "no data")


C, H, M, L = Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW


class TestScore:
    def test_no_results_scores_zero_with_zero_coverage(self) -> None:
        result = score([])

        assert result.score == 0
        assert result.level is RiskLevel.NONE
        assert result.coverage == 0.0
        assert result.breakdown == ()

    def test_sums_fired_rules_by_severity(self) -> None:
        result = score([fired("R2", C), fired("R10", H), fired("R8", M), fired("R12", L)])

        assert result.score == 25 + 15 + 8 + 3

    def test_ignores_clear_and_unevaluated_rules(self) -> None:
        result = score([fired("R7", M), clear("R8"), unevaluated("R5")])

        assert result.score == 8

    def test_caps_at_100_and_keeps_uncapped_total(self) -> None:
        results = [fired(f"R{i}", C) for i in range(1, 6)]

        result = score(results)

        assert result.score == 100
        assert result.uncapped_score == 125

    @pytest.mark.parametrize(
        ("results", "expected_score", "expected_level"),
        [
            ([fired("R2", C), fired("R7", M), fired("R8", M), fired("R9", M)], 49, RiskLevel.NONE),
            ([fired("R2", C), fired("R5", C)], 50, RiskLevel.FLAG),
            (
                [fired("R2", C), fired("R5", C), fired("R7", M), fired("R8", M), fired("R9", M)],
                74,
                RiskLevel.FLAG,
            ),
            ([fired("R2", C), fired("R5", C), fired("R6", C)], 75, RiskLevel.ALERT),
        ],
    )
    def test_threshold_edges(
        self, results: list[RuleResult], expected_score: int, expected_level: RiskLevel
    ) -> None:
        result = score(results)

        assert result.score == expected_score
        assert result.level is expected_level

    def test_rejects_duplicate_rule_ids(self) -> None:
        with pytest.raises(ValueError, match="R1"):
            score([fired("R1", H), clear("R1")])

    def test_breakdown_orders_fired_by_contribution_then_natural_rule_order(self) -> None:
        results = [
            clear("R1"),
            fired("R12", L),
            fired("R10", H),
            fired("R2", C),
            fired("R7", M),
            fired("R8", M),
            unevaluated("R5"),
        ]

        order = [r.rule_id for r in score(results).breakdown]

        assert order == ["R2", "R10", "R7", "R8", "R12", "R1", "R5"]

    def test_breakdown_ties_use_numeric_rule_order(self) -> None:
        results = [clear("R10"), clear("R2"), clear("R1"), clear("R12")]

        order = [r.rule_id for r in score(results).breakdown]

        assert order == ["R1", "R2", "R10", "R12"]

    def test_fired_and_not_evaluated_views(self) -> None:
        result = score([fired("R7", M), clear("R8"), unevaluated("R5"), unevaluated("R6")])

        assert [r.rule_id for r in result.fired] == ["R7"]
        assert {r.rule_id for r in result.not_evaluated} == {"R5", "R6"}

    def test_coverage_is_share_of_evaluated_rules(self) -> None:
        result = score([clear("R1"), clear("R2"), clear("R3"), unevaluated("R5")])

        assert result.score == 0
        assert result.coverage == pytest.approx(0.75)

    def test_needs_review_propagates_from_fired_rule(self) -> None:
        pep = RuleResult.fire("R6", "PEP match", C, {}, needs_review=True)

        assert score([pep, clear("R8")]).needs_review
        assert not score([fired("R2", C)]).needs_review

    def test_accepts_any_iterable(self) -> None:
        result = score(r for r in [fired("R7", M)])

        assert result.score == 8


@pytest.mark.parametrize(
    ("value", "level"),
    [
        (0, RiskLevel.NONE),
        (49, RiskLevel.NONE),
        (50, RiskLevel.FLAG),
        (74, RiskLevel.FLAG),
        (75, RiskLevel.ALERT),
        (100, RiskLevel.ALERT),
    ],
)
def test_risk_level_boundaries(value: int, level: RiskLevel) -> None:
    assert risk_level(value) is level
