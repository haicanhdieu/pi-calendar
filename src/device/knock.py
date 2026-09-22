"""Clock-mode port-80 knock listener: answer once, then hand over to config mode.

Clock mode runs no web stack at all. This module is the whole of its HTTP
presence: a bare listening socket that accepts a connection, writes one
module-level constant, closes, sets the config-mode flag and asks the caller
to reboot. It never parses a request, so it never needs the parser, the
router, the pages, sessions or the KDF -- the modules whose combined residency
is what made the settings page fail (issue #2).

It lives outside ``src/device/web`` on purpose: that package's ``__init__``
exports ``SetupHttpServer``, so importing anything from inside it would drag
the whole bounded HTTP server into clock mode -- measured at 17,696 bytes of
simulated heap, which is most of what this split exists to save.

It must never import ``machine``: the reboot is the caller's job, signalled by
``tick()``.
"""

from src import config

_BODY = (
    b'<!doctype html><html lang="en"><head><meta charset="utf-8">'
    b'<meta http-equiv="refresh" content="12">'
    b"<title>Pi Calendar</title></head><body>"
    b"<h1>Entering config mode</h1>"
    b"<p>The device is restarting into its settings mode. "
    b"This page reloads by itself in a few seconds.</p>"
    b"</body></html>"
)

# Content-Length matters here more than on any other response: the reset
# follows immediately, so a client reading until close sees the connection
# drop mid-body and reports a truncated response. With the length declared,
# it knows it already has the whole page.
_RESPONSE = (
    b"HTTP/1.0 200 OK\r\n"
    b"Content-Type: text/html; charset=utf-8\r\n"
    b"Content-Length: " + str(len(_BODY)).encode("ascii") + b"\r\n"
    b"Connection: close\r\n\r\n" + _BODY
)

_WOULD_BLOCK_ERRNOS = (11, 35, 10035)


class ConfigModeKnock:
    """Non-blocking listener whose only answer is 'rebooting into config'."""

    def __init__(self, socket_module=None, port=None, flag_writer=None):
        self._socket_module = socket_module
        self._port = config.HTTP_LISTEN_PORT if port is None else int(port)
        self._flag_writer = flag_writer
        self._listen = None
        self.last_failure_phase = None

    def _get_socket_module(self):
        if self._socket_module is None:
            import socket

            self._socket_module = socket
        return self._socket_module

    @staticmethod
    def _would_block(exc):
        args = getattr(exc, "args", None)
        return bool(args) and args[0] in _WOULD_BLOCK_ERRNOS

    def ensure_listening(self):
        """Bind the listening socket once; False means try again later."""
        if self._listen is not None:
            return True
        sock = None
        try:
            socket = self._get_socket_module()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception:
                pass
            sock.bind(("0.0.0.0", self._port))
            sock.listen(config.HTTP_LISTEN_BACKLOG)
            try:
                sock.setblocking(False)
            except AttributeError:
                sock.settimeout(0)
            self._listen = sock
            self.last_failure_phase = None
            return True
        except Exception as exc:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
            self._listen = None
            self.last_failure_phase = (
                "knock_listen_memory" if isinstance(exc, MemoryError) else "knock_listen"
            )
            return False

    def close(self):
        """Release the listening socket so another owner can bind port 80."""
        if self._listen is None:
            return
        try:
            self._listen.close()
        except Exception:
            pass
        self._listen = None

    @classmethod
    def _send_all(cls, conn, max_steps=16):
        """Bounded write of the one fixed response.

        A socket accepted from a non-blocking listener is itself non-blocking
        on MicroPython, and the very first ``send`` to a browser reliably
        raises EAGAIN there -- which is why an earlier version of this reset
        the device without the interstitial ever reaching the page. Give the
        connection a short timeout instead: this path ends in a reset either
        way, so the only thing a bounded wait costs is those milliseconds.
        """
        try:
            conn.settimeout(2)
        except (AttributeError, OSError):
            try:
                conn.setblocking(True)
            except Exception:
                pass
        offset = 0
        total = len(_RESPONSE)
        for _ in range(int(max_steps)):
            if offset >= total:
                return True
            try:
                sent = conn.send(_RESPONSE[offset:])
            except OSError as exc:
                if cls._would_block(exc):
                    continue
                return False
            except Exception:
                return False
            if sent is None:
                return True
            sent = int(sent)
            if sent <= 0:
                return False
            offset += sent
        return offset >= total

    def _write_flag(self):
        writer = self._flag_writer
        if writer is None:
            from src.device.mode_flag import request_config_mode

            writer = request_config_mode
        try:
            return bool(writer())
        except Exception:
            return False

    def tick(self):
        """Poll once. True means: flag written, reboot into config mode now."""
        if not self.ensure_listening():
            return False
        try:
            conn, _addr = self._listen.accept()
        except OSError as exc:
            if self._would_block(exc):
                return False
            return False
        except Exception:
            return False

        # The browser's request bytes are never read: any connection at all is
        # the signal. Not reading is what keeps this path allocation-free.
        self._send_all(conn)
        try:
            conn.close()
        except Exception:
            pass

        if not self._write_flag():
            # Without the flag the reboot would land back in clock mode, so
            # stay put and let the next knock try again.
            return False
        self.close()
        return True
