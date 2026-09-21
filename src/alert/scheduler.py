"""Pure local-civil-time alert due detection."""


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
