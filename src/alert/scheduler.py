"""Pure local-civil-time alert due detection."""

from src.calendar.gregorian import days_in_month, weekday_from_ymd
from src.time.model import DateTime


DEFAULT_POSTPONE_MINUTES = 10
MIN_POSTPONE_MINUTES = 1
MAX_POSTPONE_MINUTES = 60


def normalize_postpone_minutes(value):
    """Return a safe whole-minute delay for untrusted settings."""
    if isinstance(value, bool):
        return DEFAULT_POSTPONE_MINUTES
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_POSTPONE_MINUTES
    if value < MIN_POSTPONE_MINUTES:
        return DEFAULT_POSTPONE_MINUTES
    return min(value, MAX_POSTPONE_MINUTES)


def add_minutes(local, minutes):
    """Return a normalized local DateTime advanced by whole minutes."""
    total = local.hour * 60 + local.minute + int(minutes)
    day_delta, minute = divmod(total, 24 * 60)
    year, month, day = local.year, local.month, local.day
    while day_delta > 0:
        day += 1
        if day > days_in_month(year, month):
            day = 1
            month += 1
            if month > 12:
                month = 1
                year += 1
        day_delta -= 1
    return DateTime(
        year, month, day, weekday_from_ymd(year, month, day),
        minute // 60, minute % 60, 0,
    )


def minute_key(local):
    return (local.year, local.month, local.day, local.hour, local.minute)


def due_reached(local, due):
    return local is not None and due is not None and minute_key(local) >= minute_key(due)


class AlertScheduler:
    """Detect current-minute matches without retrofires or duplicate raises."""

    __slots__ = ("_last_minute", "_raised_keys")

    def __init__(self):
        self._last_minute = None
        self._raised_keys = set()

    @staticmethod
    def _minute(local):
        return (local.year, local.month, local.day, local.hour, local.minute)

    @staticmethod
    def _matches(alert, local):
        if not isinstance(alert, dict) or alert.get("enabled") is not True:
            return False
        if alert.get("hour") != local.hour or alert.get("minute") != local.minute:
            return False
        weekdays = alert.get("weekdays", ())
        return not weekdays or local.weekday in weekdays

    def evaluate(self, local, alerts):
        """Return enabled alerts due in current minute.

        First observation establishes boot baseline. Later matching minutes
        raise only once per alert/date/minute key, including backward jumps.
        """
        if local is None:
            return []
        minute = self._minute(local)
        if self._last_minute is None:
            self._last_minute = minute
            return []
        self._last_minute = minute
        due = []
        for alert in alerts or ():
            if not self._matches(alert, local):
                continue
            key = (alert.get("id"), local.year, local.month, local.day, local.hour, local.minute)
            if key in self._raised_keys:
                continue
            self._raised_keys.add(key)
            due.append(dict(alert))
        return due
