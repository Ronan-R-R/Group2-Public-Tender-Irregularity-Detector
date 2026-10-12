"""Price comparison shared by R10 and R11.

The specification says "more than 2 standard deviations from the mean of
comparable awards". On eTenders data a literal mean and SD are meaningless:
values span R1 to R370 billion, include placeholders (R0, R1) and capture
errors, and are heavily right-skewed. So the comparison is made on log10
values with a robust z-score, (x - median) / (1.4826 * MAD). For normally
distributed log prices that equals the ordinary z-score, so the threshold
of 2 keeps the specification's meaning while a handful of absurd values in
the history cannot move the baseline.

Comparables are awards in the same tender category that closed in the 24
months up to this award's close date, excluding this contracting process.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal

from detection.context import DetectionContext
from detection.models import JSONValue, Tender
from detection.rules._dates import months_before
from detection.sectors import is_generic

WINDOW_MONTHS = 24
MIN_COMPARABLES = 10
# Below this an amount is a placeholder or capture error, not a price.
MIN_PLAUSIBLE_VALUE = Decimal(1_000)
MAD_TO_SD = 1.4826
CHART_COMPARABLES = 20


@dataclass(frozen=True, slots=True)
class PriceComparison:
    robust_z: float
    evidence: dict[str, JSONValue]


def compare_price(tender: Tender, ctx: DetectionContext) -> PriceComparison | str:
    """Return the comparison, or the reason it cannot be made."""
    if tender.award_value is None:
        return "award value not published"
    if tender.award_value < MIN_PLAUSIBLE_VALUE:
        return f"award value below R{MIN_PLAUSIBLE_VALUE}: placeholder or capture error"
    if tender.close_date is None:
        return "tender close date not published"
    if not tender.category:
        return "tender category not published"
    if is_generic(tender.category):
        return f"tender category too broad to compare prices: {tender.category}"

    start = months_before(tender.close_date, WINDOW_MONTHS)
    comparables = [
        a
        for a in ctx.awards_in_category(tender.category, start, tender.close_date)
        if a.ocid != tender.ocid
        and a.award_value is not None
        and a.award_value >= MIN_PLAUSIBLE_VALUE
    ]
    if len(comparables) < MIN_COMPARABLES:
        return f"only {len(comparables)} comparable awards; need {MIN_COMPARABLES}"

    logs = [math.log10(a.award_value) for a in comparables if a.award_value is not None]
    median = statistics.median(logs)
    mad = statistics.median(abs(v - median) for v in logs)
    if mad == 0:
        return "comparable awards have no price spread"

    z = (math.log10(tender.award_value) - median) / (MAD_TO_SD * mad)
    median_value = 10**median
    recent = sorted(comparables, key=lambda a: (a.close_date, a.tender_id), reverse=True)
    chart: list[JSONValue] = [
        {
            "tender_id": a.tender_id,
            "buyer_name": a.buyer_name,
            "close_date": a.close_date.isoformat() if a.close_date else None,
            "award_value": str(a.award_value),
        }
        for a in recent[:CHART_COMPARABLES]
    ]
    evidence: dict[str, JSONValue] = {
        "award_value": str(tender.award_value),
        "category": tender.category,
        "window_start": start.isoformat(),
        "window_end": tender.close_date.isoformat(),
        "comparable_count": len(comparables),
        "comparable_median": f"{median_value:.2f}",
        "percent_vs_median": round((float(tender.award_value) / median_value - 1) * 100, 1),
        "robust_z": round(z, 2),
        "comparables": chart,
    }
    return PriceComparison(robust_z=z, evidence=evidence)
