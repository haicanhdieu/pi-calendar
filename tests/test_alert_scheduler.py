from src.alert.scheduler import AlertScheduler
from src.time.model import DateTime


def local(hour, minute, weekday=2, day=9, month=9, year=2026):
    return DateTime(year, month, day, weekday, hour, minute, 0)


def alert(alert_id="wake", hour=7, minute=0, enabled=True, weekdays=None):
    return {
        "id": alert_id,
        "hour": hour,
        "minute": minute,
        "enabled": enabled,
        "weekdays": [] if weekdays is None else weekdays,
    }


def test_boot_matching_minute_is_baseline_not_retrofired():
    scheduler = AlertScheduler()
    assert scheduler.evaluate(local(7, 0), [alert()]) == []


def test_matching_minute_raises_once_and_backward_revisit_does_not_repeat():
    scheduler = AlertScheduler()
    item = alert(weekdays=[2])
    scheduler.evaluate(local(6, 59), [item])
    assert scheduler.evaluate(local(7, 0), [item]) == [item]
    assert scheduler.evaluate(local(7, 0), [item]) == []
    assert scheduler.evaluate(local(6, 59), [item]) == []
    assert scheduler.evaluate(local(7, 0), [item]) == []


def test_disabled_and_wrong_weekday_alerts_do_not_raise():
    scheduler = AlertScheduler()
    scheduler.evaluate(local(6, 59), [])
    assert scheduler.evaluate(
        local(7, 0),
        [alert("off", enabled=False), alert("weekend", weekdays=[5])],
    ) == []


def test_month_year_and_weekday_boundaries_match_current_local_minute():
    scheduler = AlertScheduler()
    scheduler.evaluate(local(23, 59, weekday=6, day=31, month=12), [])
    assert scheduler.evaluate(
        local(0, 0, weekday=0, day=1, month=1, year=2027),
        [alert(hour=0, minute=0, weekdays=[0])],
    )


def test_no_local_snapshot_does_not_advance_baseline():
    scheduler = AlertScheduler()
    assert scheduler.evaluate(None, [alert()]) == []
    assert scheduler.evaluate(local(6, 59), []) == []


def test_same_minute_alerts_raise_together_once():
    scheduler = AlertScheduler()
    first = alert("first")
    second = alert("second")
    scheduler.evaluate(local(6, 59), [first, second])

    assert scheduler.evaluate(local(7, 0), [first, second]) == [first, second]
    assert scheduler.evaluate(local(7, 0), [first, second]) == []


def test_add_minutes_handles_month_and_year_boundaries():
    from src.alert.scheduler import add_minutes

    assert add_minutes(local(23, 55, day=31, month=12), 10) == local(
        0, 5, weekday=4, day=1, month=1, year=2027
    )
