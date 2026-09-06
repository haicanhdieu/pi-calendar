"""Cooperative, core-0 WLAN and NTP coordinator.

Each :meth:`tick` performs at most one state transition or non-blocking poll.
It deliberately has no wait loop, DNS lookup, or sleep call: the application
loop remains responsible for display cadence and is the only RTC writer.

Owns WLAN/socket objects and emits typed NetworkEvents. Never draws the TFT
or mutates App.
"""

import struct
import time

from src import config
from src.calendar.gregorian import weekday_from_ymd
from src.device.network.mailbox import MailboxSaturationError, SyncResult
from src.device.network.models import (
    ERROR_JOIN_FAIL,
    ERROR_JOIN_TIMEOUT,
    ERROR_PERSIST_FAIL,
    MODE_SETUP_AP,
    MODE_STATION_CONNECTING,
    MODE_STATION_ONLINE,
    SETUP_AP_SSID,
    boot_mode_for_settings,
    setup_ap_error_event,
    setup_ap_status_event,
    station_error_event,
    station_status_event,
)
from src.device.settings_store import SettingsCommitError
from src.device.web import pages
from src.provisioning.scan import ssids_from_scan_rows
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
        http_server=None,
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
        self._http = http_server
        self._command = None
        self._take_epoch = None
        self._state = "idle"
        self._sock = None
        self.fatal = None
        self._setup_ap_active = False
        self._setup_error_emitted = False
        self._mode = self._resolve_boot_mode()
        self._candidate = None
        self._candidate_deadline = None
        self._candidate_started = False

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

    @property
    def candidate_active(self):
        return self._candidate is not None

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
        now = self._ticks.ticks_ms() if now_ticks is None else int(now_ticks)
        if self._mode == MODE_SETUP_AP:
            self._tick_setup_ap(now)
            return
        if self._mode == MODE_STATION_CONNECTING and self._candidate is not None:
            # Setup join handshake: keep AP + held Connect client through result.
            self._tick_candidate_join(now)
            return
        if self._mode == MODE_STATION_CONNECTING:
            return
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

    def _tick_setup_ap(self, now):
        """Activate open setup AP, serve setup HTTP, run one candidate join."""
        if not self._setup_ap_active:
            self._activate_setup_ap()
            return

        if self._candidate is not None:
            self._tick_candidate_join(now)
            return

        http = self._http
        if http is None:
            return
        if not http.ensure_listening():
            if not self._setup_error_emitted:
                self._setup_error_emitted = True
                try:
                    self._emit(setup_ap_error_event("listen_fail"))
                except Exception:
                    pass
            return
        action = http.tick(
            MODE_SETUP_AP,
            candidate_active=False,
            scan_fn=self._scan_ssids,
        )
        if action is None:
            return
        kind, candidate = action
        if kind != "connect" or candidate is None:
            return
        self._start_candidate(candidate, now)

    def _activate_setup_ap(self):
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

    def _scan_ssids(self):
        try:
            wlan = self._get_wlan()
            try:
                wlan.active(True)
            except Exception:
                pass
            rows = wlan.scan()
        except Exception:
            return []
        return ssids_from_scan_rows(rows)

    def _start_candidate(self, candidate, now):
        self._candidate = candidate
        self._candidate_started = False
        self._candidate_deadline = self._ticks.ticks_add(
            now, config.SYNC_COMMAND_DEADLINE_MS
        )
        self._mode = MODE_STATION_CONNECTING
        try:
            self._emit(
                station_status_event(
                    mode=MODE_STATION_CONNECTING, ssid=candidate.ssid
                )
            )
        except Exception:
            pass

    def _tick_candidate_join(self, now):
        candidate = self._candidate
        if candidate is None:
            return

        # Still serve HTTP so concurrent Connect receives 503 Busy.
        # Do not scan STA while a candidate join is in flight.
        http = self._http
        if http is not None:
            http.tick(
                MODE_SETUP_AP,
                candidate_active=True,
                scan_fn=lambda: [],
            )

        if self._ticks.ticks_diff(now, self._candidate_deadline) >= 0:
            self._fail_candidate(ERROR_JOIN_TIMEOUT)
            return

        try:
            wlan = self._get_wlan()
            if not self._candidate_started:
                wlan.active(True)
                wlan.connect(candidate.ssid, candidate.wifi_password)
                self._candidate_started = True
                return
            if not wlan.isconnected():
                return
        except Exception:
            self._fail_candidate(ERROR_JOIN_FAIL)
            return

        self._complete_candidate_success()

    def _complete_candidate_success(self):
        candidate = self._candidate
        store = self._settings_store
        ip = None
        try:
            ip = self._station_ip()
        except Exception:
            ip = None

        if store is None:
            self._fail_candidate(ERROR_PERSIST_FAIL)
            return

        try:
            store.commit(
                wifi_ssid=candidate.ssid,
                wifi_password=candidate.wifi_password,
                admin_password=candidate.admin_password,
            )
        except SettingsCommitError:
            self._disconnect_station()
            self._fail_candidate(ERROR_PERSIST_FAIL)
            return
        except Exception:
            self._disconnect_station()
            self._fail_candidate(ERROR_PERSIST_FAIL)
            return

        ssid = candidate.ssid
        # Order: emit online → flush browser success → close clients → drop AP.
        self._mode = MODE_STATION_ONLINE
        try:
            self._emit(
                station_status_event(
                    mode=MODE_STATION_ONLINE, ssid=ssid, ip=ip
                )
            )
        except Exception:
            pass

        response = pages.response_join_success(ssid)
        if self._http is not None:
            self._http.queue_held_response(response)
            self._http.drain_writes()
            self._http.close_all()
        self._deactivate_ap()
        self._clear_candidate()

    def _fail_candidate(self, error_code):
        candidate = self._candidate
        ssid = candidate.ssid if candidate is not None else None
        admin = candidate.admin_password if candidate is not None else ""
        self._disconnect_station()
        try:
            self._emit(
                station_error_event(
                    error_code, mode=MODE_SETUP_AP, ssid=ssid
                )
            )
        except Exception:
            pass

        body = pages.response_join_failure(ssid or "", admin or "")
        if self._http is not None:
            self._http.queue_held_response(body)
            self._http.drain_writes()

        self._mode = MODE_SETUP_AP
        self._clear_candidate()
        # AP stays up for retry; do not deactivate.

    def _clear_candidate(self):
        if self._candidate is not None:
            try:
                self._candidate.clear_secrets()
            except Exception:
                pass
        self._candidate = None
        self._candidate_deadline = None
        self._candidate_started = False

    def _disconnect_station(self):
        try:
            wlan = self._get_wlan()
            disconnect = getattr(wlan, "disconnect", None)
            if callable(disconnect):
                disconnect()
        except Exception:
            pass

    def _station_ip(self):
        wlan = self._get_wlan()
        ifconfig = getattr(wlan, "ifconfig", None)
        if not callable(ifconfig):
            return None
        cfg = ifconfig()
        if not cfg:
            return None
        return cfg[0]

    def _deactivate_ap(self):
        try:
            ap = self._get_ap_wlan()
            ap.active(False)
        except Exception:
            pass
        self._setup_ap_active = False

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
