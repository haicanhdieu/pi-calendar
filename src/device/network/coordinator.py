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
    next_station_failure_count,
    reset_station_failure_count,
    setup_ap_error_event,
    setup_ap_status_event,
    station_error_event,
    station_failures_exhausted,
    station_status_event,
)
from src.device.settings_store import SettingsCommitError
from src.device.web import pages
from src.provisioning.kdf_job import (
    DERIVE_OK,
    PURPOSE_LOGIN_VERIFY,
    PURPOSE_PASSWORD_CHANGE_DERIVE,
    VERIFY_OK,
    KdfJob,
)
from src.provisioning.scan import ssids_from_scan_rows
from src.provisioning.session import SessionTable
from src.provisioning.validation import COLOR_SCHEME_V1
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
        self._station_failure_count = reset_station_failure_count()
        self._station_ssid = None
        self._station_password = None
        self._station_deadline = None
        self._station_started = False
        self._station_next_attempt = None
        self._station_attempt_armed = False
        self._sessions = SessionTable(ticks_module=self._ticks)
        self._kdf_job = None
        self._kdf_correlation = 0
        self._kdf_acting_session_id = None

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
            self._tick_store_station(now)
            return
        if self._mode == MODE_STATION_ONLINE and self._settings_store is not None:
            if self._watch_station_drop(now):
                return
            if self._tick_station_config(now):
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
                    # Legacy secrets path only: store STA owns association when
                    # SettingsStore is present (story 1.3).
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

    def _load_store_wifi(self):
        store = self._settings_store
        if store is None:
            return None, None
        try:
            settings = store.load()
        except Exception:
            return None, None
        if not settings:
            return None, None
        ssid = settings.get("wifi_ssid")
        password = settings.get("wifi_password")
        if not ssid or not password:
            return None, None
        return str(ssid), str(password)

    def _arm_store_station_attempt(self, now, defer_ms=0):
        """Schedule a store-credential station attempt (boot or reconnect)."""
        self._mode = MODE_STATION_CONNECTING
        self._station_started = False
        self._station_attempt_armed = False
        self._station_deadline = None
        if defer_ms > 0:
            self._station_next_attempt = self._ticks.ticks_add(now, defer_ms)
        else:
            self._station_next_attempt = now

    def _begin_store_station_attempt(self, now):
        ssid, password = self._load_store_wifi()
        if not ssid or not password:
            self._fail_store_station(ERROR_JOIN_FAIL, ssid=None)
            return
        self._station_ssid = ssid
        self._station_password = password
        self._station_deadline = self._ticks.ticks_add(
            now, config.SYNC_COMMAND_DEADLINE_MS
        )
        self._station_started = False
        self._station_attempt_armed = True
        self._station_next_attempt = None
        self._mode = MODE_STATION_CONNECTING
        try:
            self._emit(
                station_status_event(
                    mode=MODE_STATION_CONNECTING, ssid=ssid
                )
            )
        except Exception:
            pass

    def _tick_store_station(self, now):
        """Bounded store-credential STA connect/reconnect (no candidate)."""
        if not self._station_attempt_armed:
            next_at = self._station_next_attempt
            if next_at is not None and self._ticks.ticks_diff(now, next_at) < 0:
                return
            self._begin_store_station_attempt(now)
            return

        if self._ticks.ticks_diff(now, self._station_deadline) >= 0:
            self._fail_store_station(ERROR_JOIN_TIMEOUT, self._station_ssid)
            return

        try:
            wlan = self._get_wlan()
            if not self._station_started:
                wlan.active(True)
                if wlan.isconnected():
                    self._station_started = True
                    self._complete_store_station_success()
                    return
                wlan.connect(self._station_ssid, self._station_password)
                self._station_started = True
                return
            if not wlan.isconnected():
                return
        except Exception:
            self._fail_store_station(ERROR_JOIN_FAIL, self._station_ssid)
            return

        self._complete_store_station_success()

    def _complete_store_station_success(self):
        ssid = self._station_ssid
        ip = None
        try:
            ip = self._station_ip()
        except Exception:
            ip = None
        self._station_failure_count = reset_station_failure_count()
        self._clear_store_station_attempt()
        self._mode = MODE_STATION_ONLINE
        try:
            self._emit(
                station_status_event(
                    mode=MODE_STATION_ONLINE, ssid=ssid, ip=ip
                )
            )
        except Exception:
            pass

    def _fail_store_station(self, error_code, ssid):
        self._disconnect_station()
        self._station_failure_count = next_station_failure_count(
            self._station_failure_count
        )
        self._clear_store_station_attempt()
        try:
            self._emit(
                station_error_event(
                    error_code,
                    mode=MODE_STATION_CONNECTING,
                    ssid=ssid,
                )
            )
        except Exception:
            pass
        if station_failures_exhausted(self._station_failure_count):
            self._enter_setup_ap_from_failures()
            return
        # Schedule the next bounded reconnect attempt.
        now = self._ticks.ticks_ms()
        self._arm_store_station_attempt(now, config.STATION_RECONNECT_GAP_MS)

    def _enter_setup_ap_from_failures(self):
        self._mode = MODE_SETUP_AP
        self._setup_ap_active = False
        self._setup_error_emitted = False
        self._clear_store_station_attempt()
        # Emit setup_status immediately so App clears any station-IP overlay
        # on the same loop step (do not wait for the next SETUP_AP tick).
        self._activate_setup_ap()

    def _clear_store_station_attempt(self):
        self._station_ssid = None
        self._station_password = None
        self._station_deadline = None
        self._station_started = False
        self._station_attempt_armed = False
        self._station_next_attempt = None

    def _watch_station_drop(self, now):
        """If a formerly-online station drops, start a reconnect attempt."""
        try:
            if self._get_wlan().isconnected():
                return False
        except Exception:
            # Treat WLAN probe failure as a drop requiring reconnect.
            pass
        self._abort_config_auth()
        self._arm_store_station_attempt(now, 0)
        return True

    def _abort_config_auth(self):
        """Cancel mid-flight login/password-change KDF and drop held clients."""
        job = self._kdf_job
        self._kdf_job = None
        self._kdf_acting_session_id = None
        if job is not None:
            try:
                job.cancel()
            except Exception:
                pass
        if self._http is not None:
            try:
                self._http.close_all()
            except Exception:
                pass

    def _tick_station_config(self, now):
        """
        Serve Config HTTP and advance at most one KDF job while online.

        Returns True when this tick consumed the config-auth budget (so the
        mailbox NTP path should wait). Idle HTTP with no KDF returns False.
        """
        kdf_active = self._kdf_job is not None
        if kdf_active:
            result = self._kdf_job.step(config.KDF_ROUNDS_PER_TICK)
            if result is not None:
                purpose = self._kdf_job.purpose
                if purpose == PURPOSE_PASSWORD_CHANGE_DERIVE:
                    self._finish_password_change_kdf(result, now)
                else:
                    self._finish_login_kdf(result, now)

        http = self._http
        if http is None:
            return kdf_active

        if not http.ensure_listening():
            return kdf_active

        action = http.tick(
            MODE_STATION_ONLINE,
            candidate_active=False,
            scan_fn=None,
            session_table=self._sessions,
            now_ticks=now,
            kdf_busy=self._kdf_job is not None,
        )
        if action is None:
            return kdf_active
        kind, payload = action
        if kind == "login_kdf":
            if self._kdf_job is not None:
                self._wipe_bytearray(payload)
                http.queue_held_response(pages.response_busy())
                return True
            self._start_login_kdf(payload, now)
            return True
        if kind == "password_change_kdf":
            password_ba, acting_id = payload
            if self._kdf_job is not None:
                self._wipe_bytearray(password_ba)
                http.queue_held_response(pages.response_busy())
                return True
            self._start_password_change_kdf(password_ba, acting_id, now)
            return True
        return True

    def _start_login_kdf(self, password_ba, now):
        salt_hex, verifier_hex = self._load_admin_verifier()
        self._kdf_correlation = int(self._kdf_correlation) + 1
        self._kdf_acting_session_id = None
        if salt_hex is None or verifier_hex is None:
            self._wipe_bytearray(password_ba)
            if self._http is not None:
                self._http.queue_held_response(
                    pages.response_login_page(incorrect=True)
                )
            return
        self._kdf_job = KdfJob(
            self._kdf_correlation,
            PURPOSE_LOGIN_VERIFY,
            password_ba,
            salt_hex,
            verifier_hex,
        )
        # Password ownership transferred into the job (wiped on terminal).
        if self._kdf_job.done:
            self._finish_login_kdf(self._kdf_job.result, now)

    def _start_password_change_kdf(self, password_ba, acting_id, now):
        self._kdf_correlation = int(self._kdf_correlation) + 1
        self._kdf_acting_session_id = acting_id
        store = self._settings_store
        if store is None:
            self._wipe_bytearray(password_ba)
            self._kdf_acting_session_id = None
            if self._http is not None:
                self._http.queue_held_response(pages.response_settings_page())
            return
        self._kdf_job = KdfJob(
            self._kdf_correlation,
            PURPOSE_PASSWORD_CHANGE_DERIVE,
            password_ba,
        )
        if self._kdf_job.done:
            self._finish_password_change_kdf(self._kdf_job.result, now)

    def _finish_login_kdf(self, result, now):
        job = self._kdf_job
        self._kdf_job = None
        self._kdf_acting_session_id = None
        if job is not None and not job.done:
            try:
                job.cancel()
            except Exception:
                pass

        http = self._http
        held = http is not None and http.has_held_client
        if result == VERIFY_OK and held:
            session_id = self._sessions.create(now)
            if session_id is None:
                response = pages.response_busy()
            else:
                response = pages.response_login_success(session_id)
            if not http.queue_held_response(response):
                # Peer closed between create and queue — drop orphan session.
                if session_id is not None:
                    self._sessions._entries = [
                        e
                        for e in self._sessions._entries
                        if e.encoded_id != session_id
                    ]
            return

        if result == VERIFY_OK and not held:
            # Peer aborted mid-KDF: wipe already done via job terminal; no session.
            return

        response = pages.response_login_page(incorrect=True)
        if held:
            http.queue_held_response(response)

    def _finish_password_change_kdf(self, result, now):
        job = self._kdf_job
        acting_id = self._kdf_acting_session_id
        self._kdf_job = None
        self._kdf_acting_session_id = None
        if job is not None and not job.done:
            try:
                job.cancel()
            except Exception:
                pass

        http = self._http
        held = http is not None and http.has_held_client
        if result != DERIVE_OK or job is None:
            if held:
                http.queue_held_response(pages.response_settings_page())
            return

        salt_hex = job.salt_hex
        verifier_hex = job.verifier_hex
        if not salt_hex or not verifier_hex:
            if held:
                http.queue_held_response(pages.response_settings_page())
            return

        committed = self._commit_password_change(salt_hex, verifier_hex)
        if not committed:
            # Fail-closed: old verifier and every session unchanged.
            if held:
                http.queue_held_response(pages.response_settings_page())
            return

        if acting_id is not None:
            self._sessions.keep_only(acting_id, now)

        if held:
            http.queue_held_response(
                pages.response_settings_page(password_changed=True)
            )

    def _commit_password_change(self, salt_hex, verifier_hex):
        store = self._settings_store
        if store is None:
            return False
        try:
            settings = store.load()
        except Exception:
            return False
        if not settings:
            return False
        ssid = settings.get("wifi_ssid")
        wifi_password = settings.get("wifi_password")
        if not ssid or not wifi_password:
            return False
        try:
            store.commit(
                wifi_ssid=ssid,
                wifi_password=wifi_password,
                admin_salt_hex=salt_hex,
                admin_verifier_hex=verifier_hex,
                color_scheme=COLOR_SCHEME_V1,
            )
        except SettingsCommitError:
            return False
        except Exception:
            return False
        return True

    def _load_admin_verifier(self):
        store = self._settings_store
        if store is None:
            return None, None
        try:
            settings = store.load()
        except Exception:
            return None, None
        if not settings:
            return None, None
        version = settings.get("admin_verifier_version")
        salt = settings.get("admin_salt")
        verifier = settings.get("admin_verifier")
        if version != "pbkdf2-sha256-v1":
            return None, None
        if not salt or not verifier:
            return None, None
        return str(salt), str(verifier)

    @staticmethod
    def _wipe_bytearray(buf):
        if isinstance(buf, bytearray):
            for i in range(len(buf)):
                buf[i] = 0

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
        self._station_failure_count = reset_station_failure_count()
        self._clear_store_station_attempt()
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
        # Prefer SettingsStore Wi-Fi when present (story 1.3); secrets is legacy.
        if self._settings_store is not None:
            ssid, password = self._load_store_wifi()
            if ssid and password:
                self._ssid = ssid
                self._password = password
                return True
            return False
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
