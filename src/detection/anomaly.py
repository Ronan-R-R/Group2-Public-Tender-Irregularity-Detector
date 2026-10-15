"""Isolation Forest pricing signal (Liu, Ting and Zhou, 2008).

A separate signal from the composite risk score, never added to it: R10 and
R11 already score price outliers, and counting a price twice would inflate
scores (Architecture Decision AD-07).

Design:

- One model over every award with a plausible published value, not one model
  per category. Most eTenders categories have too few priced awards to train
  on (many have under ten), so category context is carried in the features
  instead:

  1. log10 award value minus the median log10 value of its tender category,
  2. log10 award value minus the median log10 value of its buyer,
  3. log10 award value.

  An award is unusual when its price is far from what its category and its
  buyer normally pay, which neither the category alone (R10/R11) nor the
  absolute value captures.
- Retrained on every run with a fixed random_state, so results are
  reproducible and no fitted model is ever stored or unpickled.
- The output is a percentile, "more unusual than X% of priced awards", because
  raw Isolation Forest scores have no meaning outside the model that made them.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from sklearn.ensemble import IsolationForest

from detection.models import Tender

MIN_PLAUSIBLE_VALUE = Decimal(1_000)
MIN_TRAINING_AWARDS = 100
N_ESTIMATORS = 200
RANDOM_STATE = 20261029


@dataclass(frozen=True, slots=True)
class AnomalySignal:
    tender_id: str
    # Share of priced awards that are less unusual than this one, 0-100.
    percentile: float
    category_median: float
    buyer_median: float
    log_vs_category: float
    log_vs_buyer: float


def _priced(awards: Sequence[Tender]) -> list[Tender]:
    return [
        a
        for a in awards
        if a.award_value is not None
        and a.award_value >= MIN_PLAUSIBLE_VALUE
        and a.category is not None
    ]


def score_awards(awards: Sequence[Tender]) -> dict[str, AnomalySignal]:
    """Anomaly signal for every award that has a plausible value and a category.

    Awards without one are absent from the result. Below MIN_TRAINING_AWARDS
    priced awards the model would only describe noise, so nothing is scored.
    """
    priced = _priced(awards)
    if len(priced) < MIN_TRAINING_AWARDS:
        return {}
    ids = [a.tender_id for a in priced]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate tender_id in anomaly input")

    logs = [math.log10(a.award_value) for a in priced if a.award_value is not None]
    by_category: dict[str, list[float]] = defaultdict(list)
    by_buyer: dict[str, list[float]] = defaultdict(list)
    for award, value in zip(priced, logs, strict=True):
        by_category[award.category or ""].append(value)
        by_buyer[award.buyer_id].append(value)
    category_median = {k: statistics.median(v) for k, v in by_category.items()}
    buyer_median = {k: statistics.median(v) for k, v in by_buyer.items()}

    features = np.array(
        [
            [
                value - category_median[award.category or ""],
                value - buyer_median[award.buyer_id],
                value,
            ]
            for award, value in zip(priced, logs, strict=True)
        ]
    )
    model = IsolationForest(
        n_estimators=N_ESTIMATORS, contamination="auto", random_state=RANDOM_STATE
    )
    model.fit(features)
    # score_samples is higher for normal points; negate so higher = more unusual.
    unusualness = -model.score_samples(features)

    order = np.argsort(unusualness, kind="stable")
    ranks = np.empty(len(order), dtype=float)
    ranks[order] = np.arange(len(order))
    denominator = max(len(order) - 1, 1)

    signals: dict[str, AnomalySignal] = {}
    for i, award in enumerate(priced):
        value = logs[i]
        cat = category_median[award.category or ""]
        buy = buyer_median[award.buyer_id]
        signals[award.tender_id] = AnomalySignal(
            tender_id=award.tender_id,
            percentile=round(float(ranks[i]) / denominator * 100, 1),
            category_median=round(10**cat, 2),
            buyer_median=round(10**buy, 2),
            log_vs_category=round(value - cat, 3),
            log_vs_buyer=round(value - buy, 3),
        )
    return signals
