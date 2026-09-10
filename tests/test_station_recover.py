"""Host tests for store-credential station recovery (story 1.3)."""

import ast
from pathlib import Path

from src import config
from src.device.network.coordinator import NetworkCoordinator
from src.device.network.mailbox import Mailbox, SyncCommand, SyncResult
from src.device.network.models import (
    EVENT_SETUP_STATUS,
    EVENT_STATION_ERROR,
    EVENT_STATION_STATUS,
    MODE_SETUP_AP,
    MODE_STATION_CONNECTING,
    MODE_STATION_ONLINE,
    SETUP_AP_GATEWAY,
    SETUP_AP_SSID,
    boot_mode_for_settings,
    next_station_failure_count,
    reset_station_failure_count,
    station_failures_exhausted,
)
from src.provisioning.verifier import derive_admin_verifier

from tests.test_network_coordinator import FakeSocketModule, FakeTicks, FakeWlan
from tests.test_setup_ap_coordinator import FakeApWlan
from tests.test_settings_store import FakeFS, _record_bytes, _store

ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN = frozenset({"machine", "network", "socket", "ntptime"})


def _configured_store(fs=None, **overrides):
    salt, verifier = derive_admin_verifier("admin", salt=b"\x11" * 16)
    payload = _record_bytes(
        admin_salt=salt, admin_verifier=verifier, **overrides
    )
    files = {".settings-v1": payload}
    return _store(fs if fs is not None else FakeFS(files))


def _coordinator(store, wlan=None, events=None, ticks=None, ap=None):
    events = events if events is not None else []
    ticks = ticks if ticks is not None else FakeTicks()
    return (
        NetworkCoordinator(
            Mailbox(),
            wlan=wlan if wlan is not None else FakeWlan(False),
            ap_wlan=ap if ap is not None else FakeApWlan(),
            settings_store=store,
            event_sink=events,
            ticks_module=ticks,
        ),
        events,
        ticks,
    )


def test_boot_mode_helpers_and_failure_count_policy():
    assert boot_mode_for_settings(False) == MODE_SETUP_AP
    assert boot_mode_for_settings(True) == MODE_STATION_CONNECTING
    assert reset_station_failure_count() == 0
    assert next_station_failure_count(0) == 1
    assert next_station_failure_count(2) == 3
    assert station_failures_exhausted(2) is False
    assert station_failures_exhausted(3) is True
    assert station_failures_exhausted(3, limit=3) is True
    assert config.STATION_FAILURE_LIMIT == 3
    assert config.STATION_IP_DISPLAY_MS is None


def test_models_module_stays_pure():
    source = (ROOT / "src" / "device" / "network" / "models.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in _FORBIDDEN
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in _FORBIDDEN


def test_configured_boot_connects_with_store_credentials_and_emits_ip():
    store = _configured_store(wifi_ssid="HomeNet", wifi_password="password1")
    wlan = FakeWlan(False, ip="192.168.1.55")
    coordinator, events, ticks = _coordinator(store, wlan=wlan)
    assert coordinator.mode == MODE_STATION_CONNECTING

    coordinator.tick()  # begin attempt (emit connecting)
    assert events[-1].kind == EVENT_STATION_STATUS
    assert events[-1].mode == MODE_STATION_CONNECTING

    coordinator.tick()  # issue connect
    assert wlan.connect_calls == [("HomeNet", "password1")]

    wlan.connected = True
    ticks.now = 50
    coordinator.tick()
    assert coordinator.mode == MODE_STATION_ONLINE
    online = events[-1]
    assert online.kind == EVENT_STATION_STATUS
    assert online.mode == MODE_STATION_ONLINE
    assert online.ip == "192.168.1.55"
    assert coordinator._station_failure_count == 0


def test_three_boot_terminal_failures_enter_setup_ap():
    store = _configured_store()
    wlan = FakeWlan(False)
    ap = FakeApWlan()
    events = []
    ticks = FakeTicks()
    coordinator, events, ticks = _coordinator(
        store, wlan=wlan, events=events, ticks=ticks, ap=ap
    )

    for attempt in range(3):
        coordinator.tick()  # begin / or resume after gap
        # Expire the 15s join deadline.
        ticks.now = ticks.ticks_add(
            ticks.now, config.SYNC_COMMAND_DEADLINE_MS
        )
        coordinator.tick()  # terminal timeout
        if attempt < 2:
            assert coordinator.mode == MODE_STATION_CONNECTING
            assert coordinator._station_failure_count == attempt + 1
            # Advance past reconnect gap so the next begin can run.
            ticks.now = ticks.ticks_add(
                ticks.now, config.STATION_RECONNECT_GAP_MS
            )

    assert coordinator._station_failure_count == 3
    assert coordinator.mode == MODE_SETUP_AP
    assert ap.active_value is True
    setup = [e for e in events if e.kind == EVENT_SETUP_STATUS]
    assert setup
    assert setup[-1].ssid == SETUP_AP_SSID
    assert setup[-1].ip == SETUP_AP_GATEWAY


def test_drop_then_recover_resets_failure_count():
    store = _configured_store()
    wlan = FakeWlan(True, ip="10.0.0.8")
    coordinator, events, ticks = _coordinator(store, wlan=wlan)

    coordinator.tick()
    coordinator.tick()
    assert coordinator.mode == MODE_STATION_ONLINE

    # Force one terminal fail count without leaving online permanently.
    coordinator._station_failure_count = 2

    wlan.connected = False
    ticks.now = 100
    coordinator.tick()  # detect drop → arm reconnect
    assert coordinator.mode == MODE_STATION_CONNECTING
    coordinator.tick()  # begin reconnect
    wlan.connected = True
    ticks.now = 150
    coordinator.tick()
    assert coordinator.mode == MODE_STATION_ONLINE
    assert coordinator._station_failure_count == 0
    assert events[-1].ip == "10.0.0.8"


def test_three_post_drop_failures_enter_setup_ap():
    store = _configured_store()
    wlan = FakeWlan(True)
    ap = FakeApWlan()
    events = []
    ticks = FakeTicks()
    coordinator, events, ticks = _coordinator(
        store, wlan=wlan, events=events, ticks=ticks, ap=ap
    )
    coordinator.tick()
    coordinator.tick()
    assert coordinator.mode == MODE_STATION_ONLINE

    wlan.connected = False
    for attempt in range(3):
        ticks.now = ticks.ticks_add(ticks.now, 10)
        coordinator.tick()  # drop watch or gap wait / begin
        if coordinator._station_attempt_armed is False and (
            coordinator.mode == MODE_STATION_CONNECTING
        ):
            coordinator.tick()  # begin if only armed last tick
        ticks.now = ticks.ticks_add(
            ticks.now, config.SYNC_COMMAND_DEADLINE_MS
        )
        coordinator.tick()
        if attempt < 2:
            assert coordinator.mode == MODE_STATION_CONNECTING
            ticks.now = ticks.ticks_add(
                ticks.now, config.STATION_RECONNECT_GAP_MS
            )

    assert coordinator.mode == MODE_SETUP_AP
    assert coordinator._station_failure_count == 3
    assert ap.active_value is True
    setup = [e for e in events if e.kind == EVENT_SETUP_STATUS]
    assert setup
    assert setup[-1].ssid == SETUP_AP_SSID
    assert setup[-1].ip == SETUP_AP_GATEWAY


def test_candidate_persist_success_resets_failure_count():
    """Persist-gated online emit clears the counter (setup join path)."""
    from src.device.web.router import SetupCandidate

    store = _configured_store()
    wlan = FakeWlan(False, ip="192.168.1.9")
    events = []
    ticks = FakeTicks()
    coordinator = NetworkCoordinator(
        Mailbox(),
        wlan=wlan,
        ap_wlan=FakeApWlan(),
        settings_store=store,
        event_sink=events,
        ticks_module=ticks,
    )
    coordinator._station_failure_count = 2
    coordinator._mode = MODE_SETUP_AP
    coordinator._setup_ap_active = True
    candidate = SetupCandidate("NewNet", "password1", "admin-secret")
    coordinator._start_candidate(candidate, ticks.now)
    coordinator.tick()  # issue candidate connect
    wlan.connected = True
    for _ in range(160):
        coordinator.tick()  # complete join + bounded verifier + persist
        if coordinator.mode == MODE_STATION_ONLINE:
            break
    assert coordinator.mode == MODE_STATION_ONLINE
    assert coordinator._station_failure_count == 0
    online = [
        e
        for e in events
        if e.kind == EVENT_STATION_STATUS and e.mode == MODE_STATION_ONLINE
    ]
    assert online
    assert online[-1].ip == "192.168.1.9"


def test_station_error_events_do_not_carry_secrets():
    store = _configured_store(wifi_password="password1")
    wlan = FakeWlan(False)
    coordinator, events, ticks = _coordinator(store, wlan=wlan)
    coordinator.tick()
    ticks.now = config.SYNC_COMMAND_DEADLINE_MS
    coordinator.tick()
    err = [e for e in events if e.kind == EVENT_STATION_ERROR]
    assert err
    assert err[-1].error_code in ("join_timeout", "join_fail")
    assert not hasattr(err[-1], "wifi_password")
    assert err[-1].ip is None


class _IdleHttp:
    """Minimal station-web stub: always listening, never serves a client."""

    has_held_client = False

    def ensure_listening(self):
        return True

    def tick(self, *_args, **_kwargs):
        return None

    def __init__(self):
        self.close_all_calls = 0

    def close_all(self):
        self.close_all_calls += 1

    def close_clients(self):
        pass


class _FakeKdfJob:
    """Minimal in-flight KDF job stub: tracks whether it was cancelled."""

    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def _online_store_coordinator(socket=None, ticks=None, events=None):
    """Configured station-online coordinator wired for a mailbox NTP command."""
    store = _configured_store(wifi_ssid="HomeNet", wifi_password="password1")
    ticks = ticks if ticks is not None else FakeTicks()
    wlan = FakeWlan(True, ip="10.0.0.9")
    events = events if events is not None else []
    coordinator = NetworkCoordinator(
        Mailbox(),
        wlan=wlan,
        ap_wlan=FakeApWlan(),
        settings_store=store,
        event_sink=events,
        ticks_module=ticks,
        http_server=_IdleHttp(),
        socket_module=socket,
    )
    coordinator.tick()  # begin store attempt (emit connecting)
    coordinator.tick()  # already associated -> online
    assert coordinator.mode == MODE_STATION_ONLINE
    return coordinator, events, ticks, wlan


def test_single_online_sync_failure_does_not_disconnect_station():
    """A lone sync failure (e.g. blocked/unreachable NTP server) must not
    disconnect an otherwise healthy station link -- the device's NTP server
    is one fixed address, not a pool, so this is a routine, expected outcome
    that must never make the station admin HTTP page unreachable."""
    ticks = FakeTicks()
    socket = FakeSocketModule(recv_exc=OSError(113, "unreachable"))
    coordinator, events, ticks, wlan = _online_store_coordinator(
        socket=socket, ticks=ticks
    )
    coordinator._mailbox.enqueue(SyncCommand(1, 100))

    coordinator.tick()  # take command; already associated -> state=start_ntp
    coordinator.tick()  # send NTP request -> state=recv_ntp
    coordinator.tick()  # recv fails -> ntp_fail -> _handle_online_sync_failure

    assert coordinator._online_sync_fail_streak == 1
    assert coordinator._station_failure_count == 0
    assert coordinator.mode == MODE_STATION_ONLINE
    assert wlan.disconnect_calls == 0

    result = coordinator._mailbox.try_take_result()
    assert result is not None
    assert result.ok is False
    assert result.error_code == "ntp_fail"


def test_online_sync_failure_streak_arms_reconnect_without_touching_setup_ap_counter():
    """Matrix: STREAK_LIMIT consecutive sync failures -> one bounded reconnect,
    but the SETUP_AP failure counter is never touched by an NTP-only streak."""
    ticks = FakeTicks()
    socket = FakeSocketModule(recv_exc=OSError(113, "unreachable"))
    coordinator, events, ticks, wlan = _online_store_coordinator(
        socket=socket, ticks=ticks
    )

    for _ in range(config.STATION_ONLINE_SYNC_FAILURE_STREAK_LIMIT):
        coordinator._mailbox.enqueue(SyncCommand(1, 100))
        coordinator.tick()
        coordinator.tick()
        coordinator.tick()
        coordinator._mailbox.try_take_result()

    assert coordinator.mode == MODE_STATION_CONNECTING
    assert coordinator._online_sync_fail_streak == 0
    assert coordinator._station_failure_count == 0
    assert wlan.disconnect_calls == 1


def test_online_sync_failure_cancels_inflight_config_auth():
    """Matrix: config-auth in flight -> cancelled/closed once the streak escalates.

    Exercises ``_handle_online_sync_failure`` directly: the coordinator's own
    dispatch (``_tick_station_config``) never lets the mailbox NTP state
    machine reach ``_finish`` while a KDF job is mid-flight (it claims the
    tick's budget first), so a real held-client-plus-KDF-job moment cannot be
    driven through ``tick()`` alone -- this isolates the abort/close sequence
    the method itself must run whenever it fires.
    """
    ticks = FakeTicks()
    coordinator, events, ticks, wlan = _online_store_coordinator(ticks=ticks)
    coordinator._online_sync_fail_streak = (
        config.STATION_ONLINE_SYNC_FAILURE_STREAK_LIMIT - 1
    )
    kdf_job = _FakeKdfJob()
    coordinator._kdf_job = kdf_job
    coordinator._kdf_acting_session_id = "sess-1"
    http = coordinator._http

    coordinator._handle_online_sync_failure("ntp_fail")

    assert kdf_job.cancelled is True
    assert coordinator._kdf_job is None
    assert coordinator._kdf_acting_session_id is None
    assert http.close_all_calls == 1
    assert coordinator._station_failure_count == 0
    assert coordinator._online_sync_fail_streak == 0
    assert coordinator.mode == MODE_STATION_CONNECTING


def test_online_sync_failure_reconnect_succeeds_resets_streak():
    """Matrix: forced reconnect (from an escalated sync-failure streak)
    succeeds -> streak resets, SETUP_AP counter was never touched."""
    ticks = FakeTicks()
    socket = FakeSocketModule(recv_exc=OSError(113, "unreachable"))
    coordinator, events, ticks, wlan = _online_store_coordinator(
        socket=socket, ticks=ticks
    )
    for _ in range(config.STATION_ONLINE_SYNC_FAILURE_STREAK_LIMIT):
        coordinator._mailbox.enqueue(SyncCommand(1, 100))
        coordinator.tick()
        coordinator.tick()
        coordinator.tick()
        coordinator._mailbox.try_take_result()
    assert coordinator.mode == MODE_STATION_CONNECTING
    assert coordinator._station_failure_count == 0

    coordinator.tick()  # begin the rearmed store attempt
    wlan.connected = True
    ticks.now = ticks.ticks_add(ticks.now, 10)
    coordinator.tick()  # observe already-associated -> online

    assert coordinator.mode == MODE_STATION_ONLINE
    assert coordinator._station_failure_count == 0
    assert coordinator._online_sync_fail_streak == 0
    online = [
        e
        for e in events
        if e.kind == EVENT_STATION_STATUS and e.mode == MODE_STATION_ONLINE
    ]
    assert online
    assert online[-1].ip == "10.0.0.9"


def test_permanently_unreachable_ntp_never_reaches_setup_ap():
    """Regression: an NTP server that never answers (but a healthy, always-
    rejoinable station link) must never accumulate toward SETUP_AP and must
    only disconnect the station once per streak, not on every failure."""
    ticks = FakeTicks()
    socket = FakeSocketModule(recv_exc=OSError(113, "unreachable"))
    coordinator, events, ticks, wlan = _online_store_coordinator(
        socket=socket, ticks=ticks
    )

    streaks = 4  # far more than STATION_FAILURE_LIMIT worth of failures
    for _ in range(streaks):
        for _ in range(config.STATION_ONLINE_SYNC_FAILURE_STREAK_LIMIT):
            coordinator._mailbox.enqueue(SyncCommand(1, 100))
            coordinator.tick()
            coordinator.tick()
            coordinator.tick()
            coordinator._mailbox.try_take_result()
        assert coordinator.mode == MODE_STATION_CONNECTING
        coordinator.tick()  # begin the rearmed (always-healthy) rejoin
        wlan.connected = True
        ticks.now = ticks.ticks_add(ticks.now, 10)
        coordinator.tick()  # rejoin succeeds -> back online
        assert coordinator.mode == MODE_STATION_ONLINE

    assert coordinator._station_failure_count == 0
    assert wlan.disconnect_calls == streaks


def test_repeated_sync_failure_streaks_still_reach_setup_ap_via_real_join_failures():
    """A genuinely dead link: each escalated reconnect's real join attempt
    also fails -> the existing join-failure counter (untouched by this
    story) still reaches SETUP_AP, proving the zombie-link case still
    recovers even though NTP failures alone never drive that counter."""
    ticks = FakeTicks()
    socket = FakeSocketModule(recv_exc=OSError(113, "unreachable"))
    coordinator, events, ticks, wlan = _online_store_coordinator(
        socket=socket, ticks=ticks
    )

    for attempt in range(config.STATION_FAILURE_LIMIT):
        for _ in range(config.STATION_ONLINE_SYNC_FAILURE_STREAK_LIMIT):
            coordinator._mailbox.enqueue(SyncCommand(1, 100))
            coordinator.tick()
            coordinator.tick()
            coordinator.tick()
            coordinator._mailbox.try_take_result()
        assert coordinator.mode == MODE_STATION_CONNECTING
        # The escalated reconnect's own join now fails for real (zombie link).
        ticks.now = ticks.ticks_add(ticks.now, config.SYNC_COMMAND_DEADLINE_MS)
        coordinator.tick()  # begin
        ticks.now = ticks.ticks_add(ticks.now, config.SYNC_COMMAND_DEADLINE_MS)
        coordinator.tick()  # terminal join timeout -> _fail_store_station
        if attempt < config.STATION_FAILURE_LIMIT - 1:
            assert coordinator.mode == MODE_STATION_CONNECTING
            ticks.now = ticks.ticks_add(ticks.now, config.STATION_RECONNECT_GAP_MS)

    assert coordinator._station_failure_count == config.STATION_FAILURE_LIMIT
    assert coordinator.mode == MODE_SETUP_AP
    setup = [e for e in events if e.kind == EVENT_SETUP_STATUS]
    assert setup
    assert setup[-1].ssid == SETUP_AP_SSID
    assert setup[-1].ip == SETUP_AP_GATEWAY


def test_finish_fatal_mailbox_saturation_skips_online_sync_failure_handling():
    """A fatal mailbox-saturation result must not also advance the streak."""
    ticks = FakeTicks()
    coordinator, events, ticks, wlan = _online_store_coordinator(ticks=ticks)
    coordinator._online_sync_fail_streak = (
        config.STATION_ONLINE_SYNC_FAILURE_STREAK_LIMIT - 1
    )
    coordinator._command = SyncCommand(1, 100)
    coordinator._take_epoch = coordinator._mailbox.epoch
    # Pre-occupy the result slot so publish_result raises MailboxSaturationError.
    coordinator._mailbox.occupy_result(SyncResult(99, True, None, None))

    coordinator._finish(False, None, "ntp_fail")

    assert coordinator.fatal is not None
    assert coordinator._online_sync_fail_streak == (
        config.STATION_ONLINE_SYNC_FAILURE_STREAK_LIMIT - 1
    )
    assert coordinator._station_failure_count == 0
    assert coordinator.mode == MODE_STATION_ONLINE
    assert wlan.disconnect_calls == 0


def test_proof_1_3_checklist_records_coexistence_fields():
    """Matrix: coexistence proof checklist exists with empty device rows."""
    path = (
        ROOT
        / "_bmad-output"
        / "implementation-artifacts"
        / "wifi-config"
        / "proof-1-3-sta-ap-coexistence.md"
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    for required in (
        "STA/AP coexistence",
        "192.168.4.1",
        "Scan during AP",
        "Bounded socket fairness",
        "Browser terminal responses",
        "Flash commits",
        "TFT Setup overlay",
        "TFT station IP overlay",
        "UNSUPPORTED",
        "PENDING",
    ):
        assert required in text
    # Device observation cells must not be pre-filled as PASS from host.
    assert "Do **not** invent on-device results from" in text
