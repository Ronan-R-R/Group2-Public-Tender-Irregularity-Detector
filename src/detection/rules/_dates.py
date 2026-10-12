from __future__ import annotations

import calendar
from datetime import date


def months_before(day: date, months: int) -> date:
    """Same calendar day ``months`` earlier, clamped to the end of short months.

    31 March minus one month is 28 (or 29) February, not an error.
    """
    if months < 0:
        raise ValueError("months must not be negative")
    total = day.year * 12 + (day.month - 1) - months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
