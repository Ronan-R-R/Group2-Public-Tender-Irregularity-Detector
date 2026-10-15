from collections.abc import Callable
from decimal import Decimal

import pytest

from detection import anomaly
from detection.models import Tender

TF = Callable[..., Tender]


def market(make_tender: TF, n: int = 200) -> list[Tender]:
    """A synthetic market: two categories, two buyers, prices around R1m and R10m."""
    awards = []
    for i in range(n):
        goods = i % 2 == 0
        base = 1_000_000 if goods else 10_000_000
        # Deterministic spread of roughly +-40% around each category's base price.
        value = base * (0.6 + 0.8 * ((i * 37) % 100) / 100)
        awards.append(
            make_tender(
                tender_id=f"t-{i}",
                ocid=f"ocds-9t57fa-{i}",
                category="Supplies: Medical" if goods else "Construction",
                buyer_id=f"dept-{i % 4}",
                award_value=Decimal(f"{value:.2f}"),
            )
        )
    return awards


def test_obvious_outlier_ranks_most_unusual(make_tender: TF) -> None:
    awards = market(make_tender)
    outlier = make_tender(
        tender_id="outlier", ocid="ocds-9t57fa-x", category="Supplies: Medical",
        buyer_id="dept-0", award_value=Decimal("950000000"),
    )  # fmt: skip

    signals = anomaly.score_awards([*awards, outlier])

    assert signals["outlier"].percentile == 100.0
    assert signals["outlier"].log_vs_category > 2.5


def test_typical_awards_sit_mid_range(make_tender: TF) -> None:
    signals = anomaly.score_awards(market(make_tender))

    median_pct = sorted(s.percentile for s in signals.values())[len(signals) // 2]
    assert 40 <= median_pct <= 60


def test_relative_features_use_category_and_buyer_medians(make_tender: TF) -> None:
    awards = market(make_tender)

    s = anomaly.score_awards(awards)["t-0"]

    assert s.category_median == pytest.approx(1_000_000, rel=0.15)
    assert s.log_vs_category == pytest.approx(-0.22, abs=0.05)


def test_is_reproducible(make_tender: TF) -> None:
    awards = market(make_tender)

    assert anomaly.score_awards(awards) == anomaly.score_awards(awards)


@pytest.mark.parametrize(
    "overrides",
    [{"award_value": None}, {"award_value": Decimal("999")}, {"category": None}],
)
def test_unscorable_awards_are_left_out(make_tender: TF, overrides: dict[str, object]) -> None:
    odd = make_tender(tender_id="odd", ocid="ocds-9t57fa-odd", **overrides)

    signals = anomaly.score_awards([*market(make_tender), odd])

    assert "odd" not in signals
    assert len(signals) == 200


def test_too_few_priced_awards_scores_nothing(make_tender: TF) -> None:
    assert anomaly.score_awards(market(make_tender, n=anomaly.MIN_TRAINING_AWARDS - 1)) == {}


def test_percentiles_span_zero_to_hundred(make_tender: TF) -> None:
    pct = [s.percentile for s in anomaly.score_awards(market(make_tender)).values()]

    assert min(pct) == 0.0
    assert max(pct) == 100.0


def test_rejects_duplicate_ids(make_tender: TF) -> None:
    awards = market(make_tender)

    with pytest.raises(ValueError, match="duplicate"):
        anomaly.score_awards([*awards, awards[0]])
