"""RTC-backed ClockPort (device layer only; AD-3)."""

from machine import RTC

from src.time.model import DateTime

# Unset / power-loss defaults are typically year 2000 or 2021 — reject those.
_MIN_VALID_YEAR = 2024
_MAX_VALID_YEAR = 2099


def _days_in_month(year, month):
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


class RtcClockPort:
    """
    Read/write UTC wall time through ``machine.RTC``.

    Only App should call this. Invalid or unset RTC values map to ``None``.
    Never calls ``ntptime.settime()``.
    """

    def __init__(self, rtc=None):
        self._rtc = rtc if rtc is not None else RTC()

    def read_utc(self):
        """Return a ``DateTime`` from the RTC, or ``None`` if cold/invalid."""
        try:
            parts = self._rtc.datetime()
        except (OSError, RuntimeError, AttributeError, TypeError, ValueError):
            return None
        if parts is None:
            return None
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            weekday = int(parts[3])
            hour = int(parts[4])
            minute = int(parts[5])
            second = int(parts[6])
        except (IndexError, TypeError, ValueError):
            return None
        if not (_MIN_VALID_YEAR <= year <= _MAX_VALID_YEAR):
            return None
        if not (1 <= month <= 12):
            return None
        if not (1 <= day <= _days_in_month(year, month)):
            return None
        if not (0 <= weekday <= 6):
            return None
        if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
            return None
        return DateTime(year, month, day, weekday, hour, minute, second)

    def set_utc(self, dt):
        """Write a ``DateTime`` into the RTC (UTC). Subseconds forced to 0."""
        if dt is None:
            return
        # MicroPython: (year, month, day, weekday, hour, minute, second, subsecond)
        self._rtc.datetime(
            (
                int(dt.year),
                int(dt.month),
                int(dt.day),
                int(dt.weekday),
                int(dt.hour),
                int(dt.minute),
                int(dt.second),
                0,
            )
        )
