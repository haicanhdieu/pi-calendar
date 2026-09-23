"""Host tests for Config login, session gate, and cooperative KDF auth."""

import ast
from html.parser import HTMLParser
from pathlib import Path

from src import config
from src.device.network.coordinator import NetworkCoordinator
from src.device.network.mailbox import Mailbox
from src.device.network.models import EVENT_STATION_ERROR, MODE_SETUP_AP, MODE_STATION_ONLINE
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
    PURPOSE_SETUP_DERIVE,
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
    assert 'href="/exit"' in login
    assert "Cancel" in login
    assert "water.css" in login
    assert "fetch(" not in login
    assert "Incorrect password" in pages.login_page_html(incorrect=True)
    assert "aria-live" in pages.login_page_html(incorrect=True)

    settings = pages.settings_page_html()
    assert "Device Settings" in settings
    assert "Admin Password" in settings
    assert "Color Scheme" in settings
    assert "Forest &amp; Amber" in settings
    assert '<details' in settings
    assert 'disabled' in settings
    assert 'name="new_password"' in settings
    assert 'name="postpone_delay_minutes"' in settings
    assert 'value="10"' in settings
    assert "Postpone delay (min)" in settings
    assert "minutes" in settings
    assert 'method="POST"' in settings
    assert 'action="/settings"' in settings
    assert "water.css" in settings
    assert "http://" not in settings
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


def test_authenticated_settings_page_lists_alerts_and_empty_state():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x12" * n)
    sid = table.create(0)
    fs = FakeFS({
        ".settings-v1": _record_bytes(
            settings_version=2,
            alerts=[
                {"id": "weekday", "hour": 7, "minute": 0, "enabled": True, "weekdays": [0, 1, 2, 3, 4]},
                {"id": "once", "hour": 9, "minute": 30, "enabled": False, "weekdays": []},
            ],
            postpone_delay_minutes=10,
        )
    })
    store = _store(fs)
    request = Req("GET", "/settings", {"cookie": "pc_session={}".format(sid)})

    response = route_config_request(
        request, MODE_STATION_ONLINE, table, 0, False, settings_store=store
    ).response

    assert b"ALERTS" in response
    assert b"07:00" in response
    assert "Monday\u2013Friday".encode() in response
    assert b"On" in response and b"Off" in response
    assert response.index(b"ALERTS") < response.index(b"POSTPONE")

    empty = _store(FakeFS({".settings-v1": _record_bytes()}))
    empty_response = route_config_request(
        request, MODE_STATION_ONLINE, table, 0, False, settings_store=empty
    ).response
    assert b"No alerts stored." in empty_response


def test_authenticated_postpone_save_preserves_record_and_renders_success():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x19" * n)
    sid = table.create(0)
    alerts = [{"id": "morning", "hour": 7, "minute": 0,
               "enabled": True, "weekdays": [0, 1]}]
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2,
        wifi_ssid="preserve-me", wifi_password="secret123",
        alerts=alerts, postpone_delay_minutes=10,
    )})
    store = _store(fs)
    before = store.load()
    response = route_config_request(
        Req("POST", "/settings", {
            "cookie": "pc_session={}".format(sid),
            "content-type": "application/x-www-form-urlencoded",
        }, b"postpone_action=save&postpone_delay_minutes=15"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response

    assert b"Postpone delay saved." in response
    saved = store.load()
    assert saved["postpone_delay_minutes"] == 15
    assert saved["alerts"] == alerts
    assert saved["wifi_ssid"] == before["wifi_ssid"]
    assert saved["wifi_password"] == before["wifi_password"]
    assert b'value="15"' in response and b"minutes" in response


def test_postpone_invalid_values_and_commit_failure_do_not_mutate_record():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x1b" * n)
    sid = table.create(0)
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2, alerts=[], postpone_delay_minutes=10
    )})
    store = _store(fs)
    headers = {"cookie": "pc_session={}".format(sid),
               "content-type": "application/x-www-form-urlencoded"}
    prior = fs.files[".settings-v1"]
    for value in ("0", "61", "1.5", "not-a-number"):
        response = route_config_request(
            Req("POST", "/settings", headers,
                ("postpone_action=save&postpone_delay_minutes=" + value).encode()),
            MODE_STATION_ONLINE, table, 0, False, settings_store=store,
        ).response
        assert b"1 to 60 whole minutes" in response
        assert fs.files[".settings-v1"] == prior

    def boom(*_args, **_kwargs):
        raise SettingsCommitError("write_fail", "forced")

    store.commit = boom
    response = route_config_request(
        Req("POST", "/settings", headers,
            b"postpone_action=save&postpone_delay_minutes=15"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Postpone delay could not be saved." in response
    assert fs.files[".settings-v1"] == prior


def test_unauthenticated_postpone_save_redirects_without_mutation():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x1c" * n)
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2, alerts=[], postpone_delay_minutes=10
    )})
    store = _store(fs)
    prior = fs.files[".settings-v1"]
    response = route_config_request(
        Req("POST", "/settings",
            {"content-type": "application/x-www-form-urlencoded"},
            b"postpone_action=save&postpone_delay_minutes=15"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Location: /login" in response
    assert fs.files[".settings-v1"] == prior


def test_unauthenticated_alert_data_never_renders():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x13" * n)
    store = _store(FakeFS({".settings-v1": _record_bytes()}))
    response = route_config_request(
        Req("GET", "/settings"), MODE_STATION_ONLINE, table, 0, False,
        settings_store=store,
    ).response
    assert b"302" in response
    assert b"No alerts stored" not in response


def test_authenticated_add_alert_commits_weekday_recurrence():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x14" * n)
    sid = table.create(0)
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2, alerts=[], postpone_delay_minutes=10
    )})
    store = _store(fs)
    body = b"alert_action=add&alert_time=07%3A00&alert_enabled=on&weekday_0=on&weekday_1=on&weekday_2=on&weekday_3=on&weekday_4=on"
    response = route_config_request(
        Req("POST", "/settings", {
            "cookie": "pc_session={}".format(sid),
            "content-type": "application/x-www-form-urlencoded",
        }, body), MODE_STATION_ONLINE, table, 0, False, settings_store=store
    ).response
    assert b"Alert saved." in response
    saved = store.load()
    assert saved["alerts"] == [{
        "id": "alert-1", "hour": 7, "minute": 0,
        "enabled": True, "weekdays": [0, 1, 2, 3, 4],
    }]
    assert b"07:00" in response and "Monday\u2013Friday".encode() in response


def test_add_one_time_alert_and_invalid_add_do_not_mutate_record():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x15" * n)
    sid = table.create(0)
    fs = FakeFS({".settings-v1": _record_bytes()})
    store = _store(fs)
    headers = {
        "cookie": "pc_session={}".format(sid),
        "content-type": "application/x-www-form-urlencoded",
    }
    one_time = route_config_request(
        Req("POST", "/settings", headers, b"alert_action=add&alert_time=09%3A30"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Alert saved." in one_time
    assert store.load()["alerts"][0]["weekdays"] == []
    prior = fs.files[".settings-v1"]
    invalid = route_config_request(
        Req("POST", "/settings", headers, b"alert_action=add&alert_time=99%3A99"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Invalid Time." in invalid
    assert fs.files[".settings-v1"] == prior


def test_invalid_add_with_unknown_field_does_not_commit():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x17" * n)
    sid = table.create(0)
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2, alerts=[], postpone_delay_minutes=10
    )})
    store = _store(fs)
    prior = fs.files[".settings-v1"]
    response = route_config_request(
        Req("POST", "/settings", {
            "cookie": "pc_session={}".format(sid),
            "content-type": "application/x-www-form-urlencoded",
        }, b"alert_action=add&alert_time=09%3A30&weekday_9=on"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Invalid alert fields." in response
    assert fs.files[".settings-v1"] == prior


def test_add_alert_is_unavailable_and_rejected_at_ten():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x16" * n)
    sid = table.create(0)
    alerts = [
        {"id": "alert-{}".format(i), "hour": i, "minute": 0,
         "enabled": True, "weekdays": []}
        for i in range(10)
    ]
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2, alerts=alerts, postpone_delay_minutes=10
    )})
    store = _store(fs)
    get = route_config_request(
        Req("GET", "/settings", {"cookie": "pc_session={}".format(sid)}),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Ten-alert limit reached" in get
    assert b'name="alert_action"' not in get
    prior = fs.files[".settings-v1"]
    post = route_config_request(
        Req("POST", "/settings", {
            "cookie": "pc_session={}".format(sid),
            "content-type": "application/x-www-form-urlencoded",
        }, b"alert_action=add&alert_time=10%3A00"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Ten-alert limit reached" in post
    assert fs.files[".settings-v1"] == prior


def test_authenticated_edit_alert_preserves_id_and_updates_time_recurrence_and_enabled():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x18" * n)
    sid = table.create(0)
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2,
        alerts=[{"id": "morning", "hour": 7, "minute": 0, "enabled": True,
                 "weekdays": [0, 1, 2, 3, 4]}],
        postpone_delay_minutes=15,
    )})
    store = _store(fs)
    headers = {"cookie": "pc_session={}".format(sid),
               "content-type": "application/x-www-form-urlencoded"}

    opened = route_config_request(
        Req("GET", "/settings/edit/morning", {"cookie": headers["cookie"]}),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b'name="alert_id" value="morning"' in opened
    assert b'value="07:00"' in opened
    assert b'name=weekday_0 type=checkbox checked' in opened
    assert b'name=weekday_5 type=checkbox>' in opened
    assert b'<a href="/settings" role="button">Cancel</a>' in opened

    body = b"alert_action=edit&alert_id=morning&alert_time=06%3A30"
    response = route_config_request(
        Req("POST", "/settings", headers, body), MODE_STATION_ONLINE,
        table, 0, False, settings_store=store,
    ).response
    assert b"Alert saved." in response
    assert store.load()["alerts"] == [{
        "id": "morning", "hour": 6, "minute": 30,
        "enabled": False, "weekdays": [],
    }]
    assert b"06:30" in response and b"One time" in response and b"Off" in response
    assert store.load()["postpone_delay_minutes"] == 15


def test_add_alert_editor_has_cancel_button_without_submitting_alert():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x1e" * n)
    sid = table.create(0)
    store = _store(FakeFS({".settings-v1": _record_bytes()}))

    response = route_config_request(
        Req("GET", "/settings/add", {"cookie": "pc_session=" + sid}),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response

    assert b'<a href="/settings" role="button">Cancel</a>' in response
    assert store.load()["alerts"] == []


class _FormsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {"attrs": attrs, "html": []}
        elif self.current is not None:
            self.current["html"].append((tag, attrs))

    def handle_endtag(self, tag):
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None


def test_delete_alert_requires_confirmation_markup_and_removes_exact_id_atomically():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x1a" * n)
    sid = table.create(0)
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2,
        wifi_ssid="wifi", wifi_password="secret123",
        alerts=[
            {"id": "morning", "hour": 7, "minute": 0, "enabled": True, "weekdays": [0]},
            {"id": "evening", "hour": 19, "minute": 30, "enabled": False, "weekdays": [4]},
        ], postpone_delay_minutes=25,
    )})
    store = _store(fs)
    cookie = "pc_session={}".format(sid)

    editor = route_config_request(
        Req("GET", "/settings/edit/morning", {"cookie": cookie}),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    forms = _FormsParser()
    forms.feed(editor.decode())
    delete_form = next(form for form in forms.forms if any(
        attrs.get("name") == "alert_action" and attrs.get("value") == "delete"
        for tag, attrs in form["html"]
    ))
    edit_form = next(form for form in forms.forms if any(
        attrs.get("name") == "alert_time" for tag, attrs in form["html"]
    ))
    assert edit_form["attrs"].get("method", "get").lower() == "post"
    assert edit_form["attrs"].get("action") == "/settings"
    assert delete_form["attrs"].get("method", "get").lower() == "post"
    assert delete_form["attrs"].get("action") == "/settings"
    edit_controls = [attrs for tag, attrs in edit_form["html"] if tag in ("input", "button")]
    delete_controls = [attrs for tag, attrs in delete_form["html"] if tag in ("input", "button")]
    assert any(c.get("name") == "alert_id" and c.get("value") == "morning" for c in edit_controls)
    assert any(c.get("name") == "alert_id" and c.get("value") == "morning" for c in delete_controls)
    assert any(c.get("name") == "alert_action" and c.get("value") == "delete" for c in delete_controls)
    assert {c["name"] for c in delete_controls if c.get("name")} == {"alert_action", "alert_id"}
    delete_button = next(c for c in delete_controls if c.get("class") == "danger")
    assert delete_button.get("type") == "submit"
    assert delete_button.get("onclick") == "return confirm('Delete this alert?')"

    prior = fs.files[".settings-v1"]
    response = route_config_request(
        Req("POST", "/settings", {
            "cookie": cookie,
            "content-type": "application/x-www-form-urlencoded",
        }, b"alert_action=delete&alert_id=morning"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Alert deleted." in response
    assert store.load()["alerts"] == [{
        "id": "evening", "hour": 19, "minute": 30,
        "enabled": False, "weekdays": [4],
    }]
    assert store.load()["wifi_ssid"] == "wifi"
    assert store.load()["postpone_delay_minutes"] == 25
    assert fs.files[".settings-v1"] != prior
    assert b"morning" not in response
    assert b"evening" in response


def test_delete_alert_unknown_or_unauthenticated_does_not_mutate():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x1b" * n)
    sid = table.create(0)
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2, postpone_delay_minutes=10,
        alerts=[{"id": "morning", "hour": 7, "minute": 0, "enabled": True, "weekdays": []}],
    )})
    store = _store(fs)
    prior = fs.files[".settings-v1"]
    headers = {"cookie": "pc_session={}".format(sid),
               "content-type": "application/x-www-form-urlencoded"}
    response = route_config_request(
        Req("POST", "/settings", headers,
            b"alert_action=delete&alert_id=missing"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Alert not found." in response
    assert fs.files[".settings-v1"] == prior

    response = route_config_request(
        Req("POST", "/settings", {},
            b"alert_action=delete&alert_id=morning"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"302" in response and b"Location: /login" in response
    assert fs.files[".settings-v1"] == prior


def test_delete_from_ten_alerts_reenables_add_and_commit_failure_preserves_record():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x1c" * n)
    sid = table.create(0)
    alerts = [{"id": "alert-{}".format(i), "hour": i, "minute": 0,
               "enabled": True, "weekdays": []} for i in range(10)]
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2, alerts=alerts, postpone_delay_minutes=10
    )})
    store = _store(fs)
    headers = {"cookie": "pc_session={}".format(sid),
               "content-type": "application/x-www-form-urlencoded"}
    response = route_config_request(
        Req("POST", "/settings", headers,
            b"alert_action=delete&alert_id=alert-9"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Ten-alert limit reached" not in response
    assert b"/settings/add" in response
    assert len(store.load()["alerts"]) == 9

    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2, alerts=alerts, postpone_delay_minutes=10
    )})
    fs.fail_rename_from = ".settings-v1"
    store = _store(fs)
    prior = fs.files[".settings-v1"]
    response = route_config_request(
        Req("POST", "/settings", headers,
            b"alert_action=delete&alert_id=alert-9"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Alert could not be deleted." in response
    assert fs.files[".settings-v1"] == prior


def test_invalid_or_unknown_edit_does_not_mutate_settings():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x19" * n)
    sid = table.create(0)
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2,
        alerts=[{"id": "morning", "hour": 7, "minute": 0, "enabled": True,
                 "weekdays": [0, 1]}],
        postpone_delay_minutes=10,
    )})
    store = _store(fs)
    headers = {"cookie": "pc_session={}".format(sid),
               "content-type": "application/x-www-form-urlencoded"}
    prior = fs.files[".settings-v1"]
    for body, message in (
        (b"alert_action=edit&alert_id=morning&alert_time=99%3A99", b"Invalid Time."),
        (b"alert_action=edit&alert_id=missing&alert_time=06%3A30", b"Alert not found."),
    ):
        response = route_config_request(
            Req("POST", "/settings", headers, body), MODE_STATION_ONLINE,
            table, 0, False, settings_store=store,
        ).response
        assert message in response
        assert fs.files[".settings-v1"] == prior


def test_delete_alert_with_extra_field_is_rejected_without_mutating():
    ticks = FakeTicks(0)
    table = SessionTable(ticks_module=ticks, urandom=lambda n: b"\x1d" * n)
    sid = table.create(0)
    fs = FakeFS({".settings-v1": _record_bytes(
        settings_version=2,
        alerts=[{"id": "morning", "hour": 7, "minute": 0, "enabled": True, "weekdays": []}],
        postpone_delay_minutes=10,
    )})
    store = _store(fs)
    headers = {"cookie": "pc_session={}".format(sid),
               "content-type": "application/x-www-form-urlencoded"}
    prior = fs.files[".settings-v1"]

    response = route_config_request(
        Req("POST", "/settings", headers,
            b"alert_action=delete&alert_id=morning&extra=1"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Invalid alert action." in response
    assert fs.files[".settings-v1"] == prior

    response = route_config_request(
        Req("POST", "/settings", headers, b"alert_action=delete"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Invalid alert action." in response, (
        "exactly one field (missing alert_id) fails the len(fields)!=2 check "
        "before the dedicated alert_id-presence check ever runs"
    )
    assert fs.files[".settings-v1"] == prior

    response = route_config_request(
        Req("POST", "/settings", headers, b"alert_action=delete&bogus=1"),
        MODE_STATION_ONLINE, table, 0, False, settings_store=store,
    ).response
    assert b"Invalid alert fields." in response, (
        "two fields but no alert_id key must reach the dedicated presence check"
    )
    assert fs.files[".settings-v1"] == prior


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


def test_coordinator_authenticated_add_page_returns_complete_editor_response():
    coordinator, http, sockets, _ticks, store = _online_coordinator()
    coordinator._get_sessions()
    sid = coordinator._sessions.create(0)
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(
        _http_get("/settings/add", "pc_session=" + sid)
    )

    assert _pump(coordinator, lambda: client.closed and client.sent)
    assert client.sent.startswith(b"HTTP/1.0 200 OK")
    assert b'name="alert_time"' in client.sent
    assert b"name=weekday_0" in client.sent


def test_exit_route_without_a_session_arms_the_reset():
    coordinator, http, sockets, _ticks, _store = _online_coordinator()
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/exit"))

    assert _pump(coordinator, lambda: client.closed and client.sent)
    assert client.sent.startswith(b"HTTP/1.0 200 OK")
    assert b"Returning to the clock" in client.sent
    assert coordinator.web_exit_requested is True


def test_authenticated_exit_route_arms_the_return_to_clock_mode():
    coordinator, http, sockets, _ticks, _store = _online_coordinator()
    coordinator._get_sessions()
    sid = coordinator._sessions.create(0)
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/exit", "pc_session=" + sid))

    assert _pump(coordinator, lambda: client.closed and client.sent)
    assert client.sent.startswith(b"HTTP/1.0 200 OK")
    assert b"Returning to the clock" in client.sent
    # The confirmation is queued first; config_mode drains it before resetting.
    assert coordinator.web_exit_requested is True


def test_settings_page_offers_the_way_back_to_the_clock():
    coordinator, _http, sockets, _ticks, _store = _online_coordinator()
    coordinator._get_sessions()
    sid = coordinator._sessions.create(0)
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/settings", "pc_session=" + sid))

    assert _pump(coordinator, lambda: client.closed and client.sent)
    assert b'href="/exit"' in client.sent


def test_clock_mode_coordinator_serves_no_admin_site():
    """station_web=False is what keeps the web stack out of clock mode."""
    salt, verifier = derive_admin_verifier("adminpass", salt=b"\x44" * 16)
    fs = FakeFS({".settings-v1": _record_bytes(admin_salt=salt, admin_verifier=verifier)})
    sockets = FakeTcpSocketModule()
    coordinator = NetworkCoordinator(
        Mailbox(),
        wlan=FakeWlan(connected=True),
        ap_wlan=FakeApWlan(),
        settings_store=_store(fs),
        ticks_module=FakeTicks(0),
        socket_module=sockets,
        station_web=False,
    )
    coordinator.tick()
    coordinator.tick()
    assert coordinator.mode == MODE_STATION_ONLINE

    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/settings"))
    for _ in range(50):
        coordinator.tick()

    # No listener was ever constructed, so nothing answered and none of the
    # router/session/KDF modules were pulled onto the heap.
    assert coordinator._http is None
    assert client.sent == b""
    assert coordinator.web_busy is False
    assert coordinator.web_exit_requested is False


def test_coordinator_authenticated_edit_page_uses_lazy_session_factory():
    coordinator, _http, sockets, _ticks, _store = _online_coordinator()
    coordinator._get_sessions()
    sid = coordinator._sessions.create(0)
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/settings/edit/morning", "pc_session=" + sid))

    assert _pump(coordinator, lambda: client.closed and client.sent)
    assert client.sent.startswith(b"HTTP/1.0 200 OK")
    assert b"Device Settings" in client.sent


def test_coordinator_unauthenticated_add_page_redirects_without_editor():
    coordinator, _http, sockets, _ticks, _store = _online_coordinator()
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/settings/add"))

    assert _pump(coordinator, lambda: client.closed and client.sent)
    assert client.sent.startswith(b"HTTP/1.0 302 Found")
    assert b"Location: /login" in client.sent
    assert b"alert_time" not in client.sent


def test_coordinator_expired_add_session_redirects_without_editor():
    coordinator, _http, sockets, ticks, _store = _online_coordinator()
    coordinator._get_sessions()
    sid = coordinator._sessions.create(0)
    ticks.now = 10**9
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/settings/add", "pc_session=" + sid))

    assert _pump(coordinator, lambda: client.closed and client.sent)
    assert client.sent.startswith(b"HTTP/1.0 302 Found")
    assert b"Location: /login" in client.sent
    assert b"Max-Age=0" in client.sent
    assert b"alert_time" not in client.sent


def test_request_render_failure_returns_503_and_followup_request_recovers(monkeypatch):
    coordinator, http, sockets, _ticks, _store = _online_coordinator()
    coordinator._get_sessions()
    sid = coordinator._sessions.create(0)
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/settings/add", "pc_session=" + sid))

    from src.device.web import pages

    original = pages.response_settings_page
    monkeypatch.setattr(
        pages,
        "response_settings_page",
        lambda *args, **kwargs: (_ for _ in ()).throw(MemoryError()),
    )
    events = []
    coordinator._event_sink = events
    assert _pump(coordinator, lambda: client.closed and client.sent)
    assert client.sent.startswith(b"HTTP/1.0 503 Service Unavailable")
    assert b"Service temporarily unavailable" in client.sent
    assert client.closed
    assert events[-1].error_code == "web_asset"
    assert http._listen is not None

    monkeypatch.setattr(pages, "response_settings_page", original)
    followup = FakeStreamSocket()
    sockets.listen.enqueue(followup)
    followup.push_client_bytes(_http_get("/settings", "pc_session=" + sid))
    assert _pump(coordinator, lambda: followup.closed and followup.sent)
    assert followup.sent.startswith(b"HTTP/1.0 200 OK")
    assert b"Device Settings" in followup.sent


def test_generic_request_failure_returns_503_and_emits_existing_event(monkeypatch):
    coordinator, http, sockets, _ticks, _store = _online_coordinator()
    coordinator._get_sessions()
    sid = coordinator._sessions.create(0)
    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_get("/settings/add", "pc_session=" + sid))

    from src.device.web import pages

    monkeypatch.setattr(
        pages,
        "response_settings_page",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    events = []
    coordinator._event_sink = events
    assert _pump(coordinator, lambda: client.closed and client.sent)
    assert client.sent.startswith(b"HTTP/1.0 503 Service Unavailable")
    assert client.closed
    assert http._listen is not None
    assert events[-1].error_code == "web_asset"


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
    assert coordinator._sessions is None


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
    coordinator.tick()  # No browser request: config sessions remain deferred.
    assert coordinator._sessions is None
    coordinator._get_sessions()
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


def test_station_online_defers_sessions_until_first_browser_request():
    coordinator, _http, _sockets, _ticks, _store = _online_coordinator()
    assert coordinator._sessions is None


def test_station_listener_and_asset_failures_emit_named_events_and_close():
    coordinator, _http, _sockets, _ticks, _store = _online_coordinator()
    events = []
    coordinator._event_sink = events

    class BadHttp:
        last_failure_phase = "listen"
        def __init__(self): self.closed = 0
        def ensure_listening(self): return False
        def close_all(self): self.closed += 1

    bad = BadHttp()
    coordinator._http = bad
    coordinator.tick()
    assert events[-1].kind == EVENT_STATION_ERROR
    assert events[-1].error_code == "web_listen"

    class ExplodingHttp(BadHttp):
        def __init__(self):
            super().__init__()
            self.clients_closed = 0
        def ensure_listening(self): return True
        def tick(self, *_args, **_kwargs): raise MemoryError()
        def close_clients(self): self.clients_closed += 1

    coordinator._web_next_retry = None
    exploding = ExplodingHttp()
    coordinator._http = exploding
    coordinator.tick()
    assert events[-1].error_code == "web_asset"
    assert exploding.clients_closed == 1
    # Listener must survive a per-request MemoryError so config stays reachable.
    assert exploding.closed == 0
    coordinator.tick()
    assert coordinator._sessions is None


def test_station_asset_import_failure_closes_clients_and_stays_recoverable():
    """Regression: a MemoryError/Exception while lazily importing the

    station web/page modules must close any already-accepted browser
    connection (the ``http.close_clients()`` call these two branches were
    previously missing, unlike every other identical failure branch in the
    file -- see spec-cannot-access-settings-page-after-boot-pi.md), must
    emit the existing secret-free ``web_asset`` event, and must leave the
    cooperative loop able to retry and eventually succeed once the import
    stops failing.
    """
    import builtins

    coordinator, _http, _sockets, ticks, _store = _online_coordinator(ticks=FakeTicks(0))
    events = []
    coordinator._event_sink = events

    class TrackingHttp:
        def __init__(self):
            self.clients_closed = 0
            self.ticked = 0

        def ensure_listening(self):
            return True

        def close_clients(self):
            self.clients_closed += 1

        def tick(self, *_args, **_kwargs):
            self.ticked += 1
            return None

    tracking = TrackingHttp()
    coordinator._http = tracking
    assert coordinator._station_assets_ready is False

    real_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "src.device.web.page_login_content":
            raise MemoryError()
        return real_import(name, *args, **kwargs)

    builtins.__import__ = failing_import
    try:
        coordinator.tick()
    finally:
        builtins.__import__ = real_import

    # The already-accepted connection must be closed, not left hanging.
    assert tracking.clients_closed == 1
    # http.tick() (which would dispatch a response) is never reached while
    # assets are not ready -- the loop returns cleanly instead of crashing.
    assert tracking.ticked == 0
    assert events[-1].kind == EVENT_STATION_ERROR
    assert events[-1].error_code == "web_asset"
    assert coordinator.mode == MODE_STATION_ONLINE

    # Bounded retry: once the import stops failing, station assets become
    # ready and normal request dispatch resumes.
    ticks.now = config.HTTP_RETRY_MS + 1
    coordinator.tick()
    assert coordinator._station_assets_ready is True
    assert tracking.ticked == 1


def test_station_asset_import_generic_exception_closes_clients():
    """Sibling of the MemoryError case above: a plain (non-MemoryError)

    exception during the same lazy station-asset import must take the
    ``except Exception`` branch, which must also close the already-accepted
    browser connection and emit the same named ``web_asset`` failure.
    """
    import builtins

    coordinator, _http, _sockets, ticks, _store = _online_coordinator(ticks=FakeTicks(0))
    events = []
    coordinator._event_sink = events

    class TrackingHttp:
        def __init__(self):
            self.clients_closed = 0

        def ensure_listening(self):
            return True

        def close_clients(self):
            self.clients_closed += 1

    tracking = TrackingHttp()
    coordinator._http = tracking
    assert coordinator._station_assets_ready is False

    real_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "src.device.web.page_login_content":
            raise RuntimeError("boom")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = failing_import
    try:
        coordinator.tick()
    finally:
        builtins.__import__ = real_import

    assert tracking.clients_closed == 1
    assert events[-1].kind == EVENT_STATION_ERROR
    assert events[-1].error_code == "web_asset"
    assert coordinator.mode == MODE_STATION_ONLINE


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
    assert coordinator._sessions is None


def test_login_and_unknown_routes_do_not_allocate_sessions():
    coordinator, _http, sockets, _ticks, _store = _online_coordinator()
    for request in (_http_get("/login"), _http_get("/missing"), _http_login_post("wrongpass1")):
        client = FakeStreamSocket()
        sockets.listen.enqueue(client)
        client.push_client_bytes(request)
        assert _pump(coordinator, lambda: client.closed or bool(client.sent))
        assert coordinator._sessions is None


def test_login_kdf_memory_failure_closes_request_and_emits_web_asset():
    import src.provisioning.kdf_job as kdf_mod

    coordinator, _http, sockets, _ticks, _store = _online_coordinator()
    events = []
    coordinator._event_sink = events
    real_kdf = kdf_mod.KdfJob
    kdf_mod.KdfJob = lambda *_args, **_kwargs: (_ for _ in ()).throw(MemoryError())
    try:
        client = FakeStreamSocket()
        sockets.listen.enqueue(client)
        client.push_client_bytes(_http_login_post("adminpass"))
        assert _pump(coordinator, lambda: client.closed)
    finally:
        kdf_mod.KdfJob = real_kdf

    assert coordinator._kdf_job is None
    assert events[-1].kind == EVENT_STATION_ERROR
    assert events[-1].error_code == "web_asset"
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


def test_setup_kdf_failure_is_a_derive_failure_and_wipes_password():
    job = KdfJob(
        10,
        PURPOSE_SETUP_DERIVE,
        bytearray(b"adminpass"),
        iterations=0,
        urandom=lambda n: b"\xcd" * n,
    )
    assert job.step(config.KDF_ROUNDS_PER_TICK) == "DERIVE_FAILED"
    assert job.salt_hex is None
    assert job.verifier_hex is None
    assert job._password is None


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


def test_login_kdf_keeps_stepping_while_web_listener_is_backed_off():
    """
    A stuck/failing web listener must not freeze an in-flight KDF job.

    Regression for a device-side lockout: an unrelated listen failure sets
    ``_web_next_retry`` into the future; the previous coordinator gated ALL
    per-tick work (including pure-computation KDF stepping) behind that
    same retry timer, so a persistently failing listener meant an admin
    login already accepted (job created) never finished, and every later
    ``/login`` attempt saw a permanent 503 Busy until reboot. KDF stepping
    is pure computation with no socket I/O, so it must progress regardless
    of listener backoff.
    """
    coordinator, http, sockets, ticks, store = _online_coordinator(password="adminpass")

    client = FakeStreamSocket()
    sockets.listen.enqueue(client)
    client.push_client_bytes(_http_login_post("adminpass"))

    for _ in range(5):
        coordinator.tick()
        if coordinator._kdf_job is not None:
            break
    assert coordinator._kdf_job is not None, "login KDF job should be in flight"

    # Simulate an active listener backoff (e.g. from an unrelated transient
    # listen/socket failure) covering the rest of the KDF job's rounds.
    coordinator._web_next_retry = ticks.ticks_add(ticks.now, config.HTTP_RETRY_MS)
    assert coordinator._web_retry_due(ticks.now) is False

    for _ in range(250):
        assert coordinator._web_retry_due(ticks.now) is False, (
            "test setup bug: backoff window elapsed before the job could finish"
        )
        coordinator.tick()
        if coordinator._kdf_job is None:
            break
    assert coordinator._kdf_job is None, "KDF job must finish even while the listener backs off"
    assert client.sent == b"", "response must stay queued, not flushed, while backed off"

    # Once the backoff window elapses, the already-finished job's queued
    # response flushes on the very next serviceable tick — no reboot needed.
    ticks.now = coordinator._ticks.ticks_add(coordinator._web_next_retry, 1)
    assert coordinator._web_retry_due(ticks.now) is True
    assert _pump(coordinator, lambda: b"302" in client.sent)
    assert b"Location: /settings" in client.sent
    assert b"Set-Cookie: pc_session=" in client.sent


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
