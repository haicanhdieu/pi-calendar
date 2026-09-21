from src.app import App
from src.time.model import DateTime
from src.ui.calendar_view import CalendarView
from src.ui.clock_view import ClockView
from src.ui.display_port import FakeDisplayPort
from tests.test_app_loop import FakeClockPort, FakeTicks


class FakeBuzzer:
    def __init__(self):
        self.ticks = []
        self.silence_count = 0

    def tick(self, now, sounding):
        self.ticks.append((now, sounding))

    def silence(self):
        self.silence_count += 1


def _app(clock, ticks, buzzer, alerts):
    display = FakeDisplayPort()
    return App(
        clock_port=clock,
        clock_view=ClockView(display),
        calendar_view=CalendarView(display),
        ticks_module=ticks,
        sync_enabled=False,
        buzzer_port=buzzer,
        alert_settings={"alerts": alerts, "postpone_delay_minutes": 10},
    ), display


def test_due_alert_takes_over_and_ticks_buzzer_once_each_active_pass():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    app, display = _app(clock, ticks, buzzer, [{
        "id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2],
    }])
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    assert app._active_alert is not None
    assert buzzer.ticks == [(1000, True)]
    assert any(op[0] == "draw_text" and op[1] == "ALERT" for op in display.ops)

    ticks.advance(1000)
    app.step()
    assert len(buzzer.ticks) == 2


def test_auto_stop_silences_and_returns_to_rotation():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    app, _display = _app(clock, ticks, buzzer, [{
        "id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2],
    }])
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    ticks.advance(300000)
    app.step()
    assert app._active_alert is None
    assert buzzer.silence_count == 1
    assert app.state.active_surface == "rotation"


def test_repeating_alert_remains_enabled_after_auto_stop():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    repeat = {"id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2]}
    app, _display = _app(clock, ticks, buzzer, [repeat])
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    ticks.advance(300000)
    app.step()
    assert app._alert_settings["alerts"][0]["enabled"] is True
