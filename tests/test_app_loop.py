"""Host tests for App loop, ClockPort fakes, and pure-module boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from src import config
from src import ticks
from src.app import VIEW_CALENDAR, VIEW_CLOCK, App, AppState
from src.time.model import TRUST_SYNCED, TRUST_UNSYNCED, DateTime
from src.ui.calendar_view import CalendarView
from src.ui.clock_view import ClockView
from src.ui.display_port import FakeDisplayPort
from src.ui.touch_state import SURFACE_BAR, SURFACE_ROTATION, SURFACE_SETTINGS

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"machine", "network", "ntptime", "src.device"}
)
PURE_APP_MODULES = (
    ROOT / "src" / "app.py",
    ROOT / "src" / "ticks.py",
    ROOT / "src" / "ui" / "view_state.py",
)


def _remember_module(roots: set[str], name: str) -> None:
    if not name:
        return
    parts = name.split(".")
    for i in range(len(parts)):
        roots.add(".".join(parts[: i + 1]))


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _remember_module(roots, alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _remember_module(roots, node.module)
            for alias in node.names:
                _remember_module(roots, f"{node.module}.{alias.name}")
    return roots


class FakeTicks:
    """Injectable tick source for host-driven App.step(now_ticks=...)."""

    PERIOD = 2**32

    def __init__(self, start=0):
        self.now = start

    def ticks_ms(self):
        return self.now & (self.PERIOD - 1)

    def ticks_add(self, ticks_val, delta_ms):
        return (int(ticks_val) + int(delta_ms)) & (self.PERIOD - 1)

    def ticks_diff(self, ticks1, ticks2):
        diff = (int(ticks1) - int(ticks2)) & (self.PERIOD - 1)
        if diff >= self.PERIOD // 2:
            diff -= self.PERIOD
        return diff

    def advance(self, ms):
        self.now = self.ticks_add(self.now, ms)


class FakeClockPort:
    """Advancing or cold UTC source for host composition tests."""

    def __init__(self, utc=None):
        self._utc = utc
        self.read_count = 0
        self.set_calls = []

    def read_utc(self):
        self.read_count += 1
        return self._utc

    def set_utc(self, dt):
        self.set_calls.append(dt)
        self._utc = dt

    def advance_second(self):
        if self._utc is None:
            return
        s = self._utc.second + 1
        m = self._utc.minute
        h = self._utc.hour
        if s >= 60:
            s = 0
            m += 1
        if m >= 60:
            m = 0
            h = (h + 1) % 24
        self._utc = DateTime(
            self._utc.year,
            self._utc.month,
            self._utc.day,
            self._utc.weekday,
            h,
            m,
            s,
        )


class FakeTouchPort:
    """One-sample-per-step fake for the device-agnostic App seam."""

    def __init__(self, samples):
        self.samples = list(samples)
        self.read_count = 0

    def read(self):
        self.read_count += 1
        if self.samples:
            return self.samples.pop(0)
        return (False, None, None)


def _utc(hour=7, minute=0, second=0):
    # 2026-09-06 Sunday(=6) 07:00 UTC → 14:00 local
    return DateTime(2026, 9, 6, 6, hour, minute, second)


class FakeRebootPort:
    """Records reset invocations for host App wiring tests."""

    def __init__(self, events=None, sleep=None):
        self.reset_count = 0
        self._events = events
        self._sleep = sleep

    def reset(self):
        if self._sleep is not None:
            assert self._sleep.calls, "reset invoked before press-flash dwell"
        if self._events is not None:
            self._events.append("reset")
        self.reset_count += 1


class RecordingSleepMs:
    """Records sleep durations for flash-before-reset ordering tests."""

    def __init__(self, events=None):
        self.calls = []
        self._events = events

    def __call__(self, ms):
        if self._events is not None:
            self._events.append("sleep")
        self.calls.append(ms)


def _settings_reboot_center(display):
    from src.ui.components import settings_reboot_item_rect

    x, y, w, h = settings_reboot_item_rect(display)
    return x + w // 2, y + h // 2


def _make_app(
    utc=_utc(),
    ticks_mod=None,
    touch_port=None,
    mailbox=None,
    reboot_port=None,
    sleep_ms_fn=None,
):
    display = FakeDisplayPort()
    view = ClockView(display)
    calendar = CalendarView(display)
    clock = FakeClockPort(utc)
    ft = ticks_mod if ticks_mod is not None else FakeTicks(0)
    logs = []
    app = App(
        clock_port=clock,
        clock_view=view,
        calendar_view=calendar,
        ticks_module=ft,
        log=logs.append,
        touch_port=touch_port,
        mailbox=mailbox,
        reboot_port=reboot_port,
        sleep_ms_fn=sleep_ms_fn,
    )
    return app, clock, view, display, ft, logs, calendar


def test_touch_edge_is_polled_once_and_committed_before_sync_work():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 123, 45)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )

    class OrderingMailbox:
        def try_take_result(self):
            assert app.state.active_surface == SURFACE_BAR
            assert app.state.surface_deadline == ft.ticks_add(
                ft.now, config.TOUCH_IDLE_TIMEOUT_MS
            )
            return None

        def enqueue(self, _command):
            return False

    app._mailbox = OrderingMailbox()
    app.boot()
    app.step(now_ticks=ft.now)

    assert touch.read_count == 1
    assert app.state.active_surface == SURFACE_BAR
    assert app.state.surface_deadline == config.TOUCH_IDLE_TIMEOUT_MS
    assert app.state.redraw_deadline == config.BAR_ANIMATION_FRAME_MS


def test_bar_freezes_view_dwell_and_reveals_on_frame_cadence():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0)])
    app, _clock, _view, display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.state.view_deadline = 0
    app.step(now_ticks=ft.now)
    deadline = app.state.view_deadline
    assert app.state.active_view == VIEW_CLOCK
    assert deadline == 0

    display.clear_ops()
    ft.advance(config.BAR_SLIDE_DURATION_MS)
    app.step(now_ticks=ft.now)
    assert touch.read_count == 2
    assert app.state.active_surface == SURFACE_BAR
    assert app.state.active_view == VIEW_CLOCK
    assert app.state.view_deadline == deadline
    assert (
        "fill_rect",
        0,
        display.height - config.BAR_HEIGHT_PX,
        display.width,
        config.BAR_HEIGHT_PX,
        config.COLOR_BAR_PANEL,
    ) in display.ops


def test_bar_idle_timeout_retracts_and_rearms_retained_clock_dwell():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.step(now_ticks=ft.now)
    ft.advance(config.TOUCH_IDLE_TIMEOUT_MS)
    app.step(now_ticks=ft.now)
    assert app.state.active_surface == SURFACE_ROTATION
    assert app.state.surface_deadline is None
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CLOCK_DWELL_MS)
    assert app._bar_retract_started == ft.now


def test_bar_outside_edge_retracts_and_rearms_retained_calendar_dwell():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 0, 0)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.state.active_view = VIEW_CALENDAR
    app.step(now_ticks=ft.now)
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_ROTATION
    assert app.state.surface_deadline is None
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CALENDAR_DWELL_MS)


def test_partial_bar_retracts_from_its_current_visible_height():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 0, 0)])
    app, _clock, _view, display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.step(now_ticks=ft.now)
    revealed_height = app._bar_visible_height
    assert 0 < revealed_height < config.BAR_HEIGHT_PX

    display.clear_ops()
    ft.advance(1)
    app.step(now_ticks=ft.now)
    assert app._bar_retract_start_height == revealed_height
    assert (
        "fill_rect",
        0,
        display.height - revealed_height,
        display.width,
        revealed_height,
        config.COLOR_BAR_PANEL,
    ) in display.ops


def test_bar_gear_edge_enters_settings_without_rotation_dwell_rearm():
    ft = FakeTicks(0)
    # The named 48px gear target is centered at (160, 222) on FakeDisplayPort.
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.step(now_ticks=ft.now)
    old_deadline = app.state.view_deadline
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_SETTINGS
    assert app.state.surface_deadline == ft.ticks_add(ft.now, config.TOUCH_IDLE_TIMEOUT_MS)
    assert app.state.view_deadline == old_deadline
    assert app._bar_retract_started == ft.now


def _enter_settings_via_gear(app, ft):
    app.boot()
    app.step(now_ticks=ft.now)
    ft.advance(1)
    app.step(now_ticks=ft.now)


def test_bar_gear_entering_settings_captures_network_status_snapshot():
    from src.device.network.models import setup_ap_status_event

    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app._network_events = [setup_ap_status_event()]
    _enter_settings_via_gear(app, ft)

    assert app.state.active_surface == SURFACE_SETTINGS
    assert app.state.settings_status_snapshot == {
        "kind": "setup",
        "ssid": config.SETUP_AP_SSID,
        "ip": config.SETUP_AP_GATEWAY,
    }


def test_settings_entry_with_no_network_status_leaves_none_snapshot():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    _enter_settings_via_gear(app, ft)

    assert app.state.settings_status_snapshot is None


def test_settings_snapshot_is_not_refreshed_while_open():
    from src.device.network.models import setup_ap_status_event

    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app._network_events = [setup_ap_status_event()]
    _enter_settings_via_gear(app, ft)
    captured = app.state.settings_status_snapshot

    app._overlay_kind = "station_ip"
    app._overlay_ssid = "Changed"
    app._overlay_ip = "10.0.0.99"
    ft.advance(config.CLOCK_REDRAW_MS)
    app.step(now_ticks=ft.now)

    assert app.state.settings_status_snapshot == captured
    assert app.state.settings_status_snapshot["kind"] == "setup"


def test_settings_reentry_overwrites_snapshot_from_current_network_state():
    from src.device.network.models import setup_ap_status_event

    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app._network_events = [setup_ap_status_event()]
    _enter_settings_via_gear(app, ft)
    assert app.state.settings_status_snapshot["kind"] == "setup"

    app.state.active_surface = SURFACE_BAR
    app._overlay_kind = "station_ip"
    app._overlay_ssid = "Home"
    app._overlay_ip = "192.168.1.50"
    app._touch_port = FakeTouchPort([(True, 160, 222)])
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert app.state.settings_status_snapshot == {
        "kind": "station_ip",
        "ssid": "Home",
        "ip": "192.168.1.50",
    }


def test_settings_render_suspends_calendar_and_hides_bar():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.state.active_view = VIEW_CALENDAR
    app.step(now_ticks=ft.now)
    ft.advance(1)
    app.step(now_ticks=ft.now)
    assert app.state.active_surface == SURFACE_SETTINGS
    display.clear_ops()
    ft.advance(config.CLOCK_REDRAW_MS)
    app.step(now_ticks=ft.now)

    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "14:00" not in texts
    assert config.BADGE_TEXT not in texts
    calendar_fills = [
        op
        for op in display.ops
        if op[0] == "fill_rect" and op[5] == config.COLOR_PRIMARY
    ]
    assert not calendar_fills


def test_settings_render_suspends_clock_and_hides_bar():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    _enter_settings_via_gear(app, ft)
    display.clear_ops()
    ft.advance(config.CLOCK_REDRAW_MS)
    app.step(now_ticks=ft.now)

    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "14:00" not in texts
    assert config.BADGE_TEXT not in texts
    bx, by, bw, bh = (
        0,
        display.height - config.BAR_HEIGHT_PX,
        display.width,
        config.BAR_HEIGHT_PX,
    )
    assert ("fill_rect", bx, by, bw, bh, config.COLOR_BAR_PANEL) not in display.ops
    # Settings content is static while open (captured once on entry), so a
    # later redraw tick with nothing changed repaints nothing at all.
    assert display.ops == []


def test_settings_reboot_tap_flashes_then_resets_once():
    from src.ui.components import settings_reboot_item_rect

    ft = FakeTicks(0)
    display = FakeDisplayPort()
    reboot_x, reboot_y = _settings_reboot_center(display)
    touch = FakeTouchPort(
        [(True, 0, 0), (True, 160, 222), (True, reboot_x, reboot_y)]
    )
    events = []
    sleep = RecordingSleepMs(events)
    reboot = FakeRebootPort(events, sleep=sleep)
    app, _clock, _view, display, ft, _logs, _cal = _make_app(
        ticks_mod=ft,
        touch_port=touch,
        reboot_port=reboot,
        sleep_ms_fn=sleep,
    )
    _enter_settings_via_gear(app, ft)
    item_x, item_y, item_w, item_h = settings_reboot_item_rect(display)
    display.clear_ops()
    ft.advance(1)
    app.step(now_ticks=ft.now)

    flash = (
        "fill_rect",
        item_x,
        item_y,
        item_w,
        item_h,
        config.COLOR_PRESS_FLASH,
    )
    assert flash in display.ops
    assert sleep.calls == [config.PRESS_FLASH_MS]
    assert reboot.reset_count == 1
    assert events == ["sleep", "reset"]


def test_settings_reboot_miss_dismisses_without_reset():
    ft = FakeTicks(0)
    display = FakeDisplayPort()
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222), (True, 10, 10)])
    reboot = FakeRebootPort()
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch, reboot_port=reboot
    )
    _enter_settings_via_gear(app, ft)
    old_view_deadline = app.state.view_deadline
    display.clear_ops()
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert reboot.reset_count == 0
    assert app.state.active_surface == SURFACE_ROTATION
    assert app.state.surface_deadline is None
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CLOCK_DWELL_MS)
    assert app.state.view_deadline != old_view_deadline
    assert not any(
        op[0] == "fill_rect" and op[5] == config.COLOR_PRESS_FLASH
        for op in display.ops
    )


def test_settings_reboot_none_port_still_flashes_without_exception():
    from src.ui.components import settings_reboot_item_rect

    ft = FakeTicks(0)
    display = FakeDisplayPort()
    reboot_x, reboot_y = _settings_reboot_center(display)
    touch = FakeTouchPort(
        [(True, 0, 0), (True, 160, 222), (True, reboot_x, reboot_y)]
    )
    sleep = RecordingSleepMs()
    app, _clock, _view, display, ft, _logs, _cal = _make_app(
        ticks_mod=ft,
        touch_port=touch,
        reboot_port=None,
        sleep_ms_fn=sleep,
    )
    _enter_settings_via_gear(app, ft)
    item_x, item_y, item_w, item_h = settings_reboot_item_rect(display)
    display.clear_ops()
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert (
        "fill_rect",
        item_x,
        item_y,
        item_w,
        item_h,
        config.COLOR_PRESS_FLASH,
    ) in display.ops
    assert sleep.calls == [config.PRESS_FLASH_MS]


def test_settings_idle_timeout_returns_to_rotation_and_rearms_clock_dwell():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    _enter_settings_via_gear(app, ft)
    ft.advance(config.TOUCH_IDLE_TIMEOUT_MS)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_ROTATION
    assert app.state.surface_deadline is None
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CLOCK_DWELL_MS)


def test_settings_outside_tap_returns_to_rotation_and_rearms_calendar_dwell():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222), (True, 10, 10)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.state.active_view = VIEW_CALENDAR
    app.step(now_ticks=ft.now)
    ft.advance(1)
    app.step(now_ticks=ft.now)
    assert app.state.active_surface == SURFACE_SETTINGS

    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_ROTATION
    assert app.state.surface_deadline is None
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CALENDAR_DWELL_MS)


def test_settings_malformed_edge_stays_on_settings_without_error():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222), (True,)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    _enter_settings_via_gear(app, ft)
    deadline = app.state.surface_deadline
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_SETTINGS
    assert app.state.surface_deadline == deadline


def test_settings_idle_timeout_rearms_calendar_dwell():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.state.active_view = VIEW_CALENDAR
    app.step(now_ticks=ft.now)
    ft.advance(1)
    app.step(now_ticks=ft.now)
    ft.advance(config.TOUCH_IDLE_TIMEOUT_MS)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_ROTATION
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CALENDAR_DWELL_MS)


def test_settings_outside_tap_clears_bar_retract_state():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222), (True, 10, 10)])
    app, _clock, _view, display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    _enter_settings_via_gear(app, ft)
    assert app._bar_retract_started is not None
    display.clear_ops()
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_ROTATION
    assert app._bar_retract_started is None
    assert app._bar_visible_height == 0
    assert not any(op[-1] == config.COLOR_BAR_PANEL for op in display.ops)


def test_settings_reboot_tap_preserves_settings_surface():
    ft = FakeTicks(0)
    display = FakeDisplayPort()
    reboot_x, reboot_y = _settings_reboot_center(display)
    touch = FakeTouchPort(
        [(True, 0, 0), (True, 160, 222), (True, reboot_x, reboot_y)]
    )
    reboot = FakeRebootPort()
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft,
        touch_port=touch,
        reboot_port=reboot,
        sleep_ms_fn=RecordingSleepMs(),
    )
    _enter_settings_via_gear(app, ft)
    armed_deadline = app.state.surface_deadline
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_SETTINGS
    assert app.state.surface_deadline == armed_deadline


def test_settings_reboot_tap_wins_when_idle_deadline_is_due():
    ft = FakeTicks(0)
    display = FakeDisplayPort()
    reboot_x, reboot_y = _settings_reboot_center(display)
    touch = FakeTouchPort(
        [(True, 0, 0), (True, 160, 222), (True, reboot_x, reboot_y)]
    )
    reboot = FakeRebootPort()
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft,
        touch_port=touch,
        reboot_port=reboot,
        sleep_ms_fn=RecordingSleepMs(),
    )
    _enter_settings_via_gear(app, ft)
    ft.advance(config.TOUCH_IDLE_TIMEOUT_MS)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_SETTINGS
    assert reboot.reset_count == 1


def test_settings_retains_the_interrupted_view_after_its_dwell_is_due():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True, 160, 222)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.step(now_ticks=ft.now)
    ft.advance(1)
    app.step(now_ticks=ft.now)
    assert app.state.active_surface == SURFACE_SETTINGS

    app.state.view_deadline = ft.now
    app.step(now_ticks=ft.now)
    assert app.state.active_surface == SURFACE_SETTINGS
    assert app.state.active_view == VIEW_CLOCK


def test_reverse_frames_shrink_across_tick_wrap_and_finish_cleanly():
    ft = FakeTicks(ticks.PERIOD - 100)
    touch = FakeTouchPort([(True, 0, 0), (False, None, None), (True, 0, 0)])
    app, _clock, _view, display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.step(now_ticks=ft.now)
    ft.advance(config.BAR_SLIDE_DURATION_MS)
    app.step(now_ticks=ft.now)
    assert app._bar_visible_height == config.BAR_HEIGHT_PX

    # Begin reverse just before wrap, then prove the next animation frame is
    # tick-safe and strictly shorter than the fully revealed Bar.
    ft.now = ticks.PERIOD - 10
    app.state.surface_deadline = ft.ticks_add(ft.now, config.TOUCH_IDLE_TIMEOUT_MS)
    app.step(now_ticks=ft.now)
    assert app._bar_retract_started == ft.now
    assert app.state.redraw_deadline == ft.ticks_add(ft.now, config.BAR_ANIMATION_FRAME_MS)

    display.clear_ops()
    ft.advance(config.BAR_ANIMATION_FRAME_MS)
    app.step(now_ticks=ft.now)
    expected_height = config.BAR_HEIGHT_PX - (
        config.BAR_HEIGHT_PX * config.BAR_ANIMATION_FRAME_MS
    ) // config.BAR_SLIDE_DURATION_MS
    assert (
        "fill_rect",
        0,
        display.height - expected_height,
        display.width,
        expected_height,
        config.COLOR_BAR_PANEL,
    ) in display.ops

    display.clear_ops()
    ft.advance(config.BAR_SLIDE_DURATION_MS - config.BAR_ANIMATION_FRAME_MS)
    app.step(now_ticks=ft.now)
    assert app._bar_retract_started is None
    assert app._bar_visible_height == 0
    assert not any(op[-1] == config.COLOR_BAR_PANEL for op in display.ops)


def test_bar_malformed_edge_stays_on_bar_without_error():
    ft = FakeTicks(0)
    touch = FakeTouchPort([(True, 0, 0), (True,)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.step(now_ticks=ft.now)
    deadline = app.state.surface_deadline
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_BAR
    assert app.state.surface_deadline == deadline


def test_bar_in_panel_non_gear_edge_keeps_bar_revealed():
    ft = FakeTicks(0)
    # Inside the 36px bottom strip, left of the centered 48px gear target.
    touch = FakeTouchPort([(True, 0, 0), (True, 10, 220)])
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(
        ticks_mod=ft, touch_port=touch
    )
    app.boot()
    app.step(now_ticks=ft.now)
    deadline = app.state.surface_deadline
    ft.advance(1)
    app.step(now_ticks=ft.now)

    assert app.state.active_surface == SURFACE_BAR
    assert app.state.surface_deadline == deadline


def test_missing_touch_port_preserves_rotation_and_view_dwell():
    ft = FakeTicks(0)
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(ticks_mod=ft)
    app.boot()
    app.state.view_deadline = 0
    app.step(now_ticks=ft.now)
    assert app.state.active_surface == SURFACE_ROTATION
    assert app.state.active_view == VIEW_CALENDAR


def test_app_and_ticks_import_under_cpython():
    from src import app, ticks as ticks_mod
    from src.time import service
    from src.ui import view_state

    assert callable(app.App)
    assert callable(ticks_mod.ticks_ms)
    assert callable(service.make_snapshot)
    assert view_state.VIEW_CALENDAR == VIEW_CALENDAR
    assert "machine" not in sys.modules


def test_app_and_ticks_modules_are_pure():
    for path in PURE_APP_MODULES:
        roots = _imported_roots(path)
        forbidden = roots & FORBIDDEN_IMPORT_ROOTS
        assert not forbidden, f"{path.name} imports forbidden: {forbidden}"


def test_app_boot_active_view_is_clock_and_owns_state():
    app, _clock, view, _display, _ft, _logs, _cal = _make_app()
    app.boot()
    assert app.state.active_view == VIEW_CLOCK
    assert isinstance(app.state, AppState)
    assert app.state.trust == TRUST_UNSYNCED
    assert app.state.active_surface == "rotation"
    assert app.state.surface_deadline is None
    assert app.state.settings_status_snapshot is None
    assert not hasattr(view, "state")
    assert not hasattr(view, "trust")


def test_renderer_cannot_mutate_app_trust_or_view():
    app, _clock, view, _display, ft, _logs, _cal = _make_app()
    app.boot()
    app.step(now_ticks=ft.now)
    trust_before = app.state.trust
    view_before = app.state.active_view
    view._cache["valid"] = False
    app._compositor._prev_badge = True
    assert app.state.trust == trust_before
    assert app.state.active_view == view_before


def test_valid_rtc_refreshes_clock_at_least_once_per_second():
    ft = FakeTicks(0)
    app, clock, _view, display, ft, _logs, _cal = _make_app(
        utc=_utc(7, 0, 0), ticks_mod=ft
    )
    app.boot()
    app.step(now_ticks=0)
    assert clock.read_count == 1
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "14:00" in texts  # UTC+7
    assert "00" in texts

    display.clear_ops()
    clock.advance_second()
    ft.advance(config.CLOCK_REDRAW_MS)
    app.step(now_ticks=ft.now)
    assert clock.read_count == 2
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "01" in texts


def test_cold_rtc_renders_placeholder_and_badge_without_crash():
    ft = FakeTicks(0)
    app, clock, _view, display, ft, _logs, _cal = _make_app(utc=None, ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    assert clock.read_count == 1
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert config.CLOCK_PLACEHOLDER_HHMM in texts
    assert config.BADGE_TEXT in texts
    assert app.state.trust == TRUST_UNSYNCED


def test_time_source_failure_marks_unsynced_keeps_valid_rtc_and_logs():
    ft = FakeTicks(0)
    app, clock, _view, display, ft, logs, _cal = _make_app(
        utc=_utc(8, 30, 15), ticks_mod=ft
    )
    app.boot()
    app.state.trust = TRUST_SYNCED
    app.report_time_source_failure("ntp unreachable")
    assert app.state.trust == TRUST_UNSYNCED
    assert logs and "ntp unreachable" in logs[-1]

    app.step(now_ticks=0)
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "15:30" in texts
    assert "15" in texts
    assert config.BADGE_TEXT in texts
    ft.advance(config.CLOCK_REDRAW_MS)
    clock.advance_second()
    app.step(now_ticks=ft.now)
    assert clock.read_count == 2


def test_invalid_credentials_soft_fail_same_as_sync_failure():
    ft = FakeTicks(0)
    app, _clock, _view, _display, ft, logs, _cal = _make_app(
        utc=_utc(), ticks_mod=ft
    )
    app.boot()
    app.report_time_source_failure("missing or empty Wi-Fi credentials")
    assert app.state.trust == TRUST_UNSYNCED
    assert any("credentials" in line for line in logs)
    app.step(now_ticks=0)


def test_deadlines_use_ticks_helpers_not_wall_clock():
    ft = FakeTicks(50_000)
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(ticks_mod=ft)
    app.boot()
    assert app.state.redraw_deadline == 50_000
    assert app.state.retry_deadline == 50_000  # due immediately for first sync
    assert app.state.freshness_deadline == ft.ticks_add(50_000, config.NTP_RETRY_MS)
    assert app.state.view_deadline == ft.ticks_add(50_000, config.CLOCK_DWELL_MS)

    app.step(now_ticks=50_000)
    assert app.state.redraw_deadline == ft.ticks_add(50_000, config.CLOCK_REDRAW_MS)
    # No mailbox: sync skip arms full NTP_RETRY_MS.
    assert app.state.retry_deadline == ft.ticks_add(50_000, config.NTP_RETRY_MS)

    # Valid local: Clock dwell → Calendar, armed with CALENDAR_DWELL_MS.
    ft.advance(config.CLOCK_DWELL_MS)
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CALENDAR
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CALENDAR_DWELL_MS)

    # Calendar dwell → Clock, armed with CLOCK_DWELL_MS.
    ft.advance(config.CALENDAR_DWELL_MS)
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CLOCK
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CLOCK_DWELL_MS)

    # Advance past NTP retry — retry and freshness re-armed via ticks_add.
    ft.advance(config.NTP_RETRY_MS)
    app.step(now_ticks=ft.now)
    assert app.state.retry_deadline == ft.ticks_add(ft.now, config.NTP_RETRY_MS)
    assert app.state.freshness_deadline == ft.ticks_add(ft.now, config.NTP_RETRY_MS)

    wrap_now = ticks.PERIOD - 100
    ft.now = wrap_now
    app.state.active_view = VIEW_CLOCK
    app.state.redraw_deadline = wrap_now
    app.state.retry_deadline = wrap_now
    app.state.freshness_deadline = wrap_now
    app.state.view_deadline = wrap_now
    app.step(now_ticks=wrap_now)
    assert app.state.redraw_deadline == ft.ticks_add(wrap_now, config.CLOCK_REDRAW_MS)
    assert app.state.retry_deadline == ft.ticks_add(wrap_now, config.NTP_RETRY_MS)
    assert app.state.freshness_deadline == ft.ticks_add(wrap_now, config.NTP_RETRY_MS)
    # Wrap-safe Clock→Calendar arm uses ticks_add only.
    assert app.state.active_view == VIEW_CALENDAR
    assert app.state.view_deadline == ft.ticks_add(wrap_now, config.CALENDAR_DWELL_MS)
    assert app.state.redraw_deadline == (wrap_now + config.CLOCK_REDRAW_MS) % ticks.PERIOD


def test_clock_calendar_rotation_with_valid_local():
    ft = FakeTicks(0)
    app, _clock, _view, display, ft, _logs, _cal = _make_app(ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    assert app.state.active_view == VIEW_CLOCK

    ft.advance(config.CLOCK_DWELL_MS)
    display.clear_ops()
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CALENDAR
    assert app._month_grid is not None
    assert app._month_grid.year == 2026
    assert app._month_grid.month == 9
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "SEPTEMBER 2026" in texts

    ft.advance(config.CALENDAR_DWELL_MS)
    display.clear_ops()
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CLOCK
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "14:00" in texts


def test_invalid_local_does_not_enter_calendar():
    ft = FakeTicks(0)
    app, _clock, _view, _display, ft, _logs, _cal = _make_app(utc=None, ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    ft.advance(config.CLOCK_DWELL_MS)
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CLOCK
    assert app._month_grid is None
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CLOCK_DWELL_MS)


def test_same_month_midnight_refreshes_today_on_calendar():
    # 2026-09-06 16:59:59 UTC → local 23:59:59; +1s → 2026-09-07 local.
    ft = FakeTicks(0)
    utc = DateTime(2026, 9, 6, 6, 16, 59, 59)
    app, clock, _view, _display, ft, _logs, _cal = _make_app(utc=utc, ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    # Force Calendar entry.
    app.state.view_deadline = 0
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CALENDAR
    grid_before = app._month_grid
    assert any(c.is_today and c.day == 6 for week in grid_before.weeks for c in week)

    clock.set_utc(DateTime(2026, 9, 6, 6, 17, 0, 0))
    ft.advance(config.CLOCK_REDRAW_MS)
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CALENDAR
    grid_after = app._month_grid
    assert grid_after is not grid_before
    assert any(c.is_today and c.day == 7 for week in grid_after.weeks for c in week)
    assert not any(c.is_today and c.day == 6 for week in grid_after.weeks for c in week)


def test_same_month_midnight_updates_clock_date_via_force_redraw():
    # Stay on Clock; cross local midnight while redraw_deadline is still ahead so
    # only force_redraw (not the 1 Hz cadence) can paint the new date line.
    ft = FakeTicks(0)
    utc = DateTime(2026, 9, 6, 6, 16, 59, 59)
    app, clock, _view, display, ft, _logs, _cal = _make_app(utc=utc, ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    assert app.state.active_view == VIEW_CLOCK
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "Sun · Sep 6 2026" in texts

    clock.set_utc(DateTime(2026, 9, 6, 6, 17, 0, 0))
    redraw_deadline = app.state.redraw_deadline
    assert ft.ticks_diff(redraw_deadline, ft.now) > 0
    display.clear_ops()
    app.step(now_ticks=ft.now)  # same now — 1 Hz redraw not due
    assert app.state.active_view == VIEW_CLOCK
    assert ft.ticks_diff(redraw_deadline, ft.now) > 0
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "Mon · Sep 7 2026" in texts


def test_month_rollover_during_calendar_cuts_to_clock_defers_grid():
    # 2026-09-30 16:59:59 UTC → local 23:59:59; +1s → 2026-10-01 local.
    ft = FakeTicks(0)
    utc = DateTime(2026, 9, 30, 2, 16, 59, 59)
    app, clock, _view, _display, ft, _logs, _cal = _make_app(utc=utc, ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    app.state.view_deadline = 0
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CALENDAR
    assert app._month_grid.month == 9
    old_grid = app._month_grid

    clock.set_utc(DateTime(2026, 9, 30, 2, 17, 0, 0))
    ft.advance(config.CLOCK_REDRAW_MS)
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CLOCK
    assert app._month_grid is None
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CLOCK_DWELL_MS)

    # Next Calendar entry builds October — not a mid-dwell swap of old_grid.
    app.state.view_deadline = 0
    app.step(now_ticks=ft.now)
    assert app.state.active_view == VIEW_CALENDAR
    assert app._month_grid is not old_grid
    assert app._month_grid.year == 2026
    assert app._month_grid.month == 10


def test_app_source_uses_ticks_for_deadlines():
    """AST: App scheduling calls ticks_ms / ticks_add / ticks_diff."""
    src = (ROOT / "src" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                called.add(func.attr)
            elif isinstance(func, ast.Name):
                called.add(func.id)
    assert "ticks_ms" in called
    assert "ticks_add" in called
    assert "ticks_diff" in called
    # No wall-clock scheduling APIs invoked by name.
    assert "time" not in called
    assert "datetime" not in called
    assert "monotonic" not in called
