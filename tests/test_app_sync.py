"""Host tests for App↔mailbox sync wiring (Story 1.5 / AD-8)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from src import config
from src.app import App
from src.device.network.mailbox import Mailbox, MailboxSaturationError, SyncResult
from src.time.model import TRUST_SYNCED, TRUST_UNSYNCED, DateTime
from src.ui.calendar_view import CalendarView
from src.ui.clock_view import ClockView
from src.ui.display_port import FakeDisplayPort

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "src" / "app.py"
NTP_OPS_PATH = ROOT / "src" / "device" / "network" / "ntp_ops.py"
FORBIDDEN_APP_IMPORT_ROOTS = frozenset(
    {"machine", "network", "ntptime", "src.device", "_thread"}
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
    def __init__(self, utc=None):
        self._utc = utc
        self.set_calls = []

    def read_utc(self):
        return self._utc

    def set_utc(self, dt):
        self.set_calls.append(dt)
        self._utc = dt


class FakeLock:
    def __init__(self):
        self.acquire_count = 0
        self.release_count = 0

    def acquire(self):
        self.acquire_count += 1
        return True

    def release(self):
        self.release_count += 1


class _Cmd:
    def __init__(self, command_id, deadline_ms):
        self.command_id = command_id
        self.deadline_ms = deadline_ms


def _utc(hour=12, minute=0, second=0):
    return DateTime(2026, 9, 6, 6, hour, minute, second)


def _make_sync_app(utc=None, ticks_mod=None, sync_enabled=True):
    display = FakeDisplayPort()
    view = ClockView(display)
    calendar = CalendarView(display)
    clock = FakeClockPort(utc)
    ft = ticks_mod if ticks_mod is not None else FakeTicks(0)
    logs = []
    mailbox = Mailbox()
    lock = FakeLock()
    app = App(
        clock_port=clock,
        clock_view=view,
        calendar_view=calendar,
        ticks_module=ft,
        log=logs.append,
        mailbox=mailbox,
        lock=lock,
        sync_enabled=sync_enabled,
    )
    return app, clock, mailbox, lock, ft, logs


def test_app_module_stays_pure():
    roots = _imported_roots(APP_PATH)
    forbidden = roots & FORBIDDEN_APP_IMPORT_ROOTS
    assert not forbidden, f"app.py imports forbidden: {forbidden}"


def test_ntp_ops_never_calls_settime():
    src = NTP_OPS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(NTP_OPS_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "settime":
                raise AssertionError("ntp_ops.py must not call settime")
            if isinstance(func, ast.Name) and func.id == "settime":
                raise AssertionError("ntp_ops.py must not call settime")
    # Import graph must not pull the bundled settime helper for side effects.
    assert "import ntptime" not in src
    assert "from ntptime" not in src


def test_boot_retry_due_immediately_enqueues_when_idle():
    ft = FakeTicks(1000)
    app, _clock, mailbox, lock, ft, _logs = _make_sync_app(ticks_mod=ft)
    app.boot()
    assert app.state.retry_deadline == 1000
    app.step(now_ticks=1000)
    assert mailbox.has_command
    assert not mailbox.idle
    assert app._inflight_id == 1
    assert app._inflight_deadline == ft.ticks_add(1000, config.SYNC_COMMAND_DEADLINE_MS)
    assert app.state.retry_deadline == ft.ticks_add(1000, config.NTP_RETRY_MS)
    assert lock.acquire_count >= 1
    assert lock.release_count == lock.acquire_count


def test_enqueue_rejected_while_busy_leaves_retry_due():
    ft = FakeTicks(0)
    app, _clock, mailbox, _lock, ft, _logs = _make_sync_app(ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    first = mailbox.try_take_command()
    assert first is not None
    assert not mailbox.idle
    app.state.retry_deadline = 0
    app.step(now_ticks=0)
    assert not mailbox.has_command
    assert app.state.retry_deadline == 0


def test_consume_success_sets_utc_and_synced():
    ft = FakeTicks(0)
    app, clock, mailbox, _lock, ft, _logs = _make_sync_app(ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    taken = mailbox.try_take_command()
    command, epoch = taken
    utc = _utc(15, 30, 0)
    mailbox.publish_result(SyncResult(command.command_id, True, utc, None), epoch)

    app.step(now_ticks=ft.now)
    assert clock.set_calls == [utc]
    assert clock.read_utc() == utc
    assert app.state.trust == TRUST_SYNCED
    assert app.state.utc_valid is True
    assert app.state.sync_age_ms == 0
    assert app._inflight_id is None
    assert app.state.retry_deadline == ft.ticks_add(ft.now, config.NTP_RETRY_MS)


def test_consume_failure_marks_unsynced_no_rtc_write():
    ft = FakeTicks(0)
    app, clock, mailbox, _lock, ft, logs = _make_sync_app(
        utc=_utc(8, 0, 0), ticks_mod=ft
    )
    app.boot()
    app.state.trust = TRUST_SYNCED
    app.step(now_ticks=0)
    taken = mailbox.try_take_command()
    command, epoch = taken
    mailbox.publish_result(
        SyncResult(command.command_id, False, None, "ntp_fail"),
        epoch,
    )
    app.step(now_ticks=ft.now)
    assert clock.set_calls == []
    assert app.state.trust == TRUST_UNSYNCED
    assert any("ntp_fail" in line for line in logs)
    assert app.state.retry_deadline == ft.ticks_add(ft.now, config.NTP_RETRY_MS)


def test_stale_id_mismatch_marks_unsynced_no_rtc_write():
    ft = FakeTicks(0)
    app, clock, mailbox, _lock, ft, logs = _make_sync_app(ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    taken = mailbox.try_take_command()
    _command, epoch = taken
    mailbox.publish_result(SyncResult(999, True, _utc(), None), epoch)
    app.step(now_ticks=ft.now)
    assert clock.set_calls == []
    assert app.state.trust == TRUST_UNSYNCED
    assert any("mismatch" in line for line in logs)


def test_expired_result_marks_unsynced_no_rtc_write():
    ft = FakeTicks(0)
    app, clock, mailbox, _lock, ft, logs = _make_sync_app(ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    taken = mailbox.try_take_command()
    command, epoch = taken
    ft.now = app._inflight_deadline
    mailbox.publish_result(SyncResult(command.command_id, True, _utc(), None), epoch)
    app.step(now_ticks=ft.now)
    assert clock.set_calls == []
    assert app.state.trust == TRUST_UNSYNCED
    assert any("expired" in line for line in logs)


def test_sync_disabled_skips_enqueue_and_arms_retry():
    ft = FakeTicks(0)
    app, _clock, mailbox, _lock, ft, _logs = _make_sync_app(
        ticks_mod=ft, sync_enabled=False
    )
    app.boot()
    app.step(now_ticks=0)
    assert not mailbox.has_command
    assert mailbox.idle
    assert app.state.retry_deadline == ft.ticks_add(0, config.NTP_RETRY_MS)


def test_retry_interval_after_terminal_consume_is_ntp_retry_ms():
    ft = FakeTicks(50)
    app, _clock, mailbox, _lock, ft, _logs = _make_sync_app(ticks_mod=ft)
    app.boot()
    app.step(now_ticks=50)
    taken = mailbox.try_take_command()
    command, epoch = taken
    mailbox.publish_result(
        SyncResult(command.command_id, False, None, "wifi_fail"),
        epoch,
    )
    app.step(now_ticks=50)
    assert app.state.retry_deadline == ft.ticks_add(50, config.NTP_RETRY_MS)
    assert config.NTP_RETRY_MS == 3_600_000


def test_saturation_preserves_prior_result():
    mailbox = Mailbox()
    mailbox.enqueue(_Cmd(1, 100))
    taken = mailbox.try_take_command()
    command, epoch = taken
    first = SyncResult(command.command_id, True, _utc(), None)
    mailbox.publish_result(first, epoch)
    prior = mailbox._result
    with pytest.raises(MailboxSaturationError):
        mailbox.publish_result(
            SyncResult(command.command_id, False, None, "overwrite"),
            epoch,
        )
    assert mailbox._result is prior


def test_result_slot_occupied_rejects_enqueue():
    """Capacity-one: unconsumed result blocks a new command (mailbox contract)."""
    mailbox = Mailbox()
    mailbox.occupy_result(SyncResult(1, False, None, "held"))
    assert mailbox.enqueue(_Cmd(2, 100)) is False
    assert mailbox.has_result
    # Consume then enqueue succeeds.
    assert mailbox.try_take_result() is not None
    assert mailbox.enqueue(_Cmd(2, 100)) is True


def test_app_occupied_result_rejects_enqueue_keeps_retry_due():
    """App enqueue path: occupied result → reject; retry_deadline stays due."""
    ft = FakeTicks(0)
    app, _clock, mailbox, _lock, ft, _logs = _make_sync_app(ticks_mod=ft)
    app.boot()
    app.step(now_ticks=0)
    taken = mailbox.try_take_command()
    command, epoch = taken
    mailbox.publish_result(
        SyncResult(command.command_id, False, None, "dns_fail"),
        epoch,
    )
    assert mailbox.has_result
    app.state.retry_deadline = 0
    # Consume would clear the slot; exercise enqueue while result still held.
    app._maybe_enqueue_sync(0)
    assert not mailbox.has_command
    assert mailbox.has_result
    assert app.state.retry_deadline == 0
    assert app._inflight_id == 1


def _connected_wlan():
    class FakeWlan:
        def active(self, value=None):
            if value is None:
                return True
            return True

        def isconnected(self):
            return True

        def connect(self, ssid, password):
            return None

    return FakeWlan()


class _Secrets:
    WIFI_SSID = "test"
    WIFI_PASSWORD = "secret"


def _ntp_payload(li=0, stratum=2, unix_seconds=1788696000):
    payload = bytearray(48)
    # LI (2) | VN=3 (3) | Mode=4 server (3)
    payload[0] = ((li & 0x03) << 6) | (3 << 3) | 4
    payload[1] = stratum & 0xFF
    ntp = int(unix_seconds) + 2208988800
    payload[40:44] = ntp.to_bytes(4, "big")
    return bytes(payload)


def _fake_socket(getaddrinfo=None, recv_data=None, recv_exc=None):
    class FakeSock:
        def __init__(self):
            self.timeout = None

        def settimeout(self, seconds):
            self.timeout = seconds

        def sendto(self, msg, addr):
            return len(msg)

        def recvfrom(self, _size):
            if recv_exc is not None:
                raise recv_exc
            return (recv_data, ("1.2.3.4", 123))

        def close(self):
            return None

    class FakeSocket:
        AF_INET = 2
        SOCK_DGRAM = 2

        def getaddrinfo(self, host, port):
            if getaddrinfo is not None:
                return getaddrinfo(host, port)
            return [(2, 2, 0, "", ("1.2.3.4", 123))]

        def socket(self, *_args, **_kwargs):
            return FakeSock()

    return FakeSocket()


def test_ntp_ops_unix_conversion_and_injectable_success():
    from src.device.network.ntp_ops import NtpOps
    from src.ticks import ticks_add, ticks_ms

    ops = NtpOps(
        wlan=_connected_wlan(),
        socket_module=_fake_socket(recv_data=_ntp_payload()),
        secrets_mod=_Secrets(),
    )
    result = ops.run(_Cmd(7, ticks_add(ticks_ms(), 60_000)))
    assert result.ok is True
    assert result.command_id == 7
    assert result.error_code is None
    assert result.utc == DateTime(2026, 9, 6, 6, 12, 0, 0)


def test_ntp_ops_wifi_fail_with_empty_secrets():
    from src.device.network.ntp_ops import NtpOps
    from src.ticks import ticks_add, ticks_ms

    class EmptySecrets:
        WIFI_SSID = ""
        WIFI_PASSWORD = ""

    result = NtpOps(secrets_mod=EmptySecrets()).run(
        _Cmd(3, ticks_add(ticks_ms(), 60_000))
    )
    assert result.ok is False
    assert result.error_code == "wifi_fail"
    assert result.utc is None


def test_ntp_ops_dns_fail():
    from src.device.network.ntp_ops import NtpOps
    from src.ticks import ticks_add, ticks_ms

    def boom(_host, _port):
        raise OSError("dns")

    ops = NtpOps(
        wlan=_connected_wlan(),
        socket_module=_fake_socket(getaddrinfo=boom),
        secrets_mod=_Secrets(),
    )
    result = ops.run(_Cmd(8, ticks_add(ticks_ms(), 60_000)))
    assert result.ok is False
    assert result.error_code == "dns_fail"
    assert result.utc is None


def test_ntp_ops_ntp_fail_on_recv_error():
    from src.device.network.ntp_ops import NtpOps
    from src.ticks import ticks_add, ticks_ms

    ops = NtpOps(
        wlan=_connected_wlan(),
        socket_module=_fake_socket(recv_exc=OSError("timeout")),
        secrets_mod=_Secrets(),
    )
    result = ops.run(_Cmd(9, ticks_add(ticks_ms(), 60_000)))
    assert result.ok is False
    assert result.error_code == "ntp_fail"
    assert result.utc is None


def test_ntp_ops_ntp_fail_on_short_packet():
    from src.device.network.ntp_ops import NtpOps
    from src.ticks import ticks_add, ticks_ms

    ops = NtpOps(
        wlan=_connected_wlan(),
        socket_module=_fake_socket(recv_data=b"\x00" * 16),
        secrets_mod=_Secrets(),
    )
    result = ops.run(_Cmd(10, ticks_add(ticks_ms(), 60_000)))
    assert result.ok is False
    assert result.error_code == "ntp_fail"


def test_ntp_ops_ntp_fail_on_kod_stratum_zero():
    from src.device.network.ntp_ops import NtpOps
    from src.ticks import ticks_add, ticks_ms

    ops = NtpOps(
        wlan=_connected_wlan(),
        socket_module=_fake_socket(recv_data=_ntp_payload(stratum=0)),
        secrets_mod=_Secrets(),
    )
    result = ops.run(_Cmd(11, ticks_add(ticks_ms(), 60_000)))
    assert result.ok is False
    assert result.error_code == "ntp_fail"


def test_ntp_ops_ntp_fail_on_li_alarm():
    from src.device.network.ntp_ops import NtpOps
    from src.ticks import ticks_add, ticks_ms

    ops = NtpOps(
        wlan=_connected_wlan(),
        socket_module=_fake_socket(recv_data=_ntp_payload(li=3, stratum=2)),
        secrets_mod=_Secrets(),
    )
    result = ops.run(_Cmd(12, ticks_add(ticks_ms(), 60_000)))
    assert result.ok is False
    assert result.error_code == "ntp_fail"
