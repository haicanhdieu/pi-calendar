from src.app import App
from src import config
from src.time.model import DateTime
from src.ui.calendar_view import CalendarView
from src.ui.clock_view import ClockView
from src.ui.display_port import FakeDisplayPort
from tests.test_app_loop import FakeClockPort, FakeTicks
from tests.test_settings_store import FakeFS, _record_bytes, _store
import json


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


def test_alert_due_while_active_joins_without_restarting_deadline():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    app, display = _app(clock, ticks, buzzer, [
        {"id": "first", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2]},
        {"id": "second", "hour": 14, "minute": 1, "enabled": True, "weekdays": [2]},
    ])
    app.step()

    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    assert [item["id"] for item in app._active_alert["alerts"]] == ["first"]
    started = app._alert_started_ticks

    clock._utc = DateTime(2026, 9, 9, 2, 7, 1, 0)
    ticks.advance(1000)
    app.step()

    assert [item["id"] for item in app._active_alert["alerts"]] == ["first", "second"]
    assert app._alert_started_ticks == started
    assert buzzer.ticks == [(1000, True), (2000, True)]
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "2 ALERTS" in texts


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


def test_stop_tap_silences_before_buzzer_tick_and_rearms_last_view():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    touch = type("Touch", (), {"read": lambda self: (False, None, None)})()
    app, _display = _app(clock, ticks, buzzer, [{
        "id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2],
    }])
    app._touch_port = touch
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    assert app._active_alert is not None

    touch.read = lambda: (True, 160, 120)
    ticks.advance(1000)
    app.step()

    assert app._active_alert is None
    assert buzzer.silence_count == 1
    assert buzzer.ticks == [(1000, True)]
    assert app.state.active_surface == "rotation"
    assert app.state.view_deadline == ticks.ticks_add(2000, config.CLOCK_DWELL_MS)


def test_stop_disables_existing_one_time_alert_but_not_missing_id():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    alert = {"id": "once", "hour": 14, "minute": 0, "enabled": True, "weekdays": []}
    touch = type("Touch", (), {"read": lambda self: (False, None, None)})()
    app, _display = _app(clock, ticks, buzzer, [alert])
    app._touch_port = touch
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    touch.read = lambda: (True, 160, 120)
    ticks.advance(1000)
    app.step()

    assert app._active_alert is None
    assert app._alert_settings["alerts"][0]["enabled"] is False
    assert alert["enabled"] is True


def test_stop_resolves_all_joined_alerts_with_one_time_member_disabled():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    touch = type("Touch", (), {"read": lambda self: (False, None, None)})()
    repeating = {"id": "repeat", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2]}
    one_time = {"id": "once", "hour": 14, "minute": 0, "enabled": True, "weekdays": []}
    app, _display = _app(clock, ticks, buzzer, [repeating, one_time])
    app._touch_port = touch
    app.step()

    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    assert [item["id"] for item in app._active_alert["alerts"]] == ["repeat", "once"]

    touch.read = lambda: (True, 160, 120)
    ticks.advance(1000)
    app.step()

    assert app._active_alert is None
    saved = {item["id"]: item for item in app._alert_settings["alerts"]}
    assert saved["repeat"]["enabled"] is True
    assert saved["once"]["enabled"] is False


def test_stop_replay_before_release_cannot_open_normal_bar():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    samples = [(False, None, None)]
    class Touch:
        def read(self):
            return samples.pop(0) if samples else (True, 160, 120)
    app, _display = _app(clock, ticks, buzzer, [{
        "id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2],
    }])
    app._touch_port = Touch()
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    samples.append((True, 160, 120))
    ticks.advance(1000)
    app.step()
    assert app._active_alert is None
    ticks.advance(1000)
    app.step()
    assert app.state.active_surface == "rotation"


def test_postpone_silences_before_tick_confirms_due_time_and_realerts_once():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    touch = type("Touch", (), {"read": lambda self: (False, None, None)})()
    app, display = _app(clock, ticks, buzzer, [{
        "id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2],
    }])
    app._touch_port = touch
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    touch.read = lambda: (True, 160, 220)
    ticks.advance(1000)
    app.step()

    assert app._active_alert is None
    assert app._postponed_alert["due"].hour == 14
    assert app._postponed_alert["due"].minute == 10
    assert buzzer.silence_count == 1
    assert buzzer.ticks == [(1000, True)]
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "DUE 2026-09-09 14:10" in texts

    ticks.advance(1000)
    app.step()
    assert app._active_alert is None
    assert buzzer.ticks == [(1000, True)]

    touch.read = lambda: (False, None, None)
    clock._utc = DateTime(2026, 9, 9, 2, 17, 0, 0)
    ticks.advance(600000)
    app.step()
    assert app._active_alert is not None
    assert [item["id"] for item in app._active_alert["alerts"]] == ["wake"]
    assert buzzer.ticks[-1] == (603000, True)


def test_postpone_release_latch_prevents_replayed_edge_from_navigation():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    samples = [(False, None, None)]

    class Touch:
        def read(self):
            return samples.pop(0) if samples else (True, 10, 10)

    app, _display = _app(clock, ticks, buzzer, [{
        "id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2],
    }])
    app._touch_port = Touch()
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    samples.append((True, 160, 220))
    ticks.advance(1000)
    app.step()
    ticks.advance(1000)
    app.step()
    assert app.state.active_surface == "rotation"


def test_invalid_postpone_delay_uses_safe_default():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    touch = type("Touch", (), {"read": lambda self: (False, None, None)})()
    app, _display = _app(clock, ticks, buzzer, [{
        "id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2],
    }])
    app._alert_cfg = (buzzer, None, {"alerts": app._alert_cfg[2]["alerts"], "postpone_delay_minutes": "bad"})
    app._touch_port = touch
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    touch.read = lambda: (True, 160, 220)
    ticks.advance(1000)
    app.step()
    assert app._postponed_alert["due"].minute == 10


def test_postponed_one_time_alert_disables_existing_id_only_after_resolution():
    ticks = FakeTicks(0)
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    touch = type("Touch", (), {"read": lambda self: (False, None, None)})()
    alert = {"id": "once", "hour": 14, "minute": 0, "enabled": True, "weekdays": []}
    app, _display = _app(clock, ticks, buzzer, [alert])
    app._touch_port = touch
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    touch.read = lambda: (True, 160, 220)
    ticks.advance(1000)
    app.step()
    touch.read = lambda: (False, None, None)
    clock._utc = DateTime(2026, 9, 9, 2, 17, 0, 0)
    ticks.advance(600000)
    app.step()
    touch.read = lambda: (True, 160, 120)
    ticks.advance(1000)
    app.step()
    assert app._alert_settings["alerts"][0]["enabled"] is False
    assert alert["enabled"] is True


def _persisted_alert_store(alerts, pending=None):
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2,
        alerts=alerts,
        postpone_delay_minutes=10,
        pending_postponed_occurrence=pending,
    )})
    return fs, _store(fs)


def _pending(due_hour, due_minute, alerts):
    return {
        "due": {
            "year": 2026, "month": 9, "day": 9, "weekday": 2,
            "hour": due_hour, "minute": due_minute,
        },
        "alerts": alerts,
        "delay": 10,
    }


def test_future_pending_postpone_restores_after_reboot_and_raises_at_due_time():
    ticks = FakeTicks(0)
    alert = {"id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2]}
    fs, store = _persisted_alert_store([alert], _pending(14, 10, [alert]))
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 5, 0))
    buzzer = FakeBuzzer()
    app = App(
        clock_port=clock, clock_view=ClockView(FakeDisplayPort()),
        calendar_view=CalendarView(FakeDisplayPort()), ticks_module=ticks,
        sync_enabled=False, buzzer_port=buzzer, settings_store=store,
    )

    app.step()
    assert app._active_alert is None
    assert buzzer.ticks == []
    clock._utc = DateTime(2026, 9, 9, 2, 7, 10, 0)
    ticks.advance(300000)
    app.step()

    assert [item["id"] for item in app._active_alert["alerts"]] == ["wake"]
    assert buzzer.ticks == [(300000, True)]
    assert json.loads(fs.files[".settings-v1"])["pending_postponed_occurrence"] is None


def test_overdue_pending_postpone_is_cleared_without_sound_and_base_alerts_remain():
    ticks = FakeTicks(0)
    alert = {"id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2]}
    fs, store = _persisted_alert_store([alert], _pending(14, 0, [alert]))
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 7, 5, 0))
    buzzer = FakeBuzzer()
    app = App(
        clock_port=clock, clock_view=ClockView(FakeDisplayPort()),
        calendar_view=CalendarView(FakeDisplayPort()), ticks_module=ticks,
        sync_enabled=False, buzzer_port=buzzer, settings_store=store,
    )

    app.step()

    saved = json.loads(fs.files[".settings-v1"])
    assert saved["pending_postponed_occurrence"] is None
    assert saved["alerts"] == [alert]
    assert app._active_alert is None
    assert buzzer.ticks == []


def test_postpone_commit_captures_members_and_preserves_unrelated_settings():
    ticks = FakeTicks(0)
    alert = {"id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2]}
    fs, store = _persisted_alert_store([alert])
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    touch = type("Touch", (), {"read": lambda self: (False, None, None)})()
    app = App(
        clock_port=clock, clock_view=ClockView(FakeDisplayPort()),
        calendar_view=CalendarView(FakeDisplayPort()), ticks_module=ticks,
        sync_enabled=False, buzzer_port=buzzer, settings_store=store,
        touch_port=touch,
    )
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    touch.read = lambda: (True, 160, 220)
    ticks.advance(1000)
    app.step()

    saved = json.loads(fs.files[".settings-v1"])
    pending = saved["pending_postponed_occurrence"]
    assert saved["wifi_ssid"] == "ssid"
    assert saved["admin_verifier"]
    assert pending["alerts"] == [alert]
    assert pending["due"]["hour"] == 14
    assert pending["due"]["minute"] == 10


def test_active_occurrence_survives_committed_edit_without_resetting_lifecycle():
    ticks = FakeTicks(0)
    alert = {"id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2]}
    fs, store = _persisted_alert_store([alert])
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    app = App(
        clock_port=clock, clock_view=ClockView(FakeDisplayPort()),
        calendar_view=CalendarView(FakeDisplayPort()), ticks_module=ticks,
        sync_enabled=False, buzzer_port=buzzer, settings_store=store,
    )
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    started = app._alert_started_ticks
    captured = [dict(item) for item in app._active_alert["alerts"]]

    store.commit(
        wifi_ssid="ssid", wifi_password="password", admin_salt_hex="00" * 16,
        admin_verifier_hex="11" * 32, color_scheme="forest-amber",
        alerts=[{"id": "wake", "hour": 15, "minute": 0, "enabled": False, "weekdays": [2]}],
        postpone_delay_minutes=10,
    )
    ticks.advance(1000)
    app.step()

    assert app._active_alert["alerts"] == captured
    assert app._alert_started_ticks == started
    assert buzzer.ticks == [(1000, True), (2000, True)]
    assert app._alert_cfg[2]["alerts"][0]["enabled"] is False


def test_committed_alert_joins_active_occurrence_at_next_loop_boundary():
    ticks = FakeTicks(0)
    first = {"id": "first", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2]}
    fs, store = _persisted_alert_store([first])
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    app = App(
        clock_port=clock, clock_view=ClockView(FakeDisplayPort()),
        calendar_view=CalendarView(FakeDisplayPort()), ticks_module=ticks,
        sync_enabled=False, buzzer_port=buzzer, settings_store=store,
    )
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    started = app._alert_started_ticks

    second = {"id": "second", "hour": 14, "minute": 1, "enabled": True, "weekdays": [2]}
    store.commit(
        wifi_ssid="ssid", wifi_password="password", admin_salt_hex="00" * 16,
        admin_verifier_hex="11" * 32, color_scheme="forest-amber",
        alerts=[first, second], postpone_delay_minutes=10,
    )
    clock._utc = DateTime(2026, 9, 9, 2, 7, 1, 0)
    ticks.advance(1000)
    app.step()

    assert [item["id"] for item in app._active_alert["alerts"]] == ["first", "second"]
    assert app._alert_started_ticks == started
    assert buzzer.ticks == [(1000, True), (2000, True)]


def test_postponed_occurrence_keeps_captured_member_after_committed_delete():
    ticks = FakeTicks(0)
    alert = {"id": "wake", "hour": 14, "minute": 0, "enabled": True, "weekdays": [2]}
    fs, store = _persisted_alert_store([alert])
    clock = FakeClockPort(DateTime(2026, 9, 9, 2, 6, 59, 0))
    buzzer = FakeBuzzer()
    touch = type("Touch", (), {"read": lambda self: (False, None, None)})()
    app = App(
        clock_port=clock, clock_view=ClockView(FakeDisplayPort()),
        calendar_view=CalendarView(FakeDisplayPort()), ticks_module=ticks,
        sync_enabled=False, buzzer_port=buzzer, settings_store=store,
        touch_port=touch,
    )
    app.step()
    clock._utc = DateTime(2026, 9, 9, 2, 7, 0, 0)
    ticks.advance(1000)
    app.step()
    touch.read = lambda: (True, 160, 220)
    ticks.advance(1000)
    app.step()
    captured = [dict(item) for item in app._postponed_alert["alerts"]]
    due = app._postponed_alert["due"]

    store.commit(
        wifi_ssid="ssid", wifi_password="password", admin_salt_hex="00" * 16,
        admin_verifier_hex="11" * 32, color_scheme="forest-amber", alerts=[], postpone_delay_minutes=60,
    )
    touch.read = lambda: (False, None, None)
    clock._utc = DateTime(2026, 9, 9, 2, 17, 0, 0)
    ticks.advance(600000)
    app.step()

    assert app._active_alert["alerts"] == captured
    assert app._active_alert["local"] == due
    assert app._alert_cfg[2]["alerts"] == []
