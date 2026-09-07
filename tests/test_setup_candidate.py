"""Host tests for setup candidate join/persist ordering on NetworkCoordinator."""

from src.device.network.coordinator import NetworkCoordinator
from src.device.network.mailbox import Mailbox
from src.device.network.models import (
    EVENT_STATION_ERROR,
    EVENT_STATION_STATUS,
    MODE_SETUP_AP,
    MODE_STATION_CONNECTING,
    MODE_STATION_ONLINE,
    ERROR_JOIN_FAIL,
    ERROR_JOIN_TIMEOUT,
    ERROR_PERSIST_FAIL,
)
from src.device.web.server import SetupHttpServer
from src.device.settings_store import SettingsCommitError, COMMIT_WRITE_FAIL

from tests.test_network_coordinator import FakeTicks, FakeWlan
from tests.test_setup_ap_coordinator import FakeApWlan, UnconfiguredStore
from tests.test_settings_store import FakeFS, _store


class ScanWlan(FakeWlan):
    def __init__(self, connected=False, scan_rows=None, fail_connect=False):
        super().__init__(connected=connected)
        self.scan_rows = scan_rows if scan_rows is not None else [
            (b"HomeNet", b"\x11" * 6, 1, -40, 3, False),
            (b"HomeNet", b"\x22" * 6, 1, -50, 3, False),
            (b"Cafe", b"\x33" * 6, 1, -60, 3, False),
        ]
        self.fail_connect = fail_connect
        self.disconnect_calls = 0
        self._ip = "192.168.1.50"
        self.active_value = False

    def active(self, value=None):
        if value is None:
            return self.active_value
        self.active_value = value

    def scan(self):
        return list(self.scan_rows)

    def connect(self, ssid, password):
        if self.fail_connect:
            raise OSError("connect fail")
        self.connect_calls.append((ssid, password))

    def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False

    def ifconfig(self):
        return (self._ip, "255.255.255.0", "192.168.1.1", "8.8.8.8")


class FakeStreamSocket:
    def __init__(self, peer=("192.168.4.2", 12345)):
        self._inbox = bytearray()
        self._outbox = bytearray()
        self.closed = False
        self.peer = peer
        self.blocking = True
        self._peer_closed = False

    def setblocking(self, value):
        self.blocking = value

    def settimeout(self, _value):
        self.blocking = False

    def push_client_bytes(self, data):
        self._inbox.extend(data)

    def mark_peer_closed(self):
        self._peer_closed = True

    def recv(self, size):
        if self.closed:
            raise OSError(9, "closed")
        if self._peer_closed:
            return b""
        if not self._inbox:
            raise OSError(11, "would block")
        chunk = bytes(self._inbox[:size])
        del self._inbox[:size]
        return chunk

    def send(self, data):
        if self.closed:
            raise OSError(9, "closed")
        self._outbox.extend(data)
        return len(data)

    def close(self):
        self.closed = True

    @property
    def sent(self):
        return bytes(self._outbox)


class FakeListenSocket:
    def __init__(self):
        self.pending = []
        self.closed = False
        self.bound = None

    def setsockopt(self, *_args):
        return None

    def bind(self, addr):
        self.bound = addr

    def listen(self, _backlog):
        return None

    def setblocking(self, _value):
        return None

    def settimeout(self, _value):
        return None

    def accept(self):
        if not self.pending:
            raise OSError(11, "would block")
        return self.pending.pop(0)

    def close(self):
        self.closed = True

    def enqueue(self, client_sock, addr=None):
        self.pending.append((client_sock, addr or client_sock.peer))


class FakeTcpSocketModule:
    AF_INET = 2
    SOCK_STREAM = 1
    SOL_SOCKET = 1
    SO_REUSEADDR = 2

    def __init__(self):
        self.listen = FakeListenSocket()

    def socket(self, *_args):
        return self.listen


def _http_get(path="/"):
    return "GET {} HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n".format(path).encode(
        "ascii"
    )


def _http_connect(ssid="HomeNet", wifi="password1", admin="password1"):
    body = "ssid={}&wifi_password={}&admin_password={}".format(ssid, wifi, admin)
    return (
        "POST /connect HTTP/1.1\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        "Content-Length: {}\r\n\r\n{}"
    ).format(len(body), body).encode("ascii")


def _make(store=None, wlan=None, ticks=None, events=None):
    events = [] if events is None else events
    ticks = FakeTicks(0) if ticks is None else ticks
    sockets = FakeTcpSocketModule()
    http = SetupHttpServer(socket_module=sockets, per_tick_bytes=4096)
    coordinator = NetworkCoordinator(
        Mailbox(),
        settings_store=store if store is not None else UnconfiguredStore(),
        event_sink=events,
        ap_wlan=FakeApWlan(),
        wlan=wlan if wlan is not None else ScanWlan(),
        ticks_module=ticks,
        http_server=http,
        socket_module=sockets,
    )
    return coordinator, http, sockets, events, ticks


def _activate(coordinator):
    coordinator.tick()
    assert coordinator.mode == MODE_SETUP_AP
    assert coordinator._setup_ap_active is True


def _pump_until(coordinator, pred, limit=40):
    for _ in range(limit):
        if pred():
            return True
        coordinator.tick()
    return pred()


def test_get_setup_page_and_scan_from_phone():
    wlan = ScanWlan()
    coordinator, http, sockets, events, ticks = _make(wlan=wlan)
    _activate(coordinator)

    client = FakeStreamSocket()
    client.push_client_bytes(_http_get("/"))
    sockets.listen.enqueue(client)
    assert _pump_until(coordinator, lambda: client.closed and b"Set Up Wi-Fi" in client.sent)
    assert b"#7c6cf6" in client.sent
    assert b"aria-live" in client.sent

    client2 = FakeStreamSocket()
    client2.push_client_bytes(_http_get("/scan"))
    sockets.listen.enqueue(client2)
    assert _pump_until(
        coordinator, lambda: client2.closed and b'"HomeNet"' in client2.sent
    )
    assert b"Cafe" in client2.sent
    # Deduped — HomeNet once; no BSSID bytes in payload.
    assert client2.sent.count(b"HomeNet") == 1
    assert b"\x11\x11" not in client2.sent


def test_next_is_client_only_no_candidate_before_connect():
    fs = FakeFS()
    store = _store(fs)
    coordinator, http, sockets, events, ticks = _make(store=store)
    _activate(coordinator)
    assert coordinator.candidate_active is False
    assert events[0].kind != EVENT_STATION_STATUS

    page = FakeStreamSocket()
    page.push_client_bytes(_http_get("/"))
    sockets.listen.enqueue(page)
    assert _pump_until(coordinator, lambda: page.closed and b"Set Up Wi-Fi" in page.sent)

    scan = FakeStreamSocket()
    scan.push_client_bytes(_http_get("/scan"))
    sockets.listen.enqueue(scan)
    assert _pump_until(coordinator, lambda: scan.closed and b"ssids" in scan.sent)

    assert coordinator.candidate_active is False
    assert store.is_configured() is False
    assert coordinator.mode == MODE_SETUP_AP
    assert not any(e.kind == EVENT_STATION_STATUS for e in events)


def test_connect_join_commit_success_order():
    fs = FakeFS()
    store = _store(fs)
    wlan = ScanWlan(connected=False)
    events = []
    ticks = FakeTicks(1000)
    client_holder = []

    class OrderAp(FakeApWlan):
        def active(self, value=None):
            if value is False:
                client = client_holder[0] if client_holder else None
                assert client is not None and b"Connected" in client.sent, (
                    "browser success must flush before AP deactivates"
                )
            return super().active(value)

    sockets = FakeTcpSocketModule()
    http = SetupHttpServer(socket_module=sockets, per_tick_bytes=4096)
    ap = OrderAp()
    coordinator = NetworkCoordinator(
        Mailbox(),
        settings_store=store,
        event_sink=events,
        ap_wlan=ap,
        wlan=wlan,
        ticks_module=ticks,
        http_server=http,
        socket_module=sockets,
    )
    _activate(coordinator)

    client = FakeStreamSocket()
    client_holder.append(client)
    client.push_client_bytes(_http_connect())
    sockets.listen.enqueue(client)

    # Accept + parse + start candidate (STA connect begins on the next tick)
    assert _pump_until(coordinator, lambda: coordinator.candidate_active)
    assert coordinator.mode == MODE_STATION_CONNECTING
    assert store.is_configured() is False  # not persisted yet
    assert not client.closed  # held through join

    assert _pump_until(coordinator, lambda: wlan.connect_calls == [("HomeNet", "password1")])
    assert store.is_configured() is False
    assert not client.closed

    wlan.connected = True
    ticks.now = 2000
    assert _pump_until(
        coordinator,
        lambda: coordinator.mode == MODE_STATION_ONLINE and client.closed,
    )
    assert store.is_configured() is True
    assert coordinator._setup_ap_active is False
    assert ap.active_value is False
    assert b"Connected" in client.sent
    kinds = [e.kind for e in events]
    assert EVENT_STATION_STATUS in kinds
    online = [e for e in events if e.kind == EVENT_STATION_STATUS and e.mode == MODE_STATION_ONLINE]
    assert online
    assert online[-1].ip == "192.168.1.50"
    assert online[-1].ssid == "HomeNet"


def test_join_timeout_keeps_ap_and_clears_wifi_only_in_response():
    fs = FakeFS()
    store = _store(fs)
    wlan = ScanWlan(connected=False)
    events = []
    ticks = FakeTicks(0)
    coordinator, http, sockets, _e, ticks = _make(
        store=store, wlan=wlan, ticks=ticks, events=events
    )
    _activate(coordinator)

    client = FakeStreamSocket()
    client.push_client_bytes(
        _http_connect(ssid="HomeNet", wifi="password1", admin="adminpass")
    )
    sockets.listen.enqueue(client)
    assert _pump_until(coordinator, lambda: coordinator.candidate_active)

    ticks.now = 20_000
    assert _pump_until(
        coordinator, lambda: not coordinator.candidate_active and client.closed
    )
    assert store.is_configured() is False
    assert coordinator.mode == MODE_SETUP_AP
    assert coordinator._setup_ap_active is True
    assert wlan.disconnect_calls >= 1
    assert b"Couldn't join" in client.sent
    assert b"adminpass" in client.sent  # admin retained in failure page
    assert b"password1" not in client.sent  # wifi password cleared
    assert b'id="screen2" class="screen active"' in client.sent
    err = [e for e in events if e.kind == EVENT_STATION_ERROR]
    assert err and err[-1].error_code == ERROR_JOIN_TIMEOUT


def test_join_fail_on_connect_error_disconnects_and_keeps_ap():
    fs = FakeFS()
    store = _store(fs)
    wlan = ScanWlan(connected=False, fail_connect=True)
    events = []
    ticks = FakeTicks(0)
    coordinator, http, sockets, _e, ticks = _make(
        store=store, wlan=wlan, ticks=ticks, events=events
    )
    _activate(coordinator)

    client = FakeStreamSocket()
    client.push_client_bytes(
        _http_connect(ssid="HomeNet", wifi="password1", admin="adminpass")
    )
    sockets.listen.enqueue(client)
    assert _pump_until(coordinator, lambda: coordinator.candidate_active)
    assert _pump_until(
        coordinator, lambda: not coordinator.candidate_active and client.closed
    )
    assert store.is_configured() is False
    assert coordinator.mode == MODE_SETUP_AP
    assert coordinator._setup_ap_active is True
    assert wlan.disconnect_calls >= 1
    assert b"Couldn't join" in client.sent
    assert b"adminpass" in client.sent
    assert b"password1" not in client.sent
    err = [e for e in events if e.kind == EVENT_STATION_ERROR]
    assert err and err[-1].error_code == ERROR_JOIN_FAIL


def test_join_timeout_wrap_safe_deadline():
    fs = FakeFS()
    store = _store(fs)
    wlan = ScanWlan(connected=False)
    events = []
    # Near uint32 wrap so only ticks_diff wrap-safety detects expiry.
    ticks = FakeTicks(FakeTicks.PERIOD - 2_000)
    coordinator, http, sockets, _e, ticks = _make(
        store=store, wlan=wlan, ticks=ticks, events=events
    )
    _activate(coordinator)

    client = FakeStreamSocket()
    client.push_client_bytes(_http_connect())
    sockets.listen.enqueue(client)
    assert _pump_until(coordinator, lambda: coordinator.candidate_active)
    deadline = coordinator._candidate_deadline
    ticks.now = ticks.ticks_add(deadline, 1)
    assert _pump_until(
        coordinator, lambda: not coordinator.candidate_active and client.closed
    )
    err = [e for e in events if e.kind == EVENT_STATION_ERROR]
    assert err and err[-1].error_code == ERROR_JOIN_TIMEOUT
    assert coordinator._setup_ap_active is True
    assert store.is_configured() is False


def test_persist_fail_disconnects_no_online_event():
    class BoomStore(UnconfiguredStore):
        def commit(self, **kwargs):
            raise SettingsCommitError(COMMIT_WRITE_FAIL, "boom")

    wlan = ScanWlan(connected=False)
    events = []
    ticks = FakeTicks(0)
    coordinator, http, sockets, _e, ticks = _make(
        store=BoomStore(), wlan=wlan, ticks=ticks, events=events
    )
    _activate(coordinator)
    client = FakeStreamSocket()
    client.push_client_bytes(_http_connect())
    sockets.listen.enqueue(client)
    assert _pump_until(coordinator, lambda: coordinator.candidate_active)
    wlan.connected = True
    assert _pump_until(
        coordinator, lambda: not coordinator.candidate_active and client.closed
    )
    assert wlan.disconnect_calls >= 1
    assert coordinator.mode == MODE_SETUP_AP
    assert coordinator._setup_ap_active is True
    online = [
        e
        for e in events
        if e.kind == EVENT_STATION_STATUS and e.mode == MODE_STATION_ONLINE
    ]
    assert online == []
    err = [e for e in events if e.kind == EVENT_STATION_ERROR]
    assert err and err[-1].error_code == ERROR_PERSIST_FAIL


def test_concurrent_connect_returns_503_busy():
    wlan = ScanWlan(connected=False)
    ticks = FakeTicks(0)
    coordinator, http, sockets, events, ticks = _make(wlan=wlan, ticks=ticks)
    _activate(coordinator)

    first = FakeStreamSocket()
    first.push_client_bytes(_http_connect())
    sockets.listen.enqueue(first)
    assert _pump_until(coordinator, lambda: coordinator.candidate_active)
    assert not first.closed

    second = FakeStreamSocket()
    second.push_client_bytes(_http_connect(ssid="Other", wifi="password1", admin="password1"))
    sockets.listen.enqueue(second)
    assert _pump_until(coordinator, lambda: second.closed and b"503" in second.sent)
    assert coordinator.candidate_active is True
    assert not first.closed


def test_main_defers_setup_http_server_to_coordinator():
    from pathlib import Path

    main_source = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8"
    )
    assert "SetupHttpServer" not in main_source
    assert "http_server=setup_http" not in main_source


def test_server_parse_error_oversized_closes_without_candidate():
    coordinator, http, sockets, events, ticks = _make()
    _activate(coordinator)
    client = FakeStreamSocket()
    client.push_client_bytes(b"GET /" + (b"a" * 400) + b" HTTP/1.1\r\n\r\n")
    sockets.listen.enqueue(client)
    assert _pump_until(coordinator, lambda: client.closed)
    assert b"413" in client.sent or b"Payload Too Large" in client.sent
    assert coordinator.candidate_active is False


def test_server_parse_error_malformed_closes_without_candidate():
    coordinator, http, sockets, events, ticks = _make()
    _activate(coordinator)
    client = FakeStreamSocket()
    client.push_client_bytes(b"NOTAREQUEST\r\n\r\n")
    sockets.listen.enqueue(client)
    assert _pump_until(coordinator, lambda: client.closed)
    assert b"400" in client.sent or b"Bad Request" in client.sent
    assert coordinator.candidate_active is False
