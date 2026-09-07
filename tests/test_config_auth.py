"""Host tests for Config login, session gate, and cooperative KDF auth."""

import ast
from pathlib import Path

from src import config
from src.device.network.coordinator import NetworkCoordinator
from src.device.network.mailbox import Mailbox
from src.device.network.models import MODE_SETUP_AP, MODE_STATION_ONLINE
from src.device.web.http_parse import cookie_header_value
from src.device.web.router import (
    ACTION_LOGIN_KDF,
    ACTION_PASSWORD_CHANGE_KDF,
    ACTION_RESPOND,
    route_config_request,
    route_setup_request,
)
from src.device.web import pages
from src.device.web.server import SetupHttpServer
from src.device.settings_store import SettingsCommitError
from src.provisioning.kdf_job import (
    DERIVE_OK,
    PURPOSE_LOGIN_VERIFY,
    PURPOSE_PASSWORD_CHANGE_DERIVE,
    VERIFY_OK,
    VERIFY_REJECTED,
    KdfJob,
)
from src.provisioning.session import SessionTable
from src.provisioning.verifier import derive_admin_verifier, verify_admin_password

from tests.test_network_coordinator import FakeTicks, FakeWlan
from tests.test_setup_ap_coordinator import FakeApWlan
from tests.test_setup_candidate import (
    FakeStreamSocket,
    FakeTcpSocketModule,
)
from tests.test_settings_store import FakeFS, _record_bytes, _store

_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN = frozenset({"machine", "network", "socket", "ntptime"})


class Req:
    def __init__(self, method, path, headers=None, body=b""):
        self.method = method
        self.path = path
        self.headers = headers or {}
        self.body = body


def _salt_verifier(password="adminpass"):
    return derive_admin_verifier(password, salt=b"\x11" * 16)


def test_cookie_header_value_parse():
    assert cookie_header_value("pc_session=abc; other=1", "pc_session") == "abc"
    assert cookie_header_value("other=1; pc_session=xyz", "pc_session") == "xyz"
    assert cookie_header_value("pc_session=abc", "missing") is None
    assert cookie_header_value("", "pc_session") is None
    assert cookie_header_value(None, "pc_session") is None


def test_login_and_settings_pages_tokens():
    login = pages.login_page_html()
    assert "Log In" in login
    assert "Admin Password" in login
    assert "username" not in login.lower() or 'name="username"' not in login
    assert 'name="password"' in login
    assert "#12161c" in login
    assert "#7c6cf6" in login
    assert "min-height:44px" in login
    assert "Incorrect password" in pages.login_page_html(incorrect=True)
    assert "aria-live" in pages.login_page_html(incorrect=True)

    settings = pages.settings_page_html()
    assert "Device Settings" in settings
    assert "Admin Password" in settings
    assert "Color Scheme" in settings
    assert "Forest &amp; Amber" in settings
    assert 'aria-disabled="true"' in settings
    assert 'name="new_password"' in settings
    assert 'method="POST"' in settings
    assert 'action="/settings"' in settings
    assert "#12161c" in settings
    assert "min-height:44px" in settings
    assert "http://" not in settings
    assert "https://" not in settings
    assert "Password changed." not in settings

    changed = pages.settings_page_html(password_changed=True)
    assert "Password changed." in changed
    assert 'aria-live="polite"' in changed
    assert "banner success" in changed


def test_http_response_set_cookie_and_redirect():
    raw = pages.response_login_success("A" * 22)
    assert b"302" in raw
    assert b"Location: /settings" in raw
    assert b"Set-Cookie: pc_session=" in raw
    assert b"HttpOnly" in raw
    assert b"SameSite=Strict" in raw
    assert b"Path=/" in raw
    assert b"Max-Age" not in raw.split(b"Set-Cookie:")[1].split(b"\r\n")[0]

    cleared = pages.response_redirect_login(clear_cookie=True)
    assert b"Location: /login" in cleared
    assert b"Max-Age=0" in cleared


def test_route_config_mode_gate_and_unauth_redirect():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x01" * n)

    r = route_config_request(Req("GET", "/"), MODE_SETUP_AP, table, 0, False)
    assert b"404" in r.response

    r = route_setup_request(Req("GET", "/login"), MODE_STATION_ONLINE, False)
    assert b"404" in r.response

    r = route_config_request(Req("GET", "/"), MODE_STATION_ONLINE, table, 0, False)
    assert r.action == ACTION_RESPOND
    assert b"302" in r.response
    assert b"Location: /login" in r.response

    r = route_config_request(
        Req("GET", "/settings"), MODE_STATION_ONLINE, table, 0, False
    )
    assert b"Location: /login" in r.response

    r = route_config_request(
        Req("GET", "/login"), MODE_STATION_ONLINE, table, 0, False
    )
    assert b"Log In" in r.response
    assert b"username" not in r.response.lower() or b'name="username"' not in r.response


def test_route_protected_valid_and_expired_cookie():
    ticks = FakeTicks(0)
    table = SessionTable(
        idle_ms=100, ticks_module=ticks, urandom=lambda n: b"\x02" * n
    )
    sid = table.create(0)
    headers = {"cookie": "pc_session={}".format(sid)}

    r = route_config_request(
        Req("GET", "/settings", headers), MODE_STATION_ONLINE, table, 0, False
    )
    assert b"Device Settings" in r.response
    assert r.renew_session_id == sid

    r = route_config_request(
        Req("GET", "/settings", headers), MODE_STATION_ONLINE, table, 200, False
    )
    assert b"Location: /login" in r.response
    assert b"Max-Age=0" in r.response


def test_route_login_post_kdf_and_busy():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x03" * n)
    body = b"password=adminpass"
    headers = {"content-type": "application/x-www-form-urlencoded"}

    r = route_config_request(
        Req("POST", "/login", headers, body),
        MODE_STATION_ONLINE,
        table,
        0,
        False,
    )
    assert r.action == ACTION_LOGIN_KDF
    assert isinstance(r.password, bytearray)
    assert bytes(r.password) == b"adminpass"

    r = route_config_request(
        Req("POST", "/login", headers, body),
        MODE_STATION_ONLINE,
        table,
        0,
        True,
    )
    assert r.action == ACTION_RESPOND
    assert b"503" in r.response


def test_kdf_job_matches_full_verify_cooperatively():
    salt, verifier = _salt_verifier("secret12")
    assert verify_admin_password("secret12", salt, verifier) is True

    job = KdfJob(1, PURPOSE_LOGIN_VERIFY, bytearray(b"secret12"), salt, verifier)
    first = job.step(config.KDF_ROUNDS_PER_TICK)
    assert first is None
    assert job.done is False
    result = None
    steps = 1
    while result is None:
        result = job.step(config.KDF_ROUNDS_PER_TICK)
        steps += 1
        assert steps < 200  # 20000/200 = 100 steps max
    assert result == VERIFY_OK
    assert job._password is None

    bad = KdfJob(2, PURPOSE_LOGIN_VERIFY, bytearray(b"wrongpass"), salt, verifier)
    result = None
    while result is None:
        result = bad.step(200)
    assert result == VERIFY_REJECTED


def _online_coordinator(password="adminpass", ticks=None):
    salt, verifier = derive_admin_verifier(password, salt=b"\x44" * 16)
    fs = FakeFS(
        {
            ".settings-v1": _record_bytes(
                admin_salt=salt, admin_verifier=verifier
            )
        }
    )
    store = _store(fs)
    ticks = FakeTicks(0) if ticks is None else ticks
    sockets = FakeTcpSocketModule()
    http = SetupHttpServer(socket_module=sockets, per_tick_bytes=8192)
    wlan = FakeWlan(connected=True)
    coordinator = NetworkCoordinator(
        Mailbox(),
        wlan=wlan,
        ap_wlan=FakeApWlan(),
        settings_store=store,
        ticks_module=ticks,
        http_server=http,
        socket_module=sockets,
    )
    # Drive store STA to online.
    coordinator.tick()
    coordinator.tick()
    assert coordinator.mode == MODE_STATION_ONLINE
    return coordinator, http, sockets, ticks, store


def _http_get(path="/", cookie=None):
    lines = ["GET {} HTTP/1.1".format(path), "Host: 192.168.1.40"]
    if cookie:
        lines.append("Cookie: {}".format(cookie))
    lines.append("")
    lines.append("")
    return "\r\n".join(lines).encode("ascii")


def _http_login_post(password):
    body = "password={}".format(password)
    return (
        "POST /login HTTP/1.1\r\n"
        "Host: 192.168.1.40\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        "Content-Length: {}\r\n\r\n{}"
    ).format(len(body), body).encode("ascii")


def _pump(coordinator, pred, limit=250):
    for _ in range(limit):
        if pred():
            return True
        coordinator.tick()
    return pred()


def test_coordinator_unauth_redirect_and_setup_404():
    coordinator, http, sockets, ticks, _store = _online_coordinator()
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/settings"))
    assert _pump(coordinator, lambda: client.closed or b"302" in client.sent)
    assert b"Location: /login" in client.sent

    client2 = FakeStreamSocket()
    sockets.listen.enqueue(client2)
    client2.push_client_bytes(_http_get("/scan"))
    assert _pump(coordinator, lambda: client2.closed or len(client2.sent) > 0)
    assert b"404" in client2.sent


def test_coordinator_bad_password_no_session_cookie():
    coordinator, http, sockets, ticks, _store = _online_coordinator()
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_login_post("wrongpass1"))
    assert _pump(
        coordinator,
        lambda: b"Incorrect password" in client.sent,
        limit=300,
    )
    assert b"Set-Cookie: pc_session=" not in client.sent or b"Max-Age=0" in client.sent
    assert b"Incorrect password" in client.sent
    assert len(coordinator._sessions) == 0


def test_coordinator_good_login_sets_cookie_and_settings():
    coordinator, http, sockets, ticks, _store = _online_coordinator(
        password="adminpass"
    )
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_login_post("adminpass"))
    assert _pump(
        coordinator,
        lambda: b"Set-Cookie: pc_session=" in client.sent,
        limit=300,
    )
    assert b"302" in client.sent
    assert b"Location: /settings" in client.sent
    assert b"HttpOnly" in client.sent
    assert b"SameSite=Strict" in client.sent
    cookie_line = [
        line for line in client.sent.split(b"\r\n") if line.startswith(b"Set-Cookie:")
    ][0]
    assert b"Max-Age" not in cookie_line
    token = cookie_line.split(b"pc_session=", 1)[1].split(b";", 1)[0].decode("ascii")
    assert len(token) == 22

    # Advance before first authed GET so renew moves the idle deadline forward.
    ticks.now = 100
    authed = FakeStreamSocket()
    sockets.listen.enqueue(authed)
    authed.push_client_bytes(
        _http_get("/settings", cookie="pc_session={}".format(token))
    )
    assert _pump(coordinator, lambda: b"Device Settings" in authed.sent)
    assert b"Forest &amp; Amber" in authed.sent
    assert b"Admin Password" in authed.sent

    # Past the pre-renew deadline (login created at ~0 → idle 900000).
    ticks.now = config.SESSION_IDLE_MS + 1
    renewed = FakeStreamSocket()
    sockets.listen.enqueue(renewed)
    renewed.push_client_bytes(
        _http_get("/settings", cookie="pc_session={}".format(token))
    )
    assert _pump(coordinator, lambda: b"Device Settings" in renewed.sent)
    assert b"302" not in renewed.sent


def test_coordinator_session_full_returns_busy():
    ticks = FakeTicks(0)
    coordinator, http, sockets, ticks, _store = _online_coordinator(ticks=ticks)
    coordinator.tick()  # First station-online HTTP tick creates sessions.
    # Fill session table.
    for i in range(config.SESSION_MAX):
        sid = coordinator._sessions.create(0)
        assert sid is not None

    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_login_post("adminpass"))
    assert _pump(coordinator, lambda: b"503" in client.sent, limit=300)
    assert b"Busy" in client.sent
    assert b"Set-Cookie: pc_session=" not in client.sent


def test_station_online_defers_sessions_until_http_tick():
    coordinator, _http, _sockets, _ticks, _store = _online_coordinator()
    assert coordinator._sessions is None
    coordinator.tick()
    assert coordinator._sessions is not None


def test_coordinator_concurrent_kdf_busy():
    coordinator, http, sockets, ticks, _store = _online_coordinator()
    first = FakeStreamSocket()
    sockets.listen.enqueue(first)
    first.push_client_bytes(_http_login_post("adminpass"))
    # Start KDF without finishing (one tick after accept/read).
    for _ in range(5):
        coordinator.tick()
        if coordinator._kdf_job is not None:
            break
    assert coordinator._kdf_job is not None

    second = FakeStreamSocket()
    sockets.listen.enqueue(second)
    second.push_client_bytes(_http_login_post("adminpass"))
    assert _pump(coordinator, lambda: b"503" in second.sent, limit=20)
    assert b"Busy" in second.sent


def test_peer_abort_mid_kdf_creates_no_session():
    coordinator, http, sockets, ticks, _store = _online_coordinator()
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_login_post("adminpass"))
    for _ in range(5):
        coordinator.tick()
        if coordinator._kdf_job is not None:
            break
    assert coordinator._kdf_job is not None
    client.mark_peer_closed()
    assert _pump(
        coordinator,
        lambda: coordinator._kdf_job is None and not http.has_held_client,
        limit=300,
    )
    assert len(coordinator._sessions) == 0
    assert b"Set-Cookie: pc_session=" not in client.sent


def test_login_multipart_content_type_rejected():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x05" * n)
    body = b"password=adminpass"
    r = route_config_request(
        Req(
            "POST",
            "/login",
            {"content-type": "multipart/form-data; boundary=abc"},
            body,
        ),
        MODE_STATION_ONLINE,
        table,
        0,
        False,
    )
    assert r.action == ACTION_RESPOND
    assert b"400" in r.response
    assert r.password is None


def test_station_drop_mid_kdf_cancels_job():
    coordinator, http, sockets, ticks, _store = _online_coordinator()
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_login_post("adminpass"))
    for _ in range(5):
        coordinator.tick()
        if coordinator._kdf_job is not None:
            break
    assert coordinator._kdf_job is not None
    coordinator._wlan.connected = False
    coordinator.tick()
    assert coordinator._kdf_job is None
    assert not http.has_held_client


def test_config_auth_pure_modules_forbid_device_imports():
    for rel in (
        "src/provisioning/kdf_job.py",
        "src/provisioning/session.py",
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


def test_kdf_job_derive_purpose_cooperative():
    job = KdfJob(
        9,
        PURPOSE_PASSWORD_CHANGE_DERIVE,
        bytearray(b"newpass12"),
        urandom=lambda n: b"\xab" * n,
    )
    result = None
    steps = 0
    while result is None:
        result = job.step(config.KDF_ROUNDS_PER_TICK)
        steps += 1
        assert steps < 200
    assert result == DERIVE_OK
    assert job.salt_hex == "ab" * 16
    assert job.verifier_hex is not None
    assert len(job.verifier_hex) == 64
    assert job._password is None
    assert verify_admin_password("newpass12", job.salt_hex, job.verifier_hex)


def _http_password_change_post(new_password, cookie):
    body = "new_password={}".format(new_password)
    return (
        "POST /settings HTTP/1.1\r\n"
        "Host: 192.168.1.40\r\n"
        "Cookie: {}\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        "Content-Length: {}\r\n\r\n{}"
    ).format(cookie, len(body), body).encode("ascii")


def _login_for_cookie(coordinator, sockets, password="adminpass"):
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_login_post(password))
    assert _pump(
        coordinator,
        lambda: b"Set-Cookie: pc_session=" in client.sent,
        limit=300,
    )
    cookie_line = [
        line for line in client.sent.split(b"\r\n") if line.startswith(b"Set-Cookie:")
    ][0]
    token = cookie_line.split(b"pc_session=", 1)[1].split(b";", 1)[0].decode("ascii")
    return "pc_session={}".format(token), token


def test_route_password_change_auth_validation_and_busy():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x08" * n)
    sid = table.create(0)
    headers = {
        "cookie": "pc_session={}".format(sid),
        "content-type": "application/x-www-form-urlencoded",
    }

    unauth = route_config_request(
        Req("POST", "/settings", {"content-type": "application/x-www-form-urlencoded"}, b"new_password=newpass12"),
        MODE_STATION_ONLINE,
        table,
        0,
        False,
    )
    assert b"Location: /login" in unauth.response

    short = route_config_request(
        Req("POST", "/settings", headers, b"new_password=short"),
        MODE_STATION_ONLINE,
        table,
        0,
        False,
    )
    assert short.action == ACTION_RESPOND
    assert b"400" in short.response

    busy = route_config_request(
        Req("POST", "/settings", headers, b"new_password=newpass12"),
        MODE_STATION_ONLINE,
        table,
        0,
        True,
    )
    assert b"503" in busy.response

    ok = route_config_request(
        Req("POST", "/settings", headers, b"new_password=newpass12"),
        MODE_STATION_ONLINE,
        table,
        0,
        False,
    )
    assert ok.action == ACTION_PASSWORD_CHANGE_KDF
    assert isinstance(ok.password, bytearray)
    assert bytes(ok.password) == b"newpass12"
    assert ok.renew_session_id == sid


def test_password_change_multipart_content_type_rejected():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x0a" * n)
    sid = table.create(0)
    body = b"new_password=newpass12"
    r = route_config_request(
        Req(
            "POST",
            "/settings",
            {
                "cookie": "pc_session={}".format(sid),
                "content-type": "multipart/form-data; boundary=abc",
            },
            body,
        ),
        MODE_STATION_ONLINE,
        table,
        0,
        False,
    )
    assert r.action == ACTION_RESPOND
    assert b"400" in r.response
    assert r.password is None


def test_coordinator_password_change_keeps_acting_invalidates_others():
    coordinator, http, sockets, ticks, store = _online_coordinator(password="adminpass")
    cookie_a, token_a = _login_for_cookie(coordinator, sockets, "adminpass")
    # Second session (other browser).
    cookie_b, token_b = _login_for_cookie(coordinator, sockets, "adminpass")
    assert token_a != token_b
    assert len(coordinator._sessions) == 2

    old_settings = dict(store.load())
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_password_change_post("brandnew1", cookie_a))
    assert _pump(
        coordinator,
        lambda: b"Password changed." in client.sent,
        limit=300,
    )
    assert b"Password changed." in client.sent
    assert b'aria-live="polite"' in client.sent
    assert len(coordinator._sessions) == 1
    assert coordinator._sessions.lookup(token_a, ticks.now) is not None
    assert coordinator._sessions.lookup(token_b, ticks.now) is None

    new_settings = store.load()
    assert new_settings["wifi_ssid"] == old_settings["wifi_ssid"]
    assert new_settings["wifi_password"] == old_settings["wifi_password"]
    assert new_settings["color_scheme"] == "forest-amber"
    assert new_settings["admin_salt"] != old_settings["admin_salt"]
    assert new_settings["admin_verifier"] != old_settings["admin_verifier"]

    # Acting session still usable.
    authed = FakeStreamSocket()
    sockets.listen.enqueue(authed)
    authed.push_client_bytes(_http_get("/settings", cookie=cookie_a))
    assert _pump(coordinator, lambda: b"Device Settings" in authed.sent)
    assert b"302" not in authed.sent

    # Other session redirected + cookie cleared.
    other = FakeStreamSocket()
    sockets.listen.enqueue(other)
    other.push_client_bytes(_http_get("/settings", cookie=cookie_b))
    assert _pump(coordinator, lambda: b"Location: /login" in other.sent)
    assert b"Max-Age=0" in other.sent

    # Old password rejected; new password accepted.
    bad = FakeStreamSocket()
    sockets.listen.enqueue(bad)
    bad.push_client_bytes(_http_login_post("adminpass"))
    assert _pump(coordinator, lambda: b"Incorrect password" in bad.sent, limit=300)

    good = FakeStreamSocket()
    sockets.listen.enqueue(good)
    good.push_client_bytes(_http_login_post("brandnew1"))
    assert _pump(
        coordinator,
        lambda: b"Set-Cookie: pc_session=" in good.sent,
        limit=300,
    )


def test_coordinator_password_change_commit_fail_leaves_sessions():
    coordinator, http, sockets, ticks, store = _online_coordinator(password="adminpass")
    cookie_a, token_a = _login_for_cookie(coordinator, sockets, "adminpass")
    cookie_b, token_b = _login_for_cookie(coordinator, sockets, "adminpass")
    before = dict(store.load())

    def boom(*_args, **_kwargs):
        raise SettingsCommitError("write_fail", "forced")

    store.commit = boom

    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_password_change_post("brandnew1", cookie_a))
    assert _pump(
        coordinator,
        lambda: b"Device Settings" in client.sent and coordinator._kdf_job is None,
        limit=300,
    )
    assert b"Password changed." not in client.sent
    assert len(coordinator._sessions) == 2
    assert coordinator._sessions.lookup(token_a, ticks.now) is not None
    assert coordinator._sessions.lookup(token_b, ticks.now) is not None
    after = store.load()
    assert after["admin_salt"] == before["admin_salt"]
    assert after["admin_verifier"] == before["admin_verifier"]


def test_coordinator_password_change_derive_fail_leaves_sessions():
    import src.provisioning.kdf_job as kdf_mod

    coordinator, http, sockets, ticks, store = _online_coordinator(password="adminpass")
    cookie_a, token_a = _login_for_cookie(coordinator, sockets, "adminpass")
    cookie_b, token_b = _login_for_cookie(coordinator, sockets, "adminpass")
    before = dict(store.load())
    session_count = len(coordinator._sessions)

    real_kdf = kdf_mod.KdfJob

    def kdf_bad_urandom(
        correlation_id,
        purpose,
        password,
        salt_hex=None,
        verifier_hex=None,
        iterations=None,
        urandom=None,
    ):
        if purpose == PURPOSE_PASSWORD_CHANGE_DERIVE:
            urandom = lambda n: b"\x00"  # wrong length → DERIVE_FAILED
        return real_kdf(
            correlation_id,
            purpose,
            password,
            salt_hex=salt_hex,
            verifier_hex=verifier_hex,
            iterations=iterations,
            urandom=urandom,
        )

    kdf_mod.KdfJob = kdf_bad_urandom
    try:
        client = FakeStreamSocket()
        sockets.listen.enqueue(client)
        client.push_client_bytes(_http_password_change_post("brandnew1", cookie_a))
        assert _pump(
            coordinator,
            lambda: b"Device Settings" in client.sent and coordinator._kdf_job is None,
            limit=50,
        )
    finally:
        kdf_mod.KdfJob = real_kdf

    assert b"Password changed." not in client.sent
    assert len(coordinator._sessions) == session_count
    assert coordinator._sessions.lookup(token_a, ticks.now) is not None
    assert coordinator._sessions.lookup(token_b, ticks.now) is not None
    after = store.load()
    assert after["admin_salt"] == before["admin_salt"]
    assert after["admin_verifier"] == before["admin_verifier"]


def test_coordinator_password_change_concurrent_busy():
    coordinator, http, sockets, ticks, store = _online_coordinator()
    cookie, _token = _login_for_cookie(coordinator, sockets)

    first = FakeStreamSocket()
    sockets.listen.enqueue(first)
    first.push_client_bytes(_http_password_change_post("brandnew1", cookie))
    for _ in range(5):
        coordinator.tick()
        if coordinator._kdf_job is not None:
            break
    assert coordinator._kdf_job is not None

    second = FakeStreamSocket()
    sockets.listen.enqueue(second)
    second.push_client_bytes(_http_password_change_post("brandnew2", cookie))
    assert _pump(coordinator, lambda: b"503" in second.sent, limit=20)
    assert b"Busy" in second.sent


def test_theme_stub_inert_no_mutating_route():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x09" * n)
    sid = table.create(0)
    headers = {"cookie": "pc_session={}".format(sid)}
    r = route_config_request(
        Req("GET", "/settings", headers), MODE_STATION_ONLINE, table, 0, False
    )
    body = r.response
    assert b"Forest &amp; Amber" in body
    assert b'aria-disabled="true"' in body
    # No theme POST path — unknown theme path 404s; settings POST without
    # valid new_password is 400, not a theme mutation.
    r2 = route_config_request(
        Req("POST", "/theme", headers, b"scheme=other"),
        MODE_STATION_ONLINE,
        table,
        0,
        False,
    )
    assert b"404" in r2.response
