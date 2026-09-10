"""Regression coverage for the memory-footprint ownership boundaries."""

import subprocess
import sys

from src.device.web.http_parse import IncrementalHttpParser
from src.device.web.server import SetupHttpServer
from src.device.web.scan_response import ResponseSource
from src.provisioning.kdf_job import KdfJob, PURPOSE_SETUP_DERIVE
from src.provisioning.setup_kdf import SetupKdfJob
from src.provisioning.verifier import pbkdf2_hmac_sha256


def test_cold_imports_do_not_pull_mode_or_crypto_modules():
    code = (
        "import sys; import src.provisioning.validation; "
        "import src.device.settings_store; import src.device.web.server; "
        "assert 'src.provisioning.verifier' not in sys.modules; "
        "assert 'hashlib' not in sys.modules; "
        "assert 'src.device.web.setup_router' not in sys.modules; "
        "assert 'src.device.web.page_setup_content' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_parser_release_drops_headers_and_body():
    parser = IncrementalHttpParser()
    request, error, _ = parser.feed(
        b"POST /connect HTTP/1.1\r\nContent-Length: 3\r\n\r\nabc"
    )
    assert error is None and request.body == b"abc"
    parser.release()
    assert parser.body == b"" and parser.headers == {}
    assert parser.path is None and parser.method is None


def test_kdf_cancel_is_terminal_and_compatible():
    password = bytearray(b"adminpass")
    job = KdfJob(1, PURPOSE_SETUP_DERIVE, password, iterations=20, urandom=lambda n: b"x" * n)
    assert job.cancel() == "DERIVE_CANCELLED"
    assert job.step(100) == "DERIVE_CANCELLED"
    assert job.done and all(value == 0 for value in password)


def test_setup_kdf_matches_pbkdf2_and_cancel_does_not_resume():
    password = bytearray(b"adminpass")
    job = SetupKdfJob(password, 3, urandom=lambda n: b"y" * n)
    assert job.step(1) is None
    assert job.step(10) == "DERIVE_OK"
    assert bytes.fromhex(job.verifier_hex) == pbkdf2_hmac_sha256(
        b"adminpass", b"y" * 16, iterations=3, dklen=32
    )
    assert job.step(10) == "DERIVE_OK"


class _PartialClient:
    def __init__(self, request, send_limit=3):
        self.inbox = bytearray(request)
        self.sent = bytearray()
        self.send_limit = send_limit
        self.closed = False
        self.send_sizes = []

    def setblocking(self, _value):
        pass

    def recv(self, size):
        if not self.inbox:
            return b""
        chunk = bytes(self.inbox[:size])
        del self.inbox[:size]
        return chunk

    def send(self, data):
        count = min(len(data), self.send_limit)
        self.send_sizes.append(count)
        self.sent.extend(data[:count])
        return count

    def close(self):
        self.closed = True


class _Listen:
    def __init__(self, client):
        self.client = client
        self.accepted = False

    def setblocking(self, _value):
        pass

    def bind(self, _address):
        pass

    def listen(self, _backlog):
        pass

    def accept(self):
        if self.accepted:
            raise OSError(11, "would block")
        self.accepted = True
        return self.client, ("127.0.0.1", 1)

    def close(self):
        pass


class _Sockets:
    AF_INET = SOCK_STREAM = SOL_SOCKET = SO_REUSEADDR = 1

    def __init__(self, client):
        self.listener = _Listen(client)

    def socket(self, *_args):
        return self.listener


def test_server_streams_exact_bytes_with_bounded_partial_sends():
    client = _PartialClient(b"GET /scan HTTP/1.1\r\nHost: x\r\n\r\n")
    server = SetupHttpServer(socket_module=_Sockets(client), per_tick_bytes=9)
    assert server.ensure_listening()
    for _ in range(200):
        server.tick("SETUP_AP", False, lambda force=False: ("Café", 'a"b'))
        if client.closed:
            break
    expected = b'"ssids":["Caf\xc3\xa9","a\\"b"]}'
    assert client.closed
    assert b"Content-Length:" in client.sent
    assert client.sent.endswith(expected)
    assert max(client.send_sizes) <= 3


def test_response_source_keeps_one_bounded_pending_chunk_and_closes():
    source = ResponseSource((b"header", "é" * 100))
    chunks = []
    while source.remaining:
        chunk = source.read(7)
        assert len(chunk) <= 7
        chunks.append(chunk)
    assert b"".join(chunks) == b"header" + ("é" * 100).encode("utf-8")
    source.close()
    assert source.closed and source.read(7) == b""


def _serve_once(path):
    client = _PartialClient(
        ("GET %s HTTP/1.1\r\nHost: x\r\n\r\n" % path).encode("ascii"), send_limit=4096
    )
    server = SetupHttpServer(socket_module=_Sockets(client), per_tick_bytes=4096)
    assert server.ensure_listening()
    forced = []

    def scan_fn(force=False):
        forced.append(force)
        return ("Home",)

    for _ in range(200):
        server.tick("SETUP_AP", False, scan_fn)
        if client.closed:
            break
    assert client.closed
    return forced, bytes(client.sent)


def test_page_load_reuses_the_cache_and_rescan_forces_a_fresh_scan():
    forced, page = _serve_once("/")
    assert forced == [False]
    assert b"<title>Pi Calendar Setup</title>" in page
    # The page's rescan control must reach the forcing route.
    assert b'href="/rescan"' in page

    forced, rescan_page = _serve_once("/rescan")
    assert forced == [True]
    assert b"<title>Pi Calendar Setup</title>" in rescan_page
    assert b"Home" in rescan_page
