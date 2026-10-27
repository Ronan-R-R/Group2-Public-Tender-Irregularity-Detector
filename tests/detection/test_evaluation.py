from collections.abc import Callable
from typing import Any

import pytest

from detection.anomaly import AnomalySignal
from detection.evaluation import evaluate
from detection.export import ScoredAward
from detection.models import Company, RuleResult, Severity, Tender
from detection.scorer import score

TF = Callable[..., Tender]
CF = Callable[..., Company]


def fire(rule_id: str, severity: Severity = Severity.MEDIUM) -> RuleResult:
    return RuleResult.fire(rule_id, f"{rule_id} title", severity, {})


def clear(rule_id: str, severity: Severity = Severity.MEDIUM) -> RuleResult:
    return RuleResult.clear(rule_id, f"{rule_id} title", severity, {})


def skipped(rule_id: str, reason: str, severity: Severity = Severity.MEDIUM) -> RuleResult:
    return RuleResult.not_evaluated(rule_id, f"{rule_id} title", severity, reason)


def award(
    make_tender: TF,
    make_company: CF,
    n: int,
    results: list[RuleResult],
    anomaly_pct: float | None = None,
    log_vs_category: float = 0.0,
) -> ScoredAward:
    tender = make_tender(tender_id=f"ocds-9t57fa-{n}/1", ocid=f"ocds-9t57fa-{n}")
    signal: Any = None
    if anomaly_pct is not None:
        signal = AnomalySignal(tender.tender_id, anomaly_pct, 1.0, 1.0, log_vs_category, 0.0)
    return ScoredAward(tender, make_company(), score(results), signal)


def test_rule_counts_fire_rates_and_reasons(make_tender: TF, make_company: CF) -> None:
    scored = [
        award(
            make_tender, make_company, 1, [fire("R7"), skipped("R10", "award value not published")]
        ),
        award(
            make_tender, make_company, 2, [clear("R7"), skipped("R10", "award value not published")]
        ),
        award(make_tender, make_company, 3, [clear("R7"), skipped("R10", "too few comparables")]),
        award(make_tender, make_company, 4, [clear("R7"), clear("R10", Severity.MEDIUM)]),
    ]

    result = evaluate(scored)

    r7, r10 = result.rules
    assert (r7.rule_id, r7.evaluated, r7.fired, r7.not_evaluated) == ("R7", 4, 1, 0)
    assert r7.fire_rate == pytest.approx(0.25)
    assert (r10.evaluated, r10.fired, r10.not_evaluated) == (1, 0, 3)
    assert r10.reasons == (("award value not published", 2), ("too few comparables", 1))


def test_a_rule_never_evaluated_has_no_fire_rate(make_tender: TF, make_company: CF) -> None:
    result = evaluate([award(make_tender, make_company, 1, [skipped("R1", "CIPC unknown")])])

    assert result.rules[0].fire_rate is None


def test_rules_are_in_natural_order(make_tender: TF, make_company: CF) -> None:
    results = [clear("R12"), clear("R2"), clear("R10")]

    result = evaluate([award(make_tender, make_company, 1, results)])

    assert [r.rule_id for r in result.rules] == ["R2", "R10", "R12"]


def test_score_bands_levels_and_coverage(make_tender: TF, make_company: CF) -> None:
    critical = [fire(f"R{i}", Severity.CRITICAL) for i in (1, 2, 3)]  # 75: alert
    scored = [
        award(make_tender, make_company, 1, [clear("R7"), skipped("R10", "x")]),
        award(make_tender, make_company, 2, [fire("R7")]),
        award(make_tender, make_company, 3, critical),
    ]

    result = evaluate(scored)

    assert result.score_bands == {"0": 1, "1-24": 1, "25-49": 0, "50-74": 0, "75-100": 1}
    assert result.levels == {"none": 2, "flag": 0, "alert": 1}
    assert result.max_score == 75
    assert result.awards_with_a_flag == 2
    assert result.coverage_counts == {0.5: 1, 1.0: 2}
    assert result.mean_coverage == pytest.approx(2.5 / 3)


def test_rules_firing_together_are_counted_once_per_award(
    make_tender: TF, make_company: CF
) -> None:
    scored = [
        award(
            make_tender, make_company, 1, [fire("R12", Severity.LOW), fire("R10", Severity.HIGH)]
        ),
        award(
            make_tender, make_company, 2, [fire("R10", Severity.HIGH), fire("R12", Severity.LOW)]
        ),
        award(make_tender, make_company, 3, [fire("R7"), clear("R8")]),
    ]

    assert evaluate(scored).rule_pairs == {("R10", "R12"): 2}


def test_anomaly_top_share_against_price_rules_and_capture_errors(
    make_tender: TF, make_company: CF
) -> None:
    # 150 priced awards: the top 1% rounds up to 2.
    scored = [
        award(make_tender, make_company, i, [clear("R10", Severity.HIGH)], anomaly_pct=i / 2)
        for i in range(148)
    ]
    scored.append(
        award(
            make_tender, make_company, 900, [fire("R10", Severity.HIGH)], 99.9, log_vs_category=2.5
        )
    )
    scored.append(award(make_tender, make_company, 901, [clear("R10", Severity.HIGH)], 99.8, 0.4))
    scored.append(award(make_tender, make_company, 902, [clear("R10", Severity.HIGH)]))

    a = evaluate(scored).anomaly

    assert a is not None
    assert (a.scored, a.top_n, a.top_with_price_flag, a.top_capture_errors) == (150, 2, 1, 1)


def test_no_anomaly_section_without_signals(make_tender: TF, make_company: CF) -> None:
    assert evaluate([award(make_tender, make_company, 1, [clear("R7")])]).anomaly is None


def test_nothing_to_evaluate_is_an_error() -> None:
    with pytest.raises(ValueError, match="nothing to evaluate"):
        evaluate([])
