"""Small, well-tested date helpers. Calendar edge cases live here and nowhere else."""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def add_months(d: date, months: int) -> date:
    """Calendar-month arithmetic, clamped to the end of the target month.

    Jan 31 + 1 month -> Feb 28 (or Feb 29 in a leap year), not Mar 3.
    """
    month_index = d.month - 1 + months
    year, month0 = divmod(month_index, 12)
    year += d.year
    last_day = calendar.monthrange(year, month0 + 1)[1]
    return date(year, month0 + 1, min(d.day, last_day))


def next_business_day(d: date) -> date:
    """Roll a Saturday/Sunday forward to Monday. Federal holidays are NOT modeled."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def safe_date(year: int, month: int, day: int) -> date:
    """date() that clamps day 29-31 to the month's end instead of raising."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))
