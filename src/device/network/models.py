"""Network mode constants and typed NetworkEvent values.

Pure module: no ``machine``, ``network``, or socket imports.
Constants come from ``src.config`` so they cannot drift.
"""

from src import config

MODE_BOOT = "BOOT"
MODE_STATION_CONNECTING = "STATION_CONNECTING"
MODE_STATION_ONLINE = "STATION_ONLINE"
MODE_SETUP_AP = "SETUP_AP"

EVENT_SETUP_STATUS = "setup_status"
EVENT_SETUP_ERROR = "setup_error"
EVENT_STATION_STATUS = "station_status"
EVENT_STATION_ERROR = "station_error"

SETUP_AP_SSID = config.SETUP_AP_SSID
SETUP_AP_GATEWAY = config.SETUP_AP_GATEWAY

# Named join / persist / busy codes (story 1.2)
ERROR_AP_FAIL = "ap_fail"
ERROR_JOIN_FAIL = "join_fail"
ERROR_JOIN_TIMEOUT = "join_timeout"
ERROR_PERSIST_FAIL = "persist_fail"
ERROR_BUSY = "busy"
ERROR_SCAN_FAIL = "scan_fail"


def boot_mode_for_settings(configured):
    """Pure boot transition: unconfigured → SETUP_AP, else STATION_CONNECTING."""
    if configured:
        return MODE_STATION_CONNECTING
    return MODE_SETUP_AP


def ntp_sync_enabled(mode, credentials_ok):
    """True only when not in SETUP_AP and credentials soft-check passed."""
    return mode != MODE_SETUP_AP and bool(credentials_ok)


def next_station_failure_count(current_count):
    """Increment consecutive terminal station failures (pure)."""
    return int(current_count) + 1


def station_failures_exhausted(count, limit=None):
    """True when consecutive terminal failures reach the setup fallback limit."""
    if limit is None:
        limit = config.STATION_FAILURE_LIMIT
    return int(count) >= int(limit)


def reset_station_failure_count():
    """Failure count after a successful persist/online station path."""
    return 0


def make_settings_coordinator(mailbox, settings_store, event_sink, **kwargs):
    """Composition helper: NetworkCoordinator wired to SettingsStore + event sink."""
    from src.device.network.coordinator import NetworkCoordinator

    return NetworkCoordinator(
        mailbox,
        settings_store=settings_store,
        event_sink=event_sink,
        **kwargs,
    )


class NetworkEvent:
    """Immutable coordinator → App event (App wiring is a later story)."""

    __slots__ = ("kind", "mode", "ssid", "ip", "error_code")

    def __init__(self, kind, mode=None, ssid=None, ip=None, error_code=None):
        self.kind = kind
        self.mode = mode
        self.ssid = ssid
        self.ip = ip
        self.error_code = error_code

    def __eq__(self, other):
        if not isinstance(other, NetworkEvent):
            return NotImplemented
        return (
            self.kind == other.kind
            and self.mode == other.mode
            and self.ssid == other.ssid
            and self.ip == other.ip
            and self.error_code == other.error_code
        )

    def __repr__(self):
        return (
            "NetworkEvent(kind={!r}, mode={!r}, ssid={!r}, ip={!r}, "
            "error_code={!r})"
        ).format(self.kind, self.mode, self.ssid, self.ip, self.error_code)


def setup_ap_status_event():
    """Golden SETUP_AP status event (SSID + gateway, no display calls)."""
    return NetworkEvent(
        EVENT_SETUP_STATUS,
        mode=MODE_SETUP_AP,
        ssid=SETUP_AP_SSID,
        ip=SETUP_AP_GATEWAY,
    )


def setup_ap_error_event(error_code):
    """Named SETUP_AP failure without crashing the coordinator."""
    return NetworkEvent(
        EVENT_SETUP_ERROR,
        mode=MODE_SETUP_AP,
        ssid=SETUP_AP_SSID,
        error_code=error_code,
    )


def station_status_event(mode=MODE_STATION_ONLINE, ssid=None, ip=None):
    """Station online/connecting status without App/TFT mutation."""
    return NetworkEvent(
        EVENT_STATION_STATUS,
        mode=mode,
        ssid=ssid,
        ip=ip,
    )


def station_error_event(error_code, mode=MODE_SETUP_AP, ssid=None):
    """Named station join/persist failure (no crash, no secret payload)."""
    return NetworkEvent(
        EVENT_STATION_ERROR,
        mode=mode,
        ssid=ssid,
        error_code=error_code,
    )
