"""Host tests for App-owned network status overlays (story 1.3)."""

from pathlib import Path

from src import config
from src.app import VIEW_CALENDAR, App
from src.device.network.coordinator import NetworkCoordinator
from src.device.network.mailbox import Mailbox
from src.device.network.models import (
    MODE_STATION_CONNECTING,
    MODE_STATION_ONLINE,
    setup_ap_status_event,
    station_status_event,
)
from src.provisioning.verifier import derive_admin_verifier
from src.time.model import TRUST_UNSYNCED, DateTime
from src.ui.calendar_view import CalendarView
from src.ui.clock_view import ClockView
from src.ui.compositor import UiCompositor
from src.ui.display_port import FakeDisplayPort

from tests.test_app_loop import FakeClockPort, FakeTicks
from tests.test_network_coordinator import FakeWlan
from tests.test_setup_ap_coordinator import FakeApWlan
from tests.test_settings_store import FakeFS, _record_bytes, _store

ROOT = Path(__file__).resolve().parents[1]


def _app(events=None, ticks=None, display=None, sync_enabled=False):
    ticks = ticks if ticks is not None else FakeTicks(0)
    display = display if display is not None else FakeDisplayPort()
    utc = DateTime(2026, 9, 6, 6, 12, 0, 0)
    app = App(
        clock_port=FakeClockPort(utc),
        clock_view=ClockView(display),
        calendar_view=CalendarView(display),
        ticks_module=ticks,
        sync_enabled=sync_enabled,
        network_events=events if events is not None else [],
    )
    app.boot()
    return app, display, ticks


def _drawn_texts(display):
    return [op[1] for op in display.ops if op[0] == "draw_text"]


def _fills(ops):
    return [op for op in ops if op[0] == "fill_rect"]


def test_setup_status_shows_continuous_ssid_and_gateway():
    events = [setup_ap_status_event()]
    app, display, ticks = _app(events=events)
    app.step(now_ticks=ticks.now)
    texts = _drawn_texts(display)
    assert config.SETUP_AP_SSID in texts
    assert config.SETUP_AP_GATEWAY in texts
    assert app._sync_enabled is False
    # Still present after another second (no dwell timeout).
    display.clear_ops()
    ticks.advance(config.STATION_IP_DISPLAY_MS + 500)
    app.step(now_ticks=ticks.now)
    texts = _drawn_texts(display)
    assert config.SETUP_AP_SSID in texts
    assert config.SETUP_AP_GATEWAY in texts


def test_station_ip_overlay_shows_at_least_ten_seconds_then_clears():
    events = [
        station_status_event(
            mode=MODE_STATION_ONLINE, ssid="Home", ip="192.168.1.77"
        )
    ]
    app, display, ticks = _app(events=events)
    app.step(now_ticks=ticks.now)
    assert "192.168.1.77" in _drawn_texts(display)
    assert app._sync_enabled is True

    display.clear_ops()
    ticks.advance(config.STATION_IP_DISPLAY_MS - 1)
    app.step(now_ticks=ticks.now)
    assert "192.168.1.77" in _drawn_texts(display)

    display.clear_ops()
    ticks.advance(2)
    app.step(now_ticks=ticks.now)
    assert "192.168.1.77" not in _drawn_texts(display)


def test_station_online_without_ip_clears_prior_address():
    events = [
        station_status_event(
            mode=MODE_STATION_ONLINE, ssid="Home", ip="192.168.1.77"
        )
    ]
    app, display, ticks = _app(events=events)
    app.step(now_ticks=ticks.now)
    assert "192.168.1.77" in _drawn_texts(display)

    app._network_events.append(
        station_status_event(mode=MODE_STATION_ONLINE, ssid="Home", ip=None)
    )
    display.clear_ops()
    app.step(now_ticks=ticks.now)
    texts = _drawn_texts(display)
    assert "192.168.1.77" not in texts
    assert "192.168.4.1" not in texts
    assert not any(
        isinstance(t, str) and t.count(".") == 3 and t[0].isdigit()
        for t in texts
    )
    assert app._sync_enabled is True


def test_wrap_safe_ip_dwell_across_tick_period():
    """IP clear deadline uses ticks_add/diff so wrap does not clear early."""
    near_wrap = (FakeTicks.PERIOD - 500) & (FakeTicks.PERIOD - 1)
    events = [
        station_status_event(
            mode=MODE_STATION_ONLINE, ssid="Home", ip="10.0.0.2"
        )
    ]
    app, display, ticks = _app(events=events, ticks=FakeTicks(near_wrap))
    app.step(now_ticks=ticks.now)
    assert "10.0.0.2" in _drawn_texts(display)

    # Advance past wrap but still within the 10s dwell.
    ticks.advance(2_000)
    display.clear_ops()
    app.step(now_ticks=ticks.now)
    assert "10.0.0.2" in _drawn_texts(display)

    ticks.advance(config.STATION_IP_DISPLAY_MS)
    display.clear_ops()
    app.step(now_ticks=ticks.now)
    assert "10.0.0.2" not in _drawn_texts(display)


def test_setup_overlay_clears_when_station_comes_online():
    events = [setup_ap_status_event()]
    app, display, ticks = _app(events=events)
    app.step(now_ticks=ticks.now)
    assert config.SETUP_AP_SSID in _drawn_texts(display)
    assert app._sync_enabled is False

    app._network_events.append(
        station_status_event(
            mode=MODE_STATION_ONLINE, ssid="Home", ip="192.168.0.5"
        )
    )
    display.clear_ops()
    app.step(now_ticks=ticks.now)
    texts = _drawn_texts(display)
    assert config.SETUP_AP_SSID not in texts
    assert "192.168.0.5" in texts
    assert app.state.trust == TRUST_UNSYNCED
    assert app._sync_enabled is True


def test_overlays_draw_on_calendar_active_view():
    events = [setup_ap_status_event()]
    app, display, ticks = _app(events=events)
    app.state.active_view = VIEW_CALENDAR
    app._month_grid = None
    app.step(now_ticks=ticks.now)
    texts = _drawn_texts(display)
    assert config.SETUP_AP_SSID in texts
    assert config.SETUP_AP_GATEWAY in texts

    app._network_events.append(
        station_status_event(
            mode=MODE_STATION_ONLINE, ssid="Home", ip="10.1.2.3"
        )
    )
    display.clear_ops()
    app.step(now_ticks=ticks.now)
    assert app.state.active_view == VIEW_CALENDAR
    texts = _drawn_texts(display)
    assert "10.1.2.3" in texts
    assert config.SETUP_AP_SSID not in texts


def test_network_key_clear_invalidates_base_full_redraw():
    """Clearing station IP forces base invalidate (same as badge hide)."""
    display = FakeDisplayPort()
    view = ClockView(display)
    compositor = UiCompositor(display)
    utc = DateTime(2026, 9, 6, 6, 12, 0, 0)
    from src.time.service import make_snapshot

    snap = make_snapshot(utc, TRUST_UNSYNCED, None)
    status = {"kind": "station_ip", "ssid": "Home", "ip": "192.168.1.9"}
    compositor.render(view, snap, status=status)
    assert "192.168.1.9" in _drawn_texts(display)

    display.clear_ops()
    compositor.render(view, snap, status=None)
    fills = _fills(display.ops)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )
    assert "192.168.1.9" not in _drawn_texts(display)


def test_shared_events_composition_coordinator_to_app_overlay():
    """Shared list: coordinator emit → App.step → drawn overlay; sync gates."""
    salt, verifier = derive_admin_verifier("admin", salt=b"\x22" * 16)
    store = _store(
        FakeFS(
            {
                ".settings-v1": _record_bytes(
                    admin_salt=salt,
                    admin_verifier=verifier,
                    wifi_ssid="HomeNet",
                    wifi_password="password1",
                )
            }
        )
    )
    assert store.is_configured() is True

    events = []
    ticks = FakeTicks()
    wlan = FakeWlan(True, ip="192.168.1.88")
    coordinator = NetworkCoordinator(
        Mailbox(),
        wlan=wlan,
        ap_wlan=FakeApWlan(),
        settings_store=store,
        event_sink=events,
        ticks_module=ticks,
    )
    assert coordinator.mode == MODE_STATION_CONNECTING

    # main.py rule: connecting → sync off; store-configured OR secrets later.
    app, display, ticks = _app(events=events, ticks=ticks, sync_enabled=False)
    assert app._sync_enabled is False

    coordinator.tick()  # begin / emit connecting
    coordinator.tick()  # already connected → online+IP
    assert any(
        e.kind == "station_status" and e.mode == MODE_STATION_ONLINE and e.ip
        for e in events
    )

    app.step(now_ticks=ticks.now)
    assert "192.168.1.88" in _drawn_texts(display)
    assert app._sync_enabled is True

    main_source = (ROOT / "main.py").read_text()
    assert "network_events=network_events" in main_source
    assert "MODE_STATION_CONNECTING" in main_source
    assert "settings_store.is_configured()" in main_source
    assert "credentials_valid()" in main_source
