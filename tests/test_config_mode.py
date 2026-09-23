"""Host tests for the clock/config boot split (issue #2).

The device answered ``503 Service temporarily unavailable`` to every
``GET /settings/add`` because the clock stack and the whole authenticated web
request path had to be resident in one 179,328-byte heap. The fix is a boot
split: clock mode runs no web stack and answers a knock on port 80 by setting
a flag and resetting; config mode runs no clock stack and serves the admin
site with the heap to itself.

Everything device-only (``machine``, sockets, the panel) is injected here, so
these tests cover the ordering and lifecycle rules that a MemoryError on
hardware would otherwise be the only way to discover.
"""

import pytest

from src import config
from src.device import config_mode, mode_flag
from src.device.knock import ConfigModeKnock
from src.device.reboot_port import RebootPort
from src.device.network.models import MODE_STATION_ONLINE
from src.time.model import DateTime


# --- flag lifecycle -------------------------------------------------------

class FakeFile:
    def __init__(self, store, path):
        self._store = store
        self._path = path
        self.closed = False

    def write(self, data):
        self._store[self._path] = data

    def read(self):
        return self._store[self._path]

    def close(self):
        self.closed = True


class FakeFS:
    """Minimal open/remove pair over a dict, matching MicroPython semantics."""

    def __init__(self, files=None):
        self.files = dict(files or {})
        self.removed = []

    def open(self, path, mode="r"):
        if mode.startswith("r"):
            if path not in self.files:
                raise OSError(2, "ENOENT")
            return FakeFile(self.files, path)
        self.files[path] = ""
        return FakeFile(self.files, path)

    def remove(self, path):
        if path not in self.files:
            raise OSError(2, "ENOENT")
        del self.files[path]
        self.removed.append(path)


def test_request_config_mode_writes_the_flag():
    fs = FakeFS()
    assert mode_flag.request_config_mode(path="/flag", open_fn=fs.open) is True
    assert fs.files["/flag"] == "1"


def test_reboot_port_enters_config_mode_only_after_flag_request(monkeypatch):
    from src.device import reboot_port as reboot_module

    events = []
    monkeypatch.setattr(
        reboot_module,
        "request_config_mode",
        lambda: events.append("flag") or True,
    )
    port = RebootPort(lambda: events.append("reset"))
    assert port.reset(True) is True
    assert events == ["flag", "reset"]

    events.clear()
    monkeypatch.setattr(reboot_module, "request_config_mode", lambda: False)
    assert port.reset(True) is False
    assert events == []


def test_consume_reports_the_flag_and_deletes_it_before_returning():
    fs = FakeFS({"/flag": "1"})
    assert mode_flag.consume_config_mode(
        path="/flag", open_fn=fs.open, remove_fn=fs.remove
    ) is True
    # Deleting on entry is what makes a config-mode crash self-healing: the
    # next reset lands in clock mode instead of looping back into config.
    assert "/flag" not in fs.files
    assert fs.removed == ["/flag"]


def test_consume_without_a_flag_is_a_clock_boot_and_no_error():
    fs = FakeFS()
    assert mode_flag.consume_config_mode(
        path="/flag", open_fn=fs.open, remove_fn=fs.remove
    ) is False
    assert fs.removed == []


def test_second_consume_after_entry_reports_clock_mode():
    fs = FakeFS({"/flag": "1"})
    mode_flag.consume_config_mode(path="/flag", open_fn=fs.open, remove_fn=fs.remove)
    assert mode_flag.consume_config_mode(
        path="/flag", open_fn=fs.open, remove_fn=fs.remove
    ) is False


def test_main_consumes_the_flag_before_any_hardware_bring_up():
    """A failure during bring-up must not strand the device in config mode."""
    import pathlib

    source = (pathlib.Path(__file__).resolve().parents[1] / "main.py").read_text()
    assert source.index("consume_config_mode()") < source.index("SPI(")
    assert source.index("consume_config_mode()") < source.index("initialize_display(")


# --- knock listener -------------------------------------------------------

class FakeConn:
    def __init__(self, chunk_size=None, would_block_first=0):
        self.sent = b""
        self.closed = False
        self.timeout = None
        self._chunk = chunk_size
        self._would_block_first = would_block_first

    def settimeout(self, seconds):
        self.timeout = seconds

    def send(self, data):
        if self._would_block_first:
            self._would_block_first -= 1
            raise OSError(11, "EAGAIN")
        if self._chunk is None:
            self.sent += data
            return len(data)
        chunk = data[: self._chunk]
        self.sent += chunk
        return len(chunk)

    def close(self):
        self.closed = True


class FakeListen:
    def __init__(self, conns=()):
        self.conns = list(conns)
        self.closed = False
        self.blocking = None
        self.bound = None
        self.backlog = None

    def setsockopt(self, *args):
        pass

    def bind(self, address):
        self.bound = address

    def listen(self, backlog):
        self.backlog = backlog

    def setblocking(self, flag):
        self.blocking = flag

    def accept(self):
        if not self.conns:
            raise OSError(11, "EAGAIN")
        return self.conns.pop(0), ("192.168.1.9", 51234)

    def close(self):
        self.closed = True


class FakeSocketModule:
    AF_INET = 2
    SOCK_STREAM = 1
    SOL_SOCKET = 1
    SO_REUSEADDR = 2

    def __init__(self, listen):
        self.listen_socket = listen

    def socket(self, *_args):
        return self.listen_socket


def _knock(conns=(), flag_writer=None):
    listen = FakeListen(conns)
    sockets = FakeSocketModule(listen)
    knock = ConfigModeKnock(socket_module=sockets, flag_writer=flag_writer)
    return knock, listen


def test_knock_without_a_connection_does_nothing():
    knock, listen = _knock()
    assert knock.tick() is False
    assert listen.bound == ("0.0.0.0", config.HTTP_LISTEN_PORT)
    assert listen.blocking is False
    assert listen.closed is False


def test_knock_answers_once_then_asks_for_the_reboot():
    conn = FakeConn()
    written = []
    knock, listen = _knock([conn], flag_writer=lambda: written.append(True) or True)

    assert knock.tick() is True
    assert conn.sent.startswith(b"HTTP/1.0 200 OK")
    assert b"http-equiv=\"refresh\"" in conn.sent
    # Declared length: the reset follows at once, so a client reading until
    # close would otherwise see a truncated body.
    header, _, body = conn.sent.partition(b"\r\n\r\n")
    assert b"Content-Length: " + str(len(body)).encode("ascii") in header
    assert conn.closed is True
    assert written == [True]
    # Port 80 is handed back so config mode's own server can bind it.
    assert listen.closed is True


def test_knock_writes_the_whole_response_across_short_sends():
    conn = FakeConn(chunk_size=32)
    knock, _listen = _knock([conn], flag_writer=lambda: True)
    assert knock.tick() is True
    assert conn.sent.endswith(b"</body></html>")


def test_knock_retries_a_would_block_send_instead_of_dropping_the_page():
    """The first send to a browser raises EAGAIN on MicroPython.

    Treating that as failure reset the device with the interstitial never
    delivered, so the page the browser was told to refresh never rendered.
    """
    conn = FakeConn(would_block_first=3)
    knock, _listen = _knock([conn], flag_writer=lambda: True)
    assert knock.tick() is True
    assert conn.timeout == 2
    assert conn.sent.endswith(b"</body></html>")


def test_knock_that_cannot_write_the_flag_stays_in_clock_mode():
    """A reboot without the flag would land back here and lose the request."""
    conn = FakeConn()
    knock, listen = _knock([conn], flag_writer=lambda: False)
    assert knock.tick() is False
    assert listen.closed is False


# --- config-mode session lifecycle ---------------------------------------

class FakeTicks:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    @staticmethod
    def ticks_add(value, delta):
        return value + delta

    @staticmethod
    def ticks_diff(a, b):
        return a - b


class FakeDisplay:
    width = 240
    height = 320

    def __init__(self):
        self.texts = []

    def fill(self, color):
        pass

    def fill_rect(self, *args):
        pass


class FakeCoordinator:
    mode = MODE_STATION_ONLINE

    def __init__(self, exit_after=None, busy_until=None):
        self.ticks = 0
        self.station_ip = "192.168.1.32"
        self.drained = False
        self._exit_after = exit_after
        self._busy_until = busy_until

    def tick(self):
        self.ticks += 1

    @property
    def web_busy(self):
        return self._busy_until is not None and self.ticks <= self._busy_until

    @property
    def web_exit_requested(self):
        return self._exit_after is not None and self.ticks >= self._exit_after

    def drain_web_writes(self):
        self.drained = True


class FakeReboot:
    def __init__(self):
        self.resets = 0

    def reset(self):
        self.resets += 1
        raise _Reset()


class _Reset(Exception):
    """Stands in for the device reset, which never returns."""


class FakeClock:
    def __init__(self, utc=None):
        self.utc = utc

    def read_utc(self):
        return self.utc


class FakeStore:
    def __init__(self, alerts=()):
        self.alerts = list(alerts)

    def load(self):
        return {"alerts": self.alerts}


def _run_config_mode(monkeypatch, coordinator, clock=None, store=None, ticks=None):
    ticks = ticks or FakeTicks()
    reboot = FakeReboot()
    monkeypatch.setattr(
        config_mode, "make_settings_coordinator",
        lambda *args, **kwargs: coordinator,
    )

    def sleep_ms(_ms):
        ticks.now += 10

    with pytest.raises(_Reset):
        config_mode.run(
            FakeDisplay(),
            store or FakeStore(),
            clock or FakeClock(),
            reboot,
            sleep_ms,
            log=lambda _message: None,
            ticks_module=ticks,
        )
    return reboot, coordinator


def test_config_mode_serves_until_the_browser_asks_to_return_to_the_clock(monkeypatch):
    coordinator = FakeCoordinator(exit_after=3)
    reboot, coordinator = _run_config_mode(monkeypatch, coordinator)
    assert reboot.resets == 1
    # A queued response is flushed before the reset, so the browser sees the
    # confirmation rather than a dropped connection.
    assert coordinator.drained is True


def test_config_mode_resets_on_the_idle_timeout(monkeypatch):
    coordinator = FakeCoordinator()
    ticks = FakeTicks()
    reboot, _ = _run_config_mode(monkeypatch, coordinator, ticks=ticks)
    assert reboot.resets == 1
    assert ticks.now >= config.CONFIG_MODE_IDLE_MS


def test_an_active_browser_keeps_the_session_open(monkeypatch):
    """Traffic re-arms the idle timeout, so a session in use is never cut."""
    idle_ticks = config.CONFIG_MODE_IDLE_MS // 10
    coordinator = FakeCoordinator(busy_until=idle_ticks + 50)
    ticks = FakeTicks()
    reboot, coordinator = _run_config_mode(monkeypatch, coordinator, ticks=ticks)
    assert reboot.resets == 1
    assert ticks.now > config.CONFIG_MODE_IDLE_MS


def test_config_mode_returns_to_the_clock_when_an_alert_comes_due(monkeypatch):
    """Clock mode owns the buzzer and the dismiss surface, so the alarm needs it."""
    alert = {"id": "alert-1", "hour": 7, "minute": 30, "enabled": True, "weekdays": []}
    store = FakeStore([alert])
    clock = FakeClock(DateTime(2026, 9, 22, 1, 7, 30, 0))
    ticks = FakeTicks()

    # The scheduler's first observation is a baseline, so move the clock one
    # minute on before the second poll to make the alert land on a new minute.
    class SteppingClock(FakeClock):
        def __init__(self):
            super().__init__(DateTime(2026, 9, 22, 1, 7, 29, 0))
            self.reads = 0

        def read_utc(self):
            self.reads += 1
            if self.reads > 1:
                return DateTime(2026, 9, 22, 1, 7, 30, 0)
            return self.utc

    monkeypatch.setattr(
        config_mode, "utc_to_local", lambda utc, *args, **kwargs: utc
    )
    coordinator = FakeCoordinator()
    reboot, _ = _run_config_mode(
        monkeypatch, coordinator, clock=SteppingClock(), store=store, ticks=ticks
    )
    assert reboot.resets == 1
    # Far sooner than the idle timeout: the alarm is what ended the session.
    assert ticks.now < config.CONFIG_MODE_IDLE_MS
    assert clock is not None
