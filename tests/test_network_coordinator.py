"""Host proof for the tick-driven WLAN/NTP coordinator."""

from src.device.network.coordinator import NetworkCoordinator
from src.device.network.mailbox import Mailbox, SyncCommand
from src.app import App
from src.time.model import TRUST_SYNCED, DateTime
from src.ui.calendar_view import CalendarView
from src.ui.clock_view import ClockView
from src.ui.display_port import FakeDisplayPort


class FakeTicks:
    PERIOD = 2**32

    def __init__(self, now=0):
        self.now = now

    def ticks_ms(self):
        return self.now

    def ticks_add(self, value, delta):
        return (value + delta) & (self.PERIOD - 1)

    def ticks_diff(self, first, second):
        value = (first - second) & (self.PERIOD - 1)
        return value - self.PERIOD if value >= self.PERIOD // 2 else value


class Secrets:
    WIFI_SSID = "ssid"
    WIFI_PASSWORD = "password"


def ntp_payload():
    data = bytearray(48)
    data[0] = (3 << 3) | 4
    data[1] = 2
    data[40:44] = (1788696000 + 2208988800).to_bytes(4, "big")
    return bytes(data)


class FakeWlan:
    def __init__(self, connected=False, ip="192.168.1.40"):
        self.connected = connected
        self.connect_calls = []
        self.disconnect_calls = 0
        self._ip = ip
        self.active_value = False

    def active(self, value=None):
        if value is None:
            return self.active_value
        self.active_value = value

    def isconnected(self):
        return self.connected

    def connect(self, ssid, password):
        self.connect_calls.append((ssid, password))

    def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False

    def ifconfig(self):
        return (self._ip, "255.255.255.0", "192.168.1.1", "8.8.8.8")


class FakeSocketModule:
    AF_INET = 2
    SOCK_DGRAM = 2

    def __init__(
        self, payload=None, would_block=False, recv_exc=None, sender=None,
        socket_exc=None, send_exc=None,
    ):
        self.payload = payload
        self.would_block = would_block
        self.recv_exc = recv_exc
        self.sender = sender if sender is not None else ("129.6.15.28", 123)
        self.socket_exc = socket_exc
        self.send_exc = send_exc
        self.sock = None

    def socket(self, *_args):
        module = self

        class Socket:
            def __init__(self):
                self.closed = False
                self.sent = None

            def setblocking(self, value):
                assert value is False

            def sendto(self, packet, address):
                if module.send_exc is not None:
                    raise module.send_exc
                self.sent = (packet, address)

            def recvfrom(self, _size):
                if module.recv_exc is not None:
                    raise module.recv_exc
                if module.would_block:
                    raise OSError(11, "would block")
                return (module.payload, module.sender)

            def close(self):
                self.closed = True

        if self.socket_exc is not None:
            raise self.socket_exc
        self.sock = Socket()
        return self.sock


def make_coordinator(wlan=None, socket=None, secrets=Secrets, now=0):
    ticks = FakeTicks(now)
    box = Mailbox()
    coordinator = NetworkCoordinator(
        box,
        wlan=wlan if wlan is not None else FakeWlan(True),
        socket_module=socket if socket is not None else FakeSocketModule(ntp_payload()),
        secrets_mod=secrets,
        ticks_module=ticks,
    )
    return coordinator, box, ticks


def terminal(box):
    result = box.try_take_result()
    assert result is not None
    assert box.try_take_result() is None
    return result


def test_pending_association_is_one_poll_per_tick_and_connects_once():
    wlan = FakeWlan(False)
    coordinator, box, _ticks = make_coordinator(wlan=wlan)
    box.enqueue(SyncCommand(1, 100))
    coordinator.tick()
    assert wlan.connect_calls == [("ssid", "password")]
    coordinator.tick()
    assert wlan.connect_calls == [("ssid", "password")]
    assert box.try_take_result() is None
    wlan.connected = True
    coordinator.tick()
    assert coordinator.active


def test_valid_wifi_and_ntp_publish_success_without_rtc_write():
    coordinator, box, _ticks = make_coordinator()
    box.enqueue(SyncCommand(2, 100))
    coordinator.tick()  # take command; already associated
    coordinator.tick()  # create/send non-blocking UDP request
    coordinator.tick()  # receive and parse
    result = terminal(box)
    assert result.ok is True
    assert result.utc == DateTime(2026, 9, 6, 6, 12, 0, 0)


def test_missing_credentials_publish_wifi_fail_without_wlan_call():
    class Empty:
        WIFI_SSID = ""
        WIFI_PASSWORD = ""

    wlan = FakeWlan()
    coordinator, box, _ticks = make_coordinator(wlan=wlan, secrets=Empty)
    box.enqueue(SyncCommand(3, 100))
    coordinator.tick()
    result = terminal(box)
    assert result.error_code == "wifi_fail"
    assert wlan.connect_calls == []


def test_deadline_closes_pending_socket_and_publishes_once():
    socket = FakeSocketModule(would_block=True)
    coordinator, box, ticks = make_coordinator(socket=socket)
    box.enqueue(SyncCommand(4, 10))
    coordinator.tick()
    coordinator.tick()
    assert socket.sock.closed is False
    ticks.now = 10
    coordinator.tick()
    assert terminal(box).error_code == "deadline"
    assert socket.sock.closed is True
    coordinator.tick()
    assert box.try_take_result() is None


def test_deadline_while_wlan_never_associates_publishes_once():
    wlan = FakeWlan(False)
    coordinator, box, ticks = make_coordinator(wlan=wlan)
    box.enqueue(SyncCommand(40, 10))
    coordinator.tick()
    coordinator.tick()
    ticks.now = 10
    coordinator.tick()
    assert terminal(box).error_code == "deadline"
    assert wlan.connect_calls == [("ssid", "password")]
    assert coordinator.active is False


def test_malformed_response_closes_socket_and_publishes_ntp_fail():
    socket = FakeSocketModule(b"bad")
    coordinator, box, _ticks = make_coordinator(socket=socket)
    box.enqueue(SyncCommand(5, 100))
    coordinator.tick()
    coordinator.tick()
    coordinator.tick()
    assert terminal(box).error_code == "ntp_fail"
    assert socket.sock.closed is True


def test_socket_setup_failure_publishes_ntp_fail_once():
    coordinator, box, _ticks = make_coordinator(
        socket=FakeSocketModule(socket_exc=OSError("socket"))
    )
    box.enqueue(SyncCommand(6, 100))
    coordinator.tick()
    coordinator.tick()
    assert terminal(box).error_code == "ntp_fail"
    assert coordinator.active is False


def test_socket_send_failure_closes_socket_and_publishes_ntp_fail():
    socket = FakeSocketModule(send_exc=OSError("send"))
    coordinator, box, _ticks = make_coordinator(socket=socket)
    box.enqueue(SyncCommand(7, 100))
    coordinator.tick()
    coordinator.tick()
    assert terminal(box).error_code == "ntp_fail"
    assert socket.sock.closed is True


def test_permanent_receive_oserror_closes_socket_and_publishes_ntp_fail():
    socket = FakeSocketModule(recv_exc=OSError(113, "unreachable"))
    coordinator, box, _ticks = make_coordinator(socket=socket)
    box.enqueue(SyncCommand(8, 100))
    coordinator.tick()
    coordinator.tick()
    coordinator.tick()
    assert terminal(box).error_code == "ntp_fail"
    assert socket.sock.closed is True


def test_wrong_sender_is_rejected_and_socket_is_closed():
    socket = FakeSocketModule(ntp_payload(), sender=("203.0.113.1", 123))
    coordinator, box, _ticks = make_coordinator(socket=socket)
    box.enqueue(SyncCommand(9, 100))
    coordinator.tick()
    coordinator.tick()
    coordinator.tick()
    assert terminal(box).error_code == "ntp_fail"
    assert socket.sock.closed is True


def test_non_server_ntp_mode_is_rejected_and_socket_is_closed():
    payload = bytearray(ntp_payload())
    payload[0] = (3 << 3) | 3  # client mode, not an NTP server response
    socket = FakeSocketModule(bytes(payload))
    coordinator, box, _ticks = make_coordinator(socket=socket)
    box.enqueue(SyncCommand(10, 100))
    coordinator.tick()
    coordinator.tick()
    coordinator.tick()
    assert terminal(box).error_code == "ntp_fail"
    assert socket.sock.closed is True


def test_production_tick_order_integrates_sync_result_with_app_rtc_write():
    class Clock:
        def __init__(self):
            self.utc = None
            self.set_calls = []

        def read_utc(self):
            return self.utc

        def set_utc(self, utc):
            self.utc = utc
            self.set_calls.append(utc)

    ticks = FakeTicks()
    mailbox = Mailbox()
    coordinator = NetworkCoordinator(
        mailbox,
        wlan=FakeWlan(True),
        socket_module=FakeSocketModule(ntp_payload()),
        secrets_mod=Secrets,
        ticks_module=ticks,
    )
    display = FakeDisplayPort()
    clock = Clock()
    app = App(
        clock_port=clock,
        clock_view=ClockView(display),
        calendar_view=CalendarView(display),
        mailbox=mailbox,
        ticks_module=ticks,
    )
    app.boot()

    # This is main.py's production ordering: coordinator before App each tick.
    coordinator.tick()
    app.step(now_ticks=ticks.now)  # enqueues command 1
    ticks.now = 1
    coordinator.tick()
    app.step(now_ticks=ticks.now)
    ticks.now = 2
    coordinator.tick()
    app.step(now_ticks=ticks.now)
    ticks.now = 3
    coordinator.tick()  # publishes fresh success
    app.step(now_ticks=ticks.now)  # consumes it in the same loop iteration

    assert clock.set_calls == [DateTime(2026, 9, 6, 6, 12, 0, 0)]
    assert app.state.trust == TRUST_SYNCED


def test_production_composition_has_no_threaded_network_worker():
    from pathlib import Path

    main_source = (Path(__file__).resolve().parents[1] / "main.py").read_text()
    assert "NetworkWorker" not in main_source
    assert "_thread" not in main_source
    assert main_source.index("coordinator.tick()") < main_source.index("app.step()")
    assert "SetupHttpServer" not in main_source
    assert "http_server=setup_http" not in main_source


class ScanWlan(FakeWlan):
    def __init__(self, results):
        super().__init__(False)
        self.results = list(results)
        self.scan_calls = 0

    def scan(self):
        self.scan_calls += 1
        return self.results.pop(0) if self.results else []


def test_empty_scan_is_not_cached_so_a_later_page_load_rescans():
    wlan = ScanWlan([[], [(b"Home", 0, 0, -40, 0, 0)]])
    coordinator, _box, _ticks = make_coordinator(wlan=wlan)

    assert coordinator._scan_ssids() == ()
    assert coordinator.scan_status == "empty"
    assert coordinator._scan_ssids() == ("Home",)
    assert coordinator.scan_status == "ok"
    assert wlan.scan_calls == 2


def test_successful_scan_survives_a_failed_setup_kdf_warmup(monkeypatch):
    wlan = ScanWlan([[(b"Home", 0, 0, -40, 0, 0)]])
    coordinator, _box, _ticks = make_coordinator(wlan=wlan)
    import builtins

    real_import = builtins.__import__

    def fail_setup_kdf(name, *args, **kwargs):
        if name == "src.provisioning.setup_kdf":
            raise MemoryError("no heap for setup kdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_setup_kdf)
    ssids = coordinator._scan_ssids()
    monkeypatch.undo()

    assert ssids == ("Home",)
    assert coordinator.scan_status == "ok"
    assert coordinator.scan_error is None


def test_cached_scan_is_reused_until_a_rescan_forces_a_refresh():
    wlan = ScanWlan([[(b"Home", 0, 0, -40, 0, 0)], [(b"Other", 0, 0, -50, 0, 0)]])
    coordinator, _box, _ticks = make_coordinator(wlan=wlan)

    assert coordinator._scan_ssids() == ("Home",)
    assert coordinator._scan_ssids() == ("Home",)
    assert wlan.scan_calls == 1
    assert coordinator._scan_ssids(force=True) == ("Other",)
    assert wlan.scan_calls == 2
