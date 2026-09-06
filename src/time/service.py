"""Pure UTC→local conversion and snapshot construction (no device imports)."""

from src import config
from src.time.model import TRUST_UNSYNCED, DateTime, TimeSnapshot


def _days_in_month(year, month):
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def utc_to_local(utc, offset_hours=config.LOCAL_UTC_OFFSET_HOURS):
    """Return a DateTime shifted by a fixed hour offset (no DST)."""
    hour = utc.hour + offset_hours
    day = utc.day
    month = utc.month
    year = utc.year
    weekday = utc.weekday

    while hour >= 24:
        hour -= 24
        day += 1
        weekday = (weekday + 1) % 7
        dim = _days_in_month(year, month)
        if day > dim:
            day = 1
            month += 1
            if month > 12:
                month = 1
                year += 1

    while hour < 0:
        hour += 24
        day -= 1
        weekday = (weekday - 1) % 7
        if day < 1:
            month -= 1
            if month < 1:
                month = 12
                year -= 1
            day = _days_in_month(year, month)

    return DateTime(
        year=year,
        month=month,
        day=day,
        weekday=weekday,
        hour=hour,
        minute=utc.minute,
        second=utc.second,
    )


def make_snapshot(utc, trust, sync_age_ms):
    """
    Build a TimeSnapshot from injected validity/trust/age.

    When ``utc`` is absent (cold boot / invalid RTC), date-times and age are
    absent and trust is forced to unsynced.
    """
    if utc is None:
        return TimeSnapshot(
            utc=None,
            local=None,
            trust=TRUST_UNSYNCED,
            sync_age_ms=None,
        )

    return TimeSnapshot(
        utc=utc,
        local=utc_to_local(utc),
        trust=trust,
        sync_age_ms=sync_age_ms,
    )
