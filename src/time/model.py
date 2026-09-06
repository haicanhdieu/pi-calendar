"""Pure time domain types and calendar-entry gate."""

TRUST_SYNCED = "synced"
TRUST_UNSYNCED = "unsynced"


class DateTime:
    """Named wall-clock fields shared by UTC and local snapshots."""

    __slots__ = ("year", "month", "day", "weekday", "hour", "minute", "second")

    def __init__(self, year, month, day, weekday, hour, minute, second):
        self.year = year
        self.month = month
        self.day = day
        self.weekday = weekday
        self.hour = hour
        self.minute = minute
        self.second = second

    def __eq__(self, other):
        if not isinstance(other, DateTime):
            return NotImplemented
        return (
            self.year == other.year
            and self.month == other.month
            and self.day == other.day
            and self.weekday == other.weekday
            and self.hour == other.hour
            and self.minute == other.minute
            and self.second == other.second
        )

    def __repr__(self):
        return (
            "DateTime(year={}, month={}, day={}, weekday={}, "
            "hour={}, minute={}, second={})"
        ).format(
            self.year,
            self.month,
            self.day,
            self.weekday,
            self.hour,
            self.minute,
            self.second,
        )


class TimeSnapshot:
    """Glanceable time state for renderers and view gating."""

    __slots__ = ("utc", "local", "trust", "sync_age_ms")

    def __init__(self, utc, local, trust, sync_age_ms):
        self.utc = utc
        self.local = local
        self.trust = trust
        self.sync_age_ms = sync_age_ms

    def __eq__(self, other):
        if not isinstance(other, TimeSnapshot):
            return NotImplemented
        return (
            self.utc == other.utc
            and self.local == other.local
            and self.trust == other.trust
            and self.sync_age_ms == other.sync_age_ms
        )

    def __repr__(self):
        return (
            "TimeSnapshot(utc={!r}, local={!r}, trust={!r}, sync_age_ms={!r})"
        ).format(self.utc, self.local, self.trust, self.sync_age_ms)


def calendar_entry_allowed(snapshot):
    """Calendar may be entered only when a local DateTime exists."""
    return snapshot.local is not None
