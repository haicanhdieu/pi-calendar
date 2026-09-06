"""Cooperative, core-0 WLAN and NTP coordinator.

Each :meth:`tick` performs at most one state transition or non-blocking poll.
It deliberately has no wait loop, DNS lookup, or sleep call: the application
loop remains responsible for display cadence and is the only RTC writer.

Owns WLAN/socket objects and emits typed NetworkEvents. Never draws the TFT
or mutates App.
"""

import struct
import time

from src.calendar.gregorian import weekday_from_ymd
from src.device.network.mailbox import MailboxSaturationError, SyncResult
from src.device.network.models import (
    MODE_SETUP_AP,
    MODE_STATION_ONLINE,
    SETUP_AP_SSID,
    boot_mode_for_settings,
    setup_ap_error_event,
    setup_ap_status_event,
)
from src.time.model import DateTime
from src import ticks as default_ticks

_NTP_DELTA = 2208988800
_NTP_PACKET = b"\x1b" + (47 * b"\x00")
# errno values used by MicroPython, Unix, and Windows for non-blocking reads.
_WOULD_BLOCK_ERRNOS = (11, 35, 10035)


class NetworkCoordinator:
    """Tick-driven owner of WLAN association and a non-blocking NTP socket."""

    def __init__(
        self,
        mailbox,
        wlan=None,
        ap_wlan=None,
        socket_module=None,
        secrets_mod=None,
        ticks_module=None,
        ntp_address=("129.6.15.28", 123),
        log=None,
        settings_store=None,
        event_sink=None,
    ):
        self._mailbox = mailbox
        self._wlan = wlan
        self._ap_wlan = ap_wlan
        self._socket_module = socket_module
        self._secrets_mod = secrets_mod
        self._ticks = ticks_module if ticks_module is not None else default_ticks
        self._ntp_address = ntp_address
        self._log = log if log is not None else print
        self._settings_store = settings_store
        self._event_sink = event_sink
        self._command = None
        self._take_epoch = None
        self._state = "idle"
        self._sock = None
        self.fatal = None
        self._setup_ap_active = False
        self._setup_error_emitted = False
        self._mode = self._resolve_boot_mode()

    def _resolve_boot_mode(self):
        store = self._settings_store
        if store is None:
            # Legacy/host path without SettingsStore: keep mailbox NTP usable.
            return MODE_STATION_ONLINE
        configured = False
        try:
            configured = bool(store.is_configured())
        except Exception:
            configured = False
        return boot_mode_for_settings(configured)

    @property
    def mode(self):
        return self._mode

    @property
    def active(self):
        return self._command is not None

    def _emit(self, event):
        sink = self._event_sink
        if sink is None:
            return
        if callable(sink):
            sink(event)
        else:
            sink.append(event)

    def tick(self, now_ticks=None):
        """Advance one bounded unit of network work; never waits or sleeps."""
        if self._mode == MODE_SETUP_AP:
            self._tick_setup_ap()
            return

        now = self._ticks.ticks_ms() if now_ticks is None else int(now_ticks)
        if self._command is None:
            taken = self._mailbox.try_take_command()
            if taken is None:
                return
            self._command, self._take_epoch = taken
            if self._expired(now):
                self._finish(False, None, "deadline")
                return
            if not self._credentials_valid():
                self._finish(False, None, "wifi_fail")
                return
            try:
                wlan = self._get_wlan()
                wlan.active(True)
                if wlan.isconnected():
                    self._state = "start_ntp"
                else:
                    # This is intentionally the only association request.
                    wlan.connect(self._ssid, self._password)
                    self._state = "wifi"
            except Exception:
                self._finish(False, None, "wifi_fail")
            return

        if self._expired(now):
            self._finish(False, None, "deadline")
            return
        if self._state == "wifi":
            try:
                if self._get_wlan().isconnected():
                    self._state = "start_ntp"
            except Exception:
                self._finish(False, None, "wifi_fail")
            return
        if self._state == "start_ntp":
            self._start_ntp()
            return
        if self._state == "recv_ntp":
            self._poll_ntp()

    def _tick_setup_ap(self):
        """Activate open setup AP and emit typed status (no App/TFT calls)."""
        if self._setup_ap_active:
            return
        try:
            ap = self._get_ap_wlan()
            ap.config(essid=SETUP_AP_SSID, security=0)
            ap.active(True)
        except Exception:
            # Retry activation on later ticks; emit the named failure once.
            if not self._setup_error_emitted:
                self._setup_error_emitted = True
                try:
                    self._emit(setup_ap_error_event("ap_fail"))
                except Exception:
                    pass
            return
        try:
            self._emit(setup_ap_status_event())
            self._setup_ap_active = True
            self._setup_error_emitted = False
        except Exception:
            # AP is up but sink failed; retry status emit on a later tick.
            pass

    def _credentials_valid(self):
        try:
            secrets_mod = self._secrets_mod
            if secrets_mod is None:
                import secrets as secrets_mod
            self._ssid = str(getattr(secrets_mod, "WIFI_SSID", "") or "").strip()
            self._password = str(
                getattr(secrets_mod, "WIFI_PASSWORD", "") or ""
            ).strip()
            return bool(self._ssid and self._password)
        except Exception:
            return False

    def _get_wlan(self):
        if self._wlan is not None:
            return self._wlan
        import network

        self._wlan = network.WLAN(network.STA_IF)
        return self._wlan

    def _get_ap_wlan(self):
        if self._ap_wlan is not None:
            return self._ap_wlan
        import network

        self._ap_wlan = network.WLAN(network.AP_IF)
        return self._ap_wlan

    def _get_socket_module(self):
        if self._socket_module is None:
            import socket

            self._socket_module = socket
        return self._socket_module

    def _start_ntp(self):
        try:
            socket = self._get_socket_module()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock = sock
            try:
                sock.setblocking(False)
            except AttributeError:
                sock.settimeout(0)
            sock.sendto(_NTP_PACKET, self._ntp_address)
            self._state = "recv_ntp"
        except Exception:
            self._close_socket()
            self._finish(False, None, "ntp_fail")

    def _poll_ntp(self):
        try:
            data, sender = self._sock.recvfrom(48)
        except OSError as exc:
            if self._would_block(exc):
                return
            self._finish(False, None, "ntp_fail")
            return
        except Exception:
            self._finish(False, None, "ntp_fail")
            return
        if sender != self._ntp_address:
            self._finish(False, None, "ntp_fail")
            return
        try:
            utc = self.parse_response(data)
        except Exception:
            self._finish(False, None, "ntp_fail")
            return
        self._finish(True, utc, None)

    def _expired(self, now):
        return self._ticks.ticks_diff(now, self._command.deadline_ms) >= 0

    @staticmethod
    def _would_block(exc):
        code = getattr(exc, "errno", None)
        if code is None and exc.args:
            code = exc.args[0]
        return code in _WOULD_BLOCK_ERRNOS

    def _finish(self, ok, utc, error_code):
        command = self._command
        epoch = self._take_epoch
        self._close_socket()
        self._command = None
        self._take_epoch = None
        self._state = "idle"
        try:
            self._mailbox.publish_result(
                SyncResult(command.command_id, ok, utc, error_code), epoch
            )
        except MailboxSaturationError as exc:
            self.fatal = exc
            self._log("FATAL:MAILBOX_SATURATION", "result slot occupied")

    def _close_socket(self):
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    @staticmethod
    def parse_response(data):
        """Validate an NTP response and convert its transmit timestamp to UTC."""
        if data is None or len(data) < 48:
            raise ValueError("short NTP response")
        if (data[0] & 0x07) != 4:
            raise ValueError("non-server NTP response")
        if ((data[0] >> 6) & 0x03) == 3 or data[1] == 0:
            raise ValueError("invalid NTP response")
        ntp_seconds = struct.unpack("!I", data[40:44])[0]
        unix_seconds = int(ntp_seconds) - _NTP_DELTA
        if unix_seconds < 0:
            raise ValueError("invalid NTP timestamp")
        tm = time.gmtime(unix_seconds)
        return DateTime(
            int(tm[0]), int(tm[1]), int(tm[2]),
            weekday_from_ymd(int(tm[0]), int(tm[1]), int(tm[2])),
            int(tm[3]), int(tm[4]), int(tm[5]),
        )
