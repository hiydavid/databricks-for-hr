"""Small calendar helpers (no external date dependency)."""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_days(d: date, days: int) -> date:
    return d + timedelta(days=days)


def days_between(a: date, b: date) -> int:
    return (b - a).days


def iso(d: date) -> str:
    return d.isoformat()


def yesterday(today: date | None = None) -> date:
    today = today or date.today()
    return today - timedelta(days=1)


def next_sunday(d: date) -> date:
    return d + timedelta(days=(6 - d.weekday()) % 7)


def iter_weeks(start: date, end: date):
    """Yield every week_start (Sunday) in ``[start, end]``."""
    cur = start + timedelta(days=(6 - start.weekday()) % 7)
    while cur <= end:
        yield cur
        cur += timedelta(days=7)
