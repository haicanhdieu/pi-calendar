"""Host tests for pure setup HTTP parse/route and scan decode policy."""

import ast
from pathlib import Path
import subprocess
import sys

from src.device.web.http_parse import (
    ERR_MALFORMED,
    ERR_TOO_LARGE,
    ERR_UNSUPPORTED,
    IncrementalHttpParser,
    html_escape,
    parse_form_urlencoded,
)
from src.device.web.router import (
    ACTION_CONNECT,
    ACTION_RESPOND,
    ACTION_SCAN,
    route_setup_request,
)
from src.device.web import pages
from src.device.web import setup_pages
from src.device.web.setup_router import route_setup_request as route_production_setup
from src.provisioning.scan import decode_ssid, ssids_from_scan_rows
from src.provisioning.validation import validate_setup_form_fields

_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN = frozenset({"machine", "network", "socket", "ntptime"})


def _feed_all(raw, **limits):
    parser = IncrementalHttpParser(**limits)
    req, err, _ = parser.feed(raw)
    return req, err


def test_html_escape_and_form_parse():
    assert html_escape('<a&b>"') == "&lt;a&amp;b&gt;&quot;"
    assert parse_form_urlencoded(b"ssid=Home&wifi_password=secret12&admin_password=adminpass") == {
        "ssid": "Home",
        "wifi_password": "secret12",
        "admin_password": "adminpass",
    }
    assert parse_form_urlencoded(b"a=%zz") is None
    assert parse_form_urlencoded("ssid=Café&wifi_password=secret12") == {
        "ssid": "Café", "wifi_password": "secret12"
    }


def test_setup_assets_keep_scan_flow_and_escape_json_controls():
    html = pages.setup_page_html({"status": "failure", "ssid": "Home"})
    assert "fetch(" not in html
    assert "Couldn't join Home" in html
    assert '<select id="ssid" name="ssid" required>' in html
    assert 'href="/"' in html
    assert 'minlength="8" maxlength="63"' in html
    assert 'name="wifi_password"' in html
    assert 'name="admin_password"' in html
    assert '<form method="POST" action="/connect">' in html
    response = setup_pages.response_scan_json(['a\n\t"\\\x01'])
    assert b'a\\n\\t\\"\\\\\\u0001' in response


def test_scan_response_accepts_an_iterable_without_copying_it():
    response = setup_pages.response_scan_json(iter(("Home", "Cafe")))
    assert b'{"ssids":["Home","Cafe"]}' in response


def test_scan_response_stream_matches_json_response():
    from src.device.web.scan_response import scan_response_stream, scan_response_chunk
    response = scan_response_stream(("Home", "Cafe"))
    raw = b"".join(
        scan_response_chunk(response, index, index + 64)
        for index in range(0, response[1], 64)
    )
    assert b'{"ssids":["Home","Cafe"]}' in raw


def test_setup_server_import_does_not_load_config_assets_or_auth():
    """The AP server's import footprint excludes admin-only resources."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import src.device.web.server; "
            "assert 'src.device.web.pages' not in sys.modules; "
            "assert 'src.device.web.router' not in sys.modules; "
            "assert 'src.provisioning.session' not in sys.modules; "
            "assert 'src.provisioning.kdf_job' not in sys.modules",
        ],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_incremental_get_and_oversized_line():
    raw = b"GET / HTTP/1.1\r\nHost: x\r\n\r\n"
    req, err = _feed_all(raw)
    assert err is None
    assert req.method == "GET"
    assert req.path == "/"

    big = b"GET /" + (b"a" * 300) + b" HTTP/1.1\r\n\r\n"
    req, err = _feed_all(big, max_request_line=64)
    assert req is None
    assert err == ERR_TOO_LARGE


def test_unsupported_version_and_malformed():
    req, err = _feed_all(b"GET / HTTP/2.0\r\n\r\n")
    assert err == ERR_UNSUPPORTED
    req, err = _feed_all(b"NOTAREQUEST\r\n\r\n")
    assert err == ERR_MALFORMED


def test_post_body_bounded():
    body = "ssid=ab&wifi_password=password1&admin_password=password1"
    raw = (
        "POST /connect HTTP/1.1\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        "Content-Length: {}\r\n\r\n{}"
    ).format(len(body), body).encode("ascii")
    req, err = _feed_all(raw)
    assert err is None
    assert req.method == "POST"
    assert req.body.decode() == body

    raw_over = (
        "POST /connect HTTP/1.1\r\n"
        "Content-Length: 50\r\n\r\n" + ("x" * 50)
    ).encode("ascii")
    req, err = _feed_all(raw_over, max_body=16)
    assert err == ERR_TOO_LARGE


def test_route_allowlist_and_connect_candidate():
    class Req:
        def __init__(self, method, path, headers=None, body=b""):
            self.method = method
            self.path = path
            self.headers = headers or {}
            self.body = body

    r = route_setup_request(Req("GET", "/"), "SETUP_AP", False)
    assert r.action == ACTION_SCAN

    r = route_setup_request(Req("GET", "/scan"), "SETUP_AP", False)
    assert r.action == ACTION_SCAN

    r = route_setup_request(Req("GET", "/login"), "SETUP_AP", False)
    assert r.action == ACTION_RESPOND
    assert b"404" in r.response

    r = route_setup_request(Req("GET", "/"), "STATION_ONLINE", False)
    assert b"404" in r.response

    body = b"ssid=HomeNet&wifi_password=password1&admin_password=password1"
    r = route_setup_request(
        Req(
            "POST",
            "/connect",
            {"content-type": "application/x-www-form-urlencoded"},
            body,
        ),
        "SETUP_AP",
        False,
    )
    assert r.action == ACTION_CONNECT
    assert r.candidate.ssid == "HomeNet"

    r = route_setup_request(
        Req(
            "POST",
            "/connect",
            {"content-type": "application/x-www-form-urlencoded"},
            body,
        ),
        "SETUP_AP",
        True,
    )
    assert r.action == ACTION_RESPOND
    assert b"503" in r.response


def test_production_setup_router_accepts_native_form_and_reopens_invalid_form():
    class Req:
        def __init__(self, body, content_type="application/x-www-form-urlencoded; charset=UTF-8"):
            self.method = "POST"
            self.path = "/connect"
            self.headers = {"content-type": content_type}
            self.body = body

    r = route_production_setup(
        Req("ssid=Café&wifi_password=password1&admin_password=adminpass"),
        "SETUP_AP", False,
    )
    assert r.action == "connect"
    assert r.candidate.ssid == "Café"

    r = route_production_setup(
        Req(b"ssid=Home&wifi_password=short&admin_password=adminpass"),
        "SETUP_AP", False,
    )
    assert r.action == "respond"
    assert b"200 OK" in r.response
    assert b"passwords between 8 and 63" in r.response


def test_setup_page_has_tokens_and_a11y():
    html = pages.setup_page_html()
    assert "#12161c" in html
    assert "#7c6cf6" in html
    assert "aria-live" in html
    assert "min-height:44px" in html
    assert "Connecting…" in pages.setup_page_html({"status": "connecting"})
    assert "No networks found" in html
    assert "charAt(0)===" not in html

    failure = pages.setup_page_html(
        {"status": "failure", "ssid": "HomeNet", "admin_password": "adminpass"}
    )
    assert "Couldn't join HomeNet" in failure
    assert 'value="adminpass"' in failure
    assert 'value=""' in failure
    assert '<option value="HomeNet" selected>HomeNet</option>' in failure


def test_scan_decode_dedupe_omits_bad():
    assert decode_ssid(b"Home") == "Home"
    assert decode_ssid(b"\xff\xfe") is None
    assert decode_ssid(b"") is None
    rows = [
        (b"Home", b"\x00" * 6, 1, -40, 3, False),
        (b"Home", b"\x01" * 6, 1, -50, 3, False),
        (b"\xff", b"\x02" * 6, 1, -60, 3, False),
        (b"Cafe", b"\x03" * 6, 1, -70, 3, False),
    ]
    assert ssids_from_scan_rows(rows) == ["Home", "Cafe"]


def test_validate_setup_form_fields():
    ok = validate_setup_form_fields("ssid", "password1", "adminpass")
    assert ok.ok is True
    assert validate_setup_form_fields("ssid", "short", "adminpass").ok is False
    assert validate_setup_form_fields("ssid", "password1", "short").ok is False
    assert validate_setup_form_fields("ssid", "password1", "").ok is False
    assert validate_setup_form_fields("", "password1", "adminpass").ok is False
    assert validate_setup_form_fields("x" * 33, "password1", "adminpass").ok is False

    class Req:
        def __init__(self, body):
            self.method = "POST"
            self.path = "/connect"
            self.headers = {"content-type": "application/x-www-form-urlencoded"}
            self.body = body

    bad_admin = route_setup_request(
        Req(b"ssid=Home&wifi_password=password1&admin_password=short"),
        "SETUP_AP",
        False,
    )
    assert bad_admin.action == ACTION_RESPOND
    assert b"400" in bad_admin.response

    bad_ssid = route_setup_request(
        Req(b"ssid=&wifi_password=password1&admin_password=password1"),
        "SETUP_AP",
        False,
    )
    assert bad_ssid.action == ACTION_RESPOND
    assert b"400" in bad_ssid.response
    assert bad_ssid.candidate is None

def test_pure_modules_forbid_device_imports():
    for rel in (
        "src/provisioning/validation.py",
        "src/provisioning/verifier.py",
        "src/provisioning/scan.py",
        "src/provisioning/session.py",
        "src/provisioning/kdf_job.py",
        "src/device/network/models.py",
        "src/device/web/http_parse.py",
        "src/device/web/router.py",
        "src/device/web/pages.py",
    ):
        source = (_ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in _FORBIDDEN
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module.split(".")[0] not in _FORBIDDEN
