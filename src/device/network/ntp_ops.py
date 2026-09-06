"""Real WLAN / DNS / UDP NTP ops for the AD-8 network worker.

Owns blocking network I/O only. Returns ``SyncResult``; never calls
``ntptime.settime()``; never touches RTC, TFT, or ``AppState``.

Network imports are lazy so host AST / import checks can load this module
without MicroPython's ``network`` package.
"""

import struct
import time

from src.calendar.gregorian import weekday_from_ymd
from src.device.network.mailbox import SyncResult
from src.time.model import DateTime
from src.ticks import ticks_add, ticks_diff, ticks_ms

# Seconds between NTP era (1900-01-01) and Unix epoch (1970-01-01).
_NTP_DELTA = 2208988800

# Default public NTP pool (non-secret).
_NTP_HOST = "pool.ntp.org"
_NTP_PORT = 123

# Poll budgets for STA connect (ms). Keep wifi+recv under SYNC_COMMAND_DEADLINE_MS.
_WIFI_POLL_MS = 200
_WIFI_CONNECT_BUDGET_MS = 10_000
_NTP_RECV_TIMEOUT_S = 2
_NTP_RECV_TIMEOUT_FLOOR_S = 0.05


class NtpOps:
    """
    Injectable worker ops: ``run(command) -> SyncResult``.

    Optional ``wlan`` / ``socket_module`` / ``secrets_mod`` hooks exist for
    host fakes; production uses MicroPython ``network`` + ``socket`` +
    device-local ``secrets``.
    """

    def __init__(
        self,
        wlan=None,
        socket_module=None,
        secrets_mod=None,
        ntp_host=_NTP_HOST,
        log=None,
    ):
        self._wlan = wlan
        self._socket_module = socket_module
        self._secrets_mod = secrets_mod
        self._ntp_host = ntp_host
        self._log = log if log is not None else print

    def run(self, command):
        """Execute one bounded sync attempt for ``command``."""
        if self._past_deadline(command):
            return self._fail(command, "deadline")

        try:
            self._ensure_wifi(command)
        except _OpsError as exc:
            return self._fail(command, exc.code)

        if self._past_deadline(command):
            return self._fail(command, "deadline")

        try:
            utc = self._query_ntp(command)
        except _OpsError as exc:
            return self._fail(command, exc.code)

        if self._past_deadline(command):
            return self._fail(command, "deadline")

        return SyncResult(command.command_id, True, utc, None)

    def _fail(self, command, error_code):
        return SyncResult(command.command_id, False, None, error_code)

    @staticmethod
    def _past_deadline(command):
        return ticks_diff(ticks_ms(), command.deadline_ms) >= 0

    def _load_secrets(self):
        if self._secrets_mod is not None:
            return self._secrets_mod
        try:
            import secrets as secrets_mod
        except Exception as exc:  # noqa: BLE001 — soft-fail to wifi error
            raise _OpsError("wifi_fail") from exc
        return secrets_mod

    def _get_wlan(self):
        if self._wlan is not None:
            return self._wlan
        try:
            import network
        except Exception as exc:  # noqa: BLE001
            raise _OpsError("wifi_fail") from exc
        return network.WLAN(network.STA_IF)

    def _get_socket(self):
        if self._socket_module is not None:
            return self._socket_module
        try:
            import socket
        except Exception as exc:  # noqa: BLE001
            raise _OpsError("dns_fail") from exc
        return socket

    def _ensure_wifi(self, command):
        secrets_mod = self._load_secrets()
        try:
            ssid = getattr(secrets_mod, "WIFI_SSID", None) or ""
            password = getattr(secrets_mod, "WIFI_PASSWORD", None) or ""
            ssid = str(ssid).strip()
            password = str(password).strip()
        except Exception as exc:  # noqa: BLE001
            raise _OpsError("wifi_fail") from exc
        if not ssid or not password:
            raise _OpsError("wifi_fail")

        wlan = self._get_wlan()
        try:
            if not wlan.active():
                wlan.active(True)
            if wlan.isconnected():
                return
            wlan.connect(ssid, password)
        except Exception as exc:  # noqa: BLE001
            raise _OpsError("wifi_fail") from exc

        wifi_deadline = ticks_add(ticks_ms(), _WIFI_CONNECT_BUDGET_MS)
        while True:
            if self._past_deadline(command):
                raise _OpsError("deadline")
            try:
                if wlan.isconnected():
                    return
            except Exception as exc:  # noqa: BLE001
                raise _OpsError("wifi_fail") from exc
            if ticks_diff(ticks_ms(), wifi_deadline) >= 0:
                raise _OpsError("wifi_fail")
            self._sleep_ms(_WIFI_POLL_MS)

    def _query_ntp(self, command):
        socket = self._get_socket()
        try:
            addr_info = socket.getaddrinfo(self._ntp_host, _NTP_PORT)
            if not addr_info:
                raise _OpsError("dns_fail")
            addr = addr_info[0][-1]
        except _OpsError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _OpsError("dns_fail") from exc

        if self._past_deadline(command):
            raise _OpsError("deadline")

        sock = None
        data = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self._recv_timeout_s(command))
            # LI=0, VN=3, Mode=3 (client) — standard 48-byte NTP request.
            msg = b"\x1b" + (47 * b"\x00")
            sock.sendto(msg, addr)
            if self._past_deadline(command):
                raise _OpsError("deadline")
            data = sock.recvfrom(48)[0]
        except _OpsError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _OpsError("ntp_fail") from exc
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:  # noqa: BLE001
                    pass

        if self._past_deadline(command):
            raise _OpsError("deadline")

        if data is None or len(data) < 48:
            raise _OpsError("ntp_fail")

        # LI==3 (alarm) or stratum 0 (Kiss-o'-Death) are not usable time.
        li = (data[0] >> 6) & 0x03
        stratum = data[1]
        if li == 3 or stratum == 0:
            raise _OpsError("ntp_fail")

        try:
            # Transmit Timestamp seconds (bytes 40–43), big-endian.
            ntp_seconds = struct.unpack("!I", data[40:44])[0]
        except Exception as exc:  # noqa: BLE001
            raise _OpsError("ntp_fail") from exc

        unix_seconds = int(ntp_seconds) - _NTP_DELTA
        if unix_seconds < 0:
            raise _OpsError("ntp_fail")
        return self._unix_to_datetime(unix_seconds)

    def _recv_timeout_s(self, command):
        """Clamp UDP recv timeout to remaining SyncCommand deadline."""
        remaining_ms = ticks_diff(command.deadline_ms, ticks_ms())
        if remaining_ms <= 0:
            raise _OpsError("deadline")
        timeout_s = remaining_ms / 1000.0
        if timeout_s > _NTP_RECV_TIMEOUT_S:
            timeout_s = _NTP_RECV_TIMEOUT_S
        if timeout_s < _NTP_RECV_TIMEOUT_FLOOR_S:
            timeout_s = _NTP_RECV_TIMEOUT_FLOOR_S
        return timeout_s

    @staticmethod
    def _unix_to_datetime(unix_seconds):
        try:
            tm = time.gmtime(unix_seconds)
        except Exception as exc:  # noqa: BLE001
            raise _OpsError("ntp_fail") from exc
        year = int(tm[0])
        month = int(tm[1])
        day = int(tm[2])
        hour = int(tm[3])
        minute = int(tm[4])
        second = int(tm[5])
        weekday = weekday_from_ymd(year, month, day)
        return DateTime(year, month, day, weekday, hour, minute, second)

    @staticmethod
    def _sleep_ms(ms):
        try:
            from time import sleep_ms

            sleep_ms(ms)
        except ImportError:
            time.sleep(ms / 1000.0)


class _OpsError(Exception):
    """Internal soft-fail carrying a SyncResult error_code."""

    def __init__(self, code):
        Exception.__init__(self, code)
        self.code = code
