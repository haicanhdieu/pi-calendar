"""Bounded incremental HTTP server for setup/config (socket I/O injected).

Owns listen/client sockets only. Pure parse/route/page policy lives in sibling
modules. Never imports ``machine``/``network``; ``socket`` is injected or
imported lazily for the device path.
"""

from src import config
from src.device.web.http_parse import IncrementalHttpParser
from src.device.web import setup_pages as pages
from src.device.web.setup_router import (
    ACTION_CONNECT,
    ACTION_RESPOND,
    ACTION_SCAN,
    route_setup_request,
    scan_response,
)

_WOULD_BLOCK_ERRNOS = (11, 35, 10035)


class WebResourceError(Exception):
    """A compact, named construction or listener failure."""

    def __init__(self, phase):
        self.phase = phase


class _Client:
    __slots__ = (
        "sock",
        "parser",
        "outbox",
        "out_offset",
        "closing",
        "held",
        "peer",
    )

    def __init__(self, sock):
        self.sock = sock
        self.parser = IncrementalHttpParser()
        self.outbox = None
        self.out_offset = 0
        self.closing = False
        self.held = False
        self.peer = None


class SetupHttpServer:
    """Accept/read/write at most one bounded step per ``tick``."""

    def __init__(
        self,
        socket_module=None,
        max_clients=None,
        per_tick_bytes=None,
        port=None,
    ):
        self._socket_module = socket_module
        self._max_clients = (
            config.HTTP_MAX_CLIENTS if max_clients is None else int(max_clients)
        )
        self._per_tick_bytes = (
            config.HTTP_PER_TICK_BYTES
            if per_tick_bytes is None
            else int(per_tick_bytes)
        )
        self._port = config.HTTP_LISTEN_PORT if port is None else int(port)
        self._listen = None
        self._clients = []
        self._held_client = None
        self.last_failure_phase = None

    @property
    def has_held_client(self):
        return self._held_client is not None

    @property
    def has_clients(self):
        """Whether a browser has reached this server (without allocating auth)."""
        return bool(self._clients)

    def _get_socket_module(self):
        if self._socket_module is None:
            import socket

            self._socket_module = socket
        return self._socket_module

    def ensure_listening(self):
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
            return True
        except MemoryError:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
            self.last_failure_phase = "listen_memory"
            self._listen = None
            return False
        except Exception:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
            self.last_failure_phase = "listen"
            self._listen = None
            return False

    def close_all(self):
        held = self._held_client
        self._held_client = None
        for client in list(self._clients):
            self._close_client(client)
        self._clients = []
        listen = self._listen
        self._listen = None
        if listen is not None:
            try:
                listen.close()
            except Exception:
                pass
        return held

    def close_non_held_clients(self):
        """Drop a failed request without losing the setup candidate reply."""
        for client in tuple(self._clients):
            if client is not self._held_client:
                self._close_client(client)

    def tick(
        self,
        mode,
        candidate_active,
        scan_fn,
        session_table=None,
        now_ticks=None,
        kdf_busy=False,
    ):
        """
        Advance one bounded unit of HTTP work.

        Setup mode may return ``(\"connect\", candidate)``. Config mode may
        return ``(\"login_kdf\", password_bytearray)`` or
        ``(\"password_change_kdf\", (password_bytearray, acting_session_id))``.
        Otherwise ``None``.
        """
        if self._listen is None:
            return None
        self._try_accept()
        # Prefer draining write buffers, then read one client.
        for client in list(self._clients):
            if client.outbox is not None:
                self._write_client(client)
                return None
        for client in list(self._clients):
            if client.held:
                self._poll_held_peer(client)
        for client in list(self._clients):
            if client.held or client.closing:
                continue
            result = self._read_client(
                client,
                mode,
                candidate_active,
                scan_fn,
                session_table,
                now_ticks,
                kdf_busy,
            )
            if result is not None:
                return result
            return None
        return None

    def queue_held_response(self, response_bytes):
        """Flush a terminal response to the held Connect/login client."""
        client = self._held_client
        if client is None:
            return False
        client.held = False
        self._held_client = None
        client.outbox = response_bytes
        client.out_offset = 0
        client.closing = True
        return True

    def drain_writes(self, max_steps=32):
        """Advance pending response writes without accepting new work."""
        for _ in range(int(max_steps)):
            pending = False
            for client in list(self._clients):
                if client.outbox is not None:
                    pending = True
                    self._write_client(client)
                    break
            if not pending:
                return

    def _try_accept(self):
        if len(self._clients) >= self._max_clients:
            return
        try:
            conn, addr = self._listen.accept()
        except OSError as exc:
            if self._would_block(exc):
                return
            return
        except Exception:
            return
        try:
            conn.setblocking(False)
        except AttributeError:
            try:
                conn.settimeout(0)
            except Exception:
                pass
        except Exception:
            pass
        client = _Client(conn)
        client.peer = addr
        self._clients.append(client)

    def _poll_held_peer(self, client):
        """Release held Connect/login slot when the peer closes mid-work."""
        try:
            data = client.sock.recv(self._per_tick_bytes)
        except OSError as exc:
            if self._would_block(exc):
                return
            self._close_client(client)
            return
        except Exception:
            self._close_client(client)
            return
        if not data:
            self._close_client(client)

    def _read_client(
        self,
        client,
        mode,
        candidate_active,
        scan_fn,
        session_table,
        now_ticks,
        kdf_busy,
    ):
        try:
            data = client.sock.recv(self._per_tick_bytes)
        except OSError as exc:
            if self._would_block(exc):
                return None
            self._close_client(client)
            return None
        except Exception:
            self._close_client(client)
            return None
        if not data:
            self._close_client(client)
            return None

        request, error, _consumed = client.parser.feed(data)
        if error is not None:
            client.outbox = pages.response_for_parse_error(error)
            client.out_offset = 0
            client.closing = True
            return None
        if request is None:
            return None

        if mode == "STATION_ONLINE":
            return self._dispatch_config(
                client, request, session_table, now_ticks, kdf_busy
            )
        return self._dispatch_setup(client, request, mode, candidate_active, scan_fn)

    def _dispatch_setup(self, client, request, mode, candidate_active, scan_fn):
        routed = route_setup_request(request, mode, candidate_active)
        if routed.action == ACTION_RESPOND:
            client.outbox = routed.response
            client.out_offset = 0
            client.closing = True
            return None
        if routed.action == ACTION_SCAN:
            try:
                ssids = list(scan_fn() if scan_fn is not None else [])
            except Exception:
                ssids = []
            client.outbox = scan_response(ssids)
            client.out_offset = 0
            client.closing = True
            return None
        if routed.action == ACTION_CONNECT:
            if self._held_client is not None:
                client.outbox = pages.response_busy()
                client.out_offset = 0
                client.closing = True
                return None
            client.held = True
            self._held_client = client
            return ("connect", routed.candidate)
        client.outbox = pages.response_not_found()
        client.out_offset = 0
        client.closing = True
        return None

    def _dispatch_config(self, client, request, session_table, now_ticks, kdf_busy):
        # Admin routing/pages are intentionally imported only after a browser
        # reaches the station-online surface.
        from src.device.web import pages as config_pages
        from src.device.web.router import (
            ACTION_LOGIN_KDF, ACTION_PASSWORD_CHANGE_KDF, route_config_request,
        )
        if callable(session_table) and request.path in ("/", "/settings"):
            session_table = session_table()
        if now_ticks is None:
            client.outbox = config_pages.response_not_found()
            client.out_offset = 0
            client.closing = True
            return None
        routed = route_config_request(
            request,
            "STATION_ONLINE",
            session_table,
            now_ticks,
            kdf_busy=bool(kdf_busy) or self._held_client is not None,
        )
        if routed.action == ACTION_RESPOND:
            if routed.renew_session_id is not None:
                try:
                    session_table.renew(routed.renew_session_id, now_ticks)
                except Exception:
                    pass
            client.outbox = routed.response
            client.out_offset = 0
            client.closing = True
            return None
        if routed.action == ACTION_LOGIN_KDF:
            # Body already cleared on the request; drop parser copy too.
            try:
                client.parser.body = b""
            except Exception:
                pass
            if self._held_client is not None:
                self._wipe_password(routed.password)
                client.outbox = config_pages.response_busy()
                client.out_offset = 0
                client.closing = True
                return None
            client.held = True
            self._held_client = client
            return ("login_kdf", routed.password)
        if routed.action == ACTION_PASSWORD_CHANGE_KDF:
            try:
                client.parser.body = b""
            except Exception:
                pass
            acting_id = routed.renew_session_id
            if acting_id is not None:
                try:
                    session_table.renew(acting_id, now_ticks)
                except Exception:
                    pass
            if self._held_client is not None:
                self._wipe_password(routed.password)
                client.outbox = config_pages.response_busy()
                client.out_offset = 0
                client.closing = True
                return None
            client.held = True
            self._held_client = client
            return ("password_change_kdf", (routed.password, acting_id))
        self._wipe_password(getattr(routed, "password", None))
        client.outbox = config_pages.response_not_found()
        client.out_offset = 0
        client.closing = True
        return None

    @staticmethod
    def _wipe_password(password):
        if isinstance(password, bytearray):
            for i in range(len(password)):
                password[i] = 0

    def _write_client(self, client):
        outbox = client.outbox
        if outbox is None:
            return
        remaining = outbox[client.out_offset :]
        chunk = remaining[: self._per_tick_bytes]
        if not chunk:
            self._close_client(client)
            return
        try:
            sent = client.sock.send(chunk)
        except OSError as exc:
            if self._would_block(exc):
                return
            self._close_client(client)
            return
        except Exception:
            self._close_client(client)
            return
        if sent is None:
            sent = len(chunk)
        client.out_offset += int(sent)
        if client.out_offset >= len(outbox):
            self._close_client(client)

    def _close_client(self, client):
        if client is self._held_client:
            self._held_client = None
        if client in self._clients:
            self._clients.remove(client)
        try:
            client.sock.close()
        except Exception:
            pass
        client.outbox = None
        client.held = False

    @staticmethod
    def _would_block(exc):
        code = getattr(exc, "errno", None)
        if code is None and exc.args:
            code = exc.args[0]
        return code in _WOULD_BLOCK_ERRNOS
