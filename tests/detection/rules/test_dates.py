from datetime import date

import pytest

from detection.rules._dates import months_before


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2025, 3, 14), 24, date(2023, 3, 14)),
        (date(2025, 3, 31), 1, date(2025, 2, 28)),
        (date(2024, 3, 31), 1, date(2024, 2, 29)),
        (date(2026, 2, 28), 24, date(2024, 2, 28)),
        (date(2025, 1, 15), 1, date(2024, 12, 15)),
        (date(2025, 1, 15), 0, date(2025, 1, 15)),
    ],
)
def test_months_before(day: date, months: int, expected: date) -> None:
    assert months_before(day, months) == expected


def test_rejects_negative_months() -> None:
    with pytest.raises(ValueError, match="negative"):
        months_before(date(2025, 1, 1), -1)
