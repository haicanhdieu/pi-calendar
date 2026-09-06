"""Pure view-rotation and local-date rollover decisions (AD-12)."""

from src.time.model import calendar_entry_allowed

VIEW_CLOCK = "clock"
VIEW_CALENDAR = "calendar"


def classify_local_rollover(prev_ymd, local):
    """
    Classify a local civil-date change relative to a previous (y, m, d).

    Returns ``None`` when there is no prior date, no local, or no change;
    ``"day"`` for a same-month day change; ``"month"`` when year or month
    differs.
    """
    if local is None or prev_ymd is None:
        return None
    prev_y, prev_m, prev_d = prev_ymd
    if local.year != prev_y or local.month != prev_m:
        return "month"
    if local.day != prev_d:
        return "day"
    return None


def next_view_after_dwell(active, snapshot):
    """
    Decide the next active view when a dwell deadline expires.

    Clock → Calendar only when ``calendar_entry_allowed(snapshot)``; otherwise
    stay on Clock. Calendar always returns to Clock.
    """
    if active == VIEW_CALENDAR:
        return VIEW_CLOCK
    if active == VIEW_CLOCK and calendar_entry_allowed(snapshot):
        return VIEW_CALENDAR
    return VIEW_CLOCK
