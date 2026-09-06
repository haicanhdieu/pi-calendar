"""Host tests for App loop, ClockPort fakes, and pure-module boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from src import config
from src import ticks
from src.app import VIEW_CLOCK, App, AppState
from src.time.model import TRUST_SYNCED, TRUST_UNSYNCED, DateTime
from src.ui.clock_view import ClockView
from src.ui.display_port import FakeDisplayPort

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"machine", "network", "ntptime", "src.device"}
)
PURE_APP_MODULES = (
    ROOT / "src" / "app.py",
    ROOT / "src" / "ticks.py",
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


def _utc(hour=7, minute=0, second=0):
    # 2026-09-06 Sunday(=6) 07:00 UTC → 14:00 local
    return DateTime(2026, 9, 6, 6, hour, minute, second)


def _make_app(utc=_utc(), ticks_mod=None):
    display = FakeDisplayPort()
    view = ClockView(display)
    clock = FakeClockPort(utc)
    ft = ticks_mod if ticks_mod is not None else FakeTicks(0)
    logs = []
    app = App(
        clock_port=clock,
        clock_view=view,
        ticks_module=ft,
        log=logs.append,
    )
    return app, clock, view, display, ft, logs


def test_app_and_ticks_import_under_cpython():
    from src import app, ticks as ticks_mod
    from src.time import service

    assert callable(app.App)
    assert callable(ticks_mod.ticks_ms)
    assert callable(service.make_snapshot)
    assert "machine" not in sys.modules


def test_app_and_ticks_modules_are_pure():
    for path in PURE_APP_MODULES:
        roots = _imported_roots(path)
        forbidden = roots & FORBIDDEN_IMPORT_ROOTS
        assert not forbidden, f"{path.name} imports forbidden: {forbidden}"


def test_app_boot_active_view_is_clock_and_owns_state():
    app, _clock, view, _display, _ft, _logs = _make_app()
    app.boot()
    assert app.state.active_view == VIEW_CLOCK
    assert isinstance(app.state, AppState)
    assert app.state.trust == TRUST_UNSYNCED
    assert not hasattr(view, "state")
    assert not hasattr(view, "trust")


def test_renderer_cannot_mutate_app_trust_or_view():
    app, _clock, view, _display, ft, _logs = _make_app()
    app.boot()
    app.step(now_ticks=ft.now)
    trust_before = app.state.trust
    view_before = app.state.active_view
    view._cache["badge"] = True
    view._cache["valid"] = False
    assert app.state.trust == trust_before
    assert app.state.active_view == view_before


def test_valid_rtc_refreshes_clock_at_least_once_per_second():
    ft = FakeTicks(0)
    app, clock, _view, display, ft, _logs = _make_app(utc=_utc(7, 0, 0), ticks_mod=ft)
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
    app, clock, _view, display, ft, _logs = _make_app(utc=None, ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    assert clock.read_count == 1
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert config.CLOCK_PLACEHOLDER_HHMM in texts
    assert config.BADGE_TEXT in texts
    assert app.state.trust == TRUST_UNSYNCED


def test_time_source_failure_marks_unsynced_keeps_valid_rtc_and_logs():
    ft = FakeTicks(0)
    app, clock, _view, display, ft, logs = _make_app(utc=_utc(8, 30, 15), ticks_mod=ft)
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
    app, _clock, _view, _display, ft, logs = _make_app(utc=_utc(), ticks_mod=ft)
    app.boot()
    app.report_time_source_failure("missing or empty Wi-Fi credentials")
    assert app.state.trust == TRUST_UNSYNCED
    assert any("credentials" in line for line in logs)
    app.step(now_ticks=0)


def test_deadlines_use_ticks_helpers_not_wall_clock():
    ft = FakeTicks(50_000)
    app, _clock, _view, _display, ft, _logs = _make_app(ticks_mod=ft)
    app.boot()
    assert app.state.redraw_deadline == 50_000
    assert app.state.retry_deadline == ft.ticks_add(50_000, config.NTP_RETRY_MS)
    assert app.state.freshness_deadline == ft.ticks_add(50_000, config.NTP_RETRY_MS)
    assert app.state.view_deadline == ft.ticks_add(50_000, config.CLOCK_DWELL_MS)

    app.step(now_ticks=50_000)
    assert app.state.redraw_deadline == ft.ticks_add(50_000, config.CLOCK_REDRAW_MS)

    # Advance past view dwell — view deadline re-armed via ticks_add.
    ft.advance(config.CLOCK_DWELL_MS)
    app.step(now_ticks=ft.now)
    assert app.state.view_deadline == ft.ticks_add(ft.now, config.CLOCK_DWELL_MS)
    assert app.state.active_view == VIEW_CLOCK

    # Advance past NTP retry — retry and freshness re-armed via ticks_add.
    ft.advance(config.NTP_RETRY_MS)
    app.step(now_ticks=ft.now)
    assert app.state.retry_deadline == ft.ticks_add(ft.now, config.NTP_RETRY_MS)
    assert app.state.freshness_deadline == ft.ticks_add(ft.now, config.NTP_RETRY_MS)

    wrap_now = ticks.PERIOD - 100
    ft.now = wrap_now
    app.state.redraw_deadline = wrap_now
    app.state.retry_deadline = wrap_now
    app.state.freshness_deadline = wrap_now
    app.state.view_deadline = wrap_now
    app.step(now_ticks=wrap_now)
    assert app.state.redraw_deadline == ft.ticks_add(wrap_now, config.CLOCK_REDRAW_MS)
    assert app.state.retry_deadline == ft.ticks_add(wrap_now, config.NTP_RETRY_MS)
    assert app.state.freshness_deadline == ft.ticks_add(wrap_now, config.NTP_RETRY_MS)
    assert app.state.view_deadline == ft.ticks_add(wrap_now, config.CLOCK_DWELL_MS)
    assert app.state.redraw_deadline == (wrap_now + config.CLOCK_REDRAW_MS) % ticks.PERIOD


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
