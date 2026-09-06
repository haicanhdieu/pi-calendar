"""Host tests for SETUP_AP boot ownership on NetworkCoordinator."""

from src.device.network.coordinator import NetworkCoordinator
from src.device.network.mailbox import Mailbox, SyncCommand
from src.device.network.models import (
    EVENT_SETUP_ERROR,
    EVENT_SETUP_STATUS,
    MODE_SETUP_AP,
    MODE_STATION_CONNECTING,
    MODE_STATION_ONLINE,
    SETUP_AP_GATEWAY,
    SETUP_AP_SSID,
    make_settings_coordinator,
    ntp_sync_enabled,
)
from src.provisioning.verifier import derive_admin_verifier

from tests.test_network_coordinator import (
    FakeSocketModule,
    FakeTicks,
    FakeWlan,
    Secrets,
    make_coordinator,
    ntp_payload,
    terminal,
)
from tests.test_settings_store import FakeFS, _record_bytes, _store


class FakeApWlan:
    def __init__(self, fail=False, fail_times=0):
        self.fail = fail
        self._failures_left = int(fail_times)
        self.active_value = None
        self.config_calls = []

    def _should_fail(self):
        if self.fail:
            return True
        if self._failures_left > 0:
            self._failures_left -= 1
            return True
        return False

    def config(self, **kwargs):
        if self._should_fail():
            raise OSError("ap config fail")
        self.config_calls.append(kwargs)

    def active(self, value=None):
        if self.fail:
            raise OSError("ap active fail")
        if value is None:
            return self.active_value
        self.active_value = value


class UnconfiguredStore:
    def is_configured(self):
        return False


def test_absent_settings_enters_setup_ap_without_crash():
    events = []
    ap = FakeApWlan()
    coordinator = NetworkCoordinator(
        Mailbox(),
        settings_store=UnconfiguredStore(),
        event_sink=events,
        ap_wlan=ap,
        wlan=FakeWlan(),
        secrets_mod=Secrets,
    )
    assert coordinator.mode == MODE_SETUP_AP
    coordinator.tick()
    assert ap.config_calls == [{"essid": SETUP_AP_SSID, "security": 0}]
    assert ap.active_value is True
    assert len(events) == 1
    assert events[0].kind == EVENT_SETUP_STATUS
    assert events[0].mode == MODE_SETUP_AP
    assert events[0].ssid == SETUP_AP_SSID
    assert events[0].ip == SETUP_AP_GATEWAY


def test_malformed_settings_file_enters_setup_ap_and_preserves_bytes():
    fs = FakeFS({".settings-v1": b"{bad"})
    store = _store(fs)
    events = []
    coordinator = NetworkCoordinator(
        Mailbox(),
        settings_store=store,
        event_sink=events,
        ap_wlan=FakeApWlan(),
    )
    assert coordinator.mode == MODE_SETUP_AP
    assert fs.files[".settings-v1"] == b"{bad"
    coordinator.tick()
    assert events[0].ssid == SETUP_AP_SSID


def test_valid_settings_do_not_enter_setup_ap_and_keep_ntp_path():
    salt, verifier = derive_admin_verifier("admin", salt=b"\x03" * 16)
    fs = FakeFS(
        {
            ".settings-v1": _record_bytes(
                admin_salt=salt, admin_verifier=verifier
            )
        }
    )
    store = _store(fs)
    events = []
    coordinator, box, _ticks = make_coordinator()
    wlan = FakeWlan(True)
    # Rebuild with configured store while reusing mailbox NTP fakes.
    coordinator = NetworkCoordinator(
        box,
        wlan=wlan,
        socket_module=FakeSocketModule(ntp_payload()),
        secrets_mod=Secrets,
        ticks_module=FakeTicks(),
        settings_store=store,
        event_sink=events,
        ap_wlan=FakeApWlan(),
    )
    assert coordinator.mode == MODE_STATION_CONNECTING
    assert store.is_configured() is True
    # Store STA connect completes first, then NTP mailbox path runs.
    coordinator.tick()  # begin attempt + emit connecting
    coordinator.tick()  # already connected → online
    assert coordinator.mode == MODE_STATION_ONLINE
    box.enqueue(SyncCommand(1, 100))
    coordinator.tick()
    coordinator.tick()
    coordinator.tick()
    assert terminal(box).ok is True
    kinds = [e.kind for e in events]
    assert "station_status" in kinds


def test_setup_ap_wlan_error_emits_named_event_without_crash():
    events = []
    coordinator = NetworkCoordinator(
        Mailbox(),
        settings_store=UnconfiguredStore(),
        event_sink=events,
        ap_wlan=FakeApWlan(fail=True),
    )
    coordinator.tick()
    assert events[0].kind == EVENT_SETUP_ERROR
    assert events[0].error_code == "ap_fail"
    coordinator.tick()  # still safe
    assert len(events) == 1


def test_setup_ap_retries_after_transient_wlan_failure():
    events = []
    ap = FakeApWlan(fail_times=1)
    coordinator = NetworkCoordinator(
        Mailbox(),
        settings_store=UnconfiguredStore(),
        event_sink=events,
        ap_wlan=ap,
    )
    coordinator.tick()
    assert events[0].kind == EVENT_SETUP_ERROR
    assert events[0].error_code == "ap_fail"
    coordinator.tick()
    assert ap.config_calls == [{"essid": SETUP_AP_SSID, "security": 0}]
    assert ap.active_value is True
    assert events[1].kind == EVENT_SETUP_STATUS
    assert events[1].ssid == SETUP_AP_SSID


def test_legacy_without_settings_store_keeps_ntp_tests_path():
    coordinator, box, _ticks = make_coordinator()
    assert coordinator.mode == MODE_STATION_ONLINE
    box.enqueue(SyncCommand(2, 100))
    coordinator.tick()
    coordinator.tick()
    coordinator.tick()
    assert terminal(box).ok is True


def test_ntp_sync_enabled_gates_setup_ap_and_follows_credentials():
    assert ntp_sync_enabled(MODE_SETUP_AP, True) is False
    assert ntp_sync_enabled(MODE_SETUP_AP, False) is False
    assert ntp_sync_enabled(MODE_STATION_ONLINE, True) is True
    assert ntp_sync_enabled(MODE_STATION_ONLINE, False) is False


def test_make_settings_coordinator_absent_store_enters_setup_ap():
    fs = FakeFS()
    store = _store(fs)
    events = []
    coordinator = make_settings_coordinator(
        Mailbox(), store, events, ap_wlan=FakeApWlan()
    )
    assert store.is_configured() is False
    assert coordinator.mode == MODE_SETUP_AP


def test_boot_uses_real_settings_store_is_configured():
    fs = FakeFS()
    store = _store(fs)
    assert store.is_configured() is False
    coordinator = NetworkCoordinator(
        Mailbox(),
        settings_store=store,
        ap_wlan=FakeApWlan(),
    )
    assert coordinator.mode == MODE_SETUP_AP

    salt, verifier = derive_admin_verifier("admin", salt=b"\x04" * 16)
    fs.files[".settings-v1"] = _record_bytes(
        admin_salt=salt, admin_verifier=verifier
    )
    configured = _store(fs)
    assert configured.is_configured() is True
    online = NetworkCoordinator(
        Mailbox(),
        settings_store=configured,
        ap_wlan=FakeApWlan(),
    )
    assert online.mode == MODE_STATION_CONNECTING
