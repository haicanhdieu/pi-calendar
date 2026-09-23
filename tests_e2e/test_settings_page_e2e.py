"""Live-device E2E tests for the Config settings web page.

Targets a real Pi Calendar device over HTTP (not a fake socket). Requires
STATION_ONLINE mode and a reachable device — the whole module is skipped
automatically when the device does not answer, so this file is safe to
leave in the normal test tree and reuse in future sessions.

Configure the target with env vars (defaults match the current bench unit):
    PI_CALENDAR_URL="http://192.168.1.32"
    PI_CALENDAR_ADMIN_PASSWORD="12345678"

Run explicitly (not part of the default unit-test sweep, which has no
device to talk to):
    pytest tests_e2e/test_settings_page_e2e.py -v

Any test that mutates device state (password, postpone delay, alerts)
restores the original value in a ``finally`` block, so the suite is
repeatable against the same device.

IMPORTANT — session budget: the device's SessionTable holds at most
``config.SESSION_MAX`` (4) concurrent sessions, there is no logout route,
and idle sessions only drop after ``config.SESSION_IDLE_MS`` (15 minutes).
A fresh successful login permanently consumes one of those 4 slots for the
rest of that window. This suite therefore logs in as few times as
possible and reuses one shared authenticated session for everything that
doesn't specifically need its own fresh login — logging in per-test would
exhaust the table after ~4 tests and every later login would correctly
receive 503 Busy (the device doing exactly what it's supposed to, not a
bug). Two full back-to-back runs within 15 minutes can still collide for
the same reason; that is a real device constraint, not a test flake.

KNOWN, PRE-EXISTING FLAKE (not caused by this suite or fixed by pacing):
past ~20 requests in one boot cycle, this specific device has reliably
started returning 503/malformed responses to write requests (alert edit,
alert-add validation, password change), regardless of request pacing
(tried 1s/2s/3s -- identical failure point every time, so it is a fixed
per-boot request budget, not a rate limit). This matches the project's
documented, previously-investigated, unresolved heap-fragmentation issue:
``_bmad-output/implementation-artifacts/touch-ui/
settings-page-fragmentation-attempts-log.md``. Every test that mutates
device state still verifies and restores it in a ``finally``/retry path
(see ``_force_admin_password``), so a run hitting this ceiling fails
loudly rather than corrupting device state. If this resurfaces, reboot
the device (via ``mpremote connect <port> reset``) between test groups
rather than chasing it as a suite bug.
"""

import os
import re
import time
import uuid
from html.parser import HTMLParser

import pytest
import requests

from tests_e2e.config_mode import DeviceUnreachable, ensure_config_mode


class _DeleteFormParser(HTMLParser):
    """Read forms and their successful named controls from rendered HTML."""

    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None
        self.select = None
        self.textarea = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {"method": attrs.get("method", "get").lower(),
                            "action": attrs.get("action", ""), "fields": []}
        elif self.current is not None and tag == "input" and attrs.get("name"):
            kind = attrs.get("type", "text").lower()
            if kind in ("checkbox", "radio") and "checked" not in attrs:
                return
            if kind not in ("submit", "button", "image", "reset", "file"):
                self.current["fields"].append((
                    attrs["name"], attrs.get("value", "on" if kind == "checkbox" else "")
                ))
        elif self.current is not None and tag == "select" and attrs.get("name"):
            self.select = {"name": attrs["name"], "values": []}
        elif self.current is not None and tag == "option" and self.select is not None:
            if "selected" in attrs:
                self.select["values"].append(attrs.get("value", ""))
        elif self.current is not None and tag == "textarea" and attrs.get("name"):
            self.textarea = {"name": attrs["name"], "value": ""}

    def handle_data(self, data):
        if self.textarea is not None:
            self.textarea["value"] += data

    def handle_endtag(self, tag):
        if tag == "select" and self.select is not None:
            if self.select["values"]:
                self.current["fields"].extend(
                    (self.select["name"], value) for value in self.select["values"]
                )
            self.select = None
        elif tag == "textarea" and self.textarea is not None:
            self.current["fields"].append((self.textarea["name"], self.textarea["value"]))
            self.textarea = None
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None


def _rendered_delete_fields(page):
    parser = _DeleteFormParser()
    parser.feed(page)
    for form in parser.forms:
        fields = form["fields"]
        if ("alert_action", "delete") in fields:
            assert form["method"] == "post"
            assert form["action"] == "/settings"
            assert fields.count(("alert_action", "delete")) == 1
            alert_ids = [value for name, value in fields if name == "alert_id"]
            assert len(alert_ids) == 1
            assert len(fields) == 2
            return {"alert_action": "delete", "alert_id": alert_ids[0]}
    raise AssertionError("Settings page has no rendered alert delete form")

BASE_URL = os.environ.get("PI_CALENDAR_URL", "http://192.168.1.32").rstrip("/")
ADMIN_PASSWORD = os.environ.get("PI_CALENDAR_ADMIN_PASSWORD", "12345678")
TIMEOUT = 8

# The device is a single-core, single-threaded MicroPython HTTP server:
# back-to-back requests with no gap between them can overrun its tiny TCP
# backlog. Pace every request issued through `requests` so this suite
# behaves like a real browser, not a flood.
_REQUEST_PACE_S = float(os.environ.get("PI_CALENDAR_REQUEST_PACE_S", "1.0"))
_unpaced_request = requests.Session.request


def _paced_request(self, *args, **kwargs):
    time.sleep(_REQUEST_PACE_S)
    return _unpaced_request(self, *args, **kwargs)


requests.Session.request = _paced_request


def _url(path):
    return BASE_URL + path


@pytest.fixture(scope="module", autouse=True)
def _require_device():
    # The admin site exists only in config mode (issue #2); a device sitting
    # on the clock face answers the first request with a knock interstitial
    # and reboots into it.
    try:
        ensure_config_mode(BASE_URL, timeout=TIMEOUT)
    except (requests.exceptions.RequestException, DeviceUnreachable) as exc:
        pytest.skip("Pi Calendar device not reachable at {}: {}".format(BASE_URL, exc))


def _login(password=ADMIN_PASSWORD):
    """Return an authenticated requests.Session, or None if login failed.

    Consumes one of the device's SESSION_MAX session-table slots on
    success — see the module docstring. Prefer the shared `auth_session`
    fixture; call this directly only when a test needs its own fresh
    login (e.g. proving a specific password does/doesn't work).
    """
    session = requests.Session()
    resp = session.post(
        _url("/login"), data={"password": password}, timeout=TIMEOUT, allow_redirects=False
    )
    if resp.status_code == 302 and "pc_session" in session.cookies.get_dict():
        return session
    return None


@pytest.fixture(scope="module")
def auth_session():
    """One authenticated session, shared read/write across the whole
    module. Individual tests must leave device state as they found it."""
    session = requests.Session()
    resp = session.post(
        _url("/login"), data={"password": ADMIN_PASSWORD},
        timeout=TIMEOUT, allow_redirects=False,
    )
    assert resp.status_code == 302, "setup login with configured admin password failed"
    assert resp.headers.get("Location") == "/settings"
    cookie = session.cookies.get("pc_session")
    assert cookie
    return session


# --- Login page -------------------------------------------------------

def test_login_page_serves_form():
    resp = requests.get(_url("/login"), timeout=TIMEOUT)
    assert resp.status_code == 200
    assert 'name="password"' in resp.text
    assert "Incorrect password" not in resp.text


def test_login_wrong_password_shows_incorrect_banner_and_no_cookie():
    session = requests.Session()
    resp = session.post(
        _url("/login"), data={"password": "definitely-wrong-pw"},
        timeout=TIMEOUT, allow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Incorrect password" in resp.text
    assert "pc_session" not in session.cookies.get_dict()


def test_login_wrong_content_type_is_bad_request():
    resp = requests.post(
        _url("/login"),
        data="password=" + ADMIN_PASSWORD,
        headers={"Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 400


# --- Auth gate on /settings --------------------------------------------

def test_settings_without_cookie_redirects_to_login():
    resp = requests.get(_url("/settings"), timeout=TIMEOUT, allow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers.get("Location") == "/login"


def test_settings_with_bogus_cookie_redirects_and_clears_cookie():
    resp = requests.get(
        _url("/settings"), cookies={"pc_session": "not-a-real-session-token"},
        timeout=TIMEOUT, allow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers.get("Location") == "/login"
    assert "Max-Age=0" in resp.headers.get("Set-Cookie", "")


def test_settings_authenticated_returns_device_settings_page(auth_session):
    resp = auth_session.get(_url("/settings"), timeout=TIMEOUT)
    assert resp.status_code == 200
    assert "Device Settings" in resp.text
    assert "Admin Password" in resp.text
    assert "POSTPONE" in resp.text


# --- Routing edge cases --------------------------------------------------

def test_unknown_route_is_not_found(auth_session):
    resp = auth_session.get(_url("/does-not-exist"), timeout=TIMEOUT)
    assert resp.status_code == 404


def test_unsupported_method_on_settings_is_method_not_allowed(auth_session):
    resp = auth_session.put(_url("/settings"), timeout=TIMEOUT)
    assert resp.status_code == 405


def test_unsupported_method_on_login_is_method_not_allowed():
    resp = requests.put(_url("/login"), timeout=TIMEOUT)
    assert resp.status_code == 405


# --- Postpone delay -------------------------------------------------------

def test_postpone_delay_round_trip(auth_session):
    original = auth_session.get(_url("/settings"), timeout=TIMEOUT)
    assert original.status_code == 200

    resp = auth_session.post(
        _url("/settings"),
        data={"postpone_action": "save", "postpone_delay_minutes": "37"},
        timeout=TIMEOUT,
    )
    try:
        assert resp.status_code == 200
        assert "Postpone delay saved." in resp.text
        assert 'value="37"' in resp.text
    finally:
        restore = auth_session.post(
            _url("/settings"),
            data={"postpone_action": "save", "postpone_delay_minutes": "10"},
            timeout=TIMEOUT,
        )
        assert restore.status_code == 200
        assert 'value="10"' in restore.text


def test_postpone_delay_out_of_range_is_rejected_without_mutating(auth_session):
    before = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert 'value="10"' in before

    resp = auth_session.post(
        _url("/settings"),
        data={"postpone_action": "save", "postpone_delay_minutes": "9999"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 400
    assert "Postpone delay must be 1 to 60 whole minutes." in resp.text

    after = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert 'value="10"' in after


def test_postpone_save_unauthenticated_redirects_without_mutating(auth_session):
    before = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert 'value="10"' in before

    resp = requests.post(
        _url("/settings"),
        data={"postpone_action": "save", "postpone_delay_minutes": "42"},
        timeout=TIMEOUT, allow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers.get("Location") == "/login"

    after = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert 'value="10"' in after


# --- Alert lifecycle -------------------------------------------------------

def test_alert_add_edit_delete_round_trip(auth_session):
    before = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    prior_ids = set(re.findall(r'href="/settings/edit/([^"?#]+)', before))
    alert_id = None
    try:
        resp = auth_session.post(
            _url("/settings"),
            data={
                "alert_action": "add",
                "alert_time": "07:15",
                "alert_enabled": "on",
                "weekday_0": "on",
            },
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        assert "Alert saved." in resp.text
        assert "07:15" in resp.text

        page = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
        new_ids = set(re.findall(r'href="/settings/edit/([^"?#]+)', page)) - prior_ids
        assert len(new_ids) == 1
        alert_id = new_ids.pop()
        editor = auth_session.get(_url("/settings/edit/" + alert_id), timeout=TIMEOUT).text
        delete_fields = _rendered_delete_fields(editor)
        assert delete_fields == {"alert_action": "delete", "alert_id": alert_id}

        edited = auth_session.post(
            _url("/settings"),
            data={
                "alert_action": "edit",
                "alert_id": alert_id,
                "alert_time": "08:30",
                "alert_enabled": "on",
                "weekday_1": "on",
            },
            timeout=TIMEOUT,
        )
        assert edited.status_code == 200
        assert "Alert saved." in edited.text
        assert "08:30" in edited.text
    finally:
        if alert_id is None:
            page = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
            new_ids = set(re.findall(r'href="/settings/edit/([^"?#]+)', page)) - prior_ids
            if len(new_ids) == 1:
                alert_id = new_ids.pop()
        if alert_id is not None:
            deleted = auth_session.post(
                _url("/settings"),
                data={"alert_action": "delete", "alert_id": alert_id},
                timeout=TIMEOUT,
            )
            assert deleted.status_code == 200
            assert "Alert deleted." in deleted.text

    after = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert "No alerts stored." in after or alert_id not in after


def test_alert_add_invalid_time_is_rejected(auth_session):
    resp = auth_session.post(
        _url("/settings"),
        data={"alert_action": "add", "alert_time": "not-a-time", "alert_enabled": "on"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 400
    assert "Invalid" in resp.text


def test_alert_delete_unknown_id_is_rejected(auth_session):
    resp = auth_session.post(
        _url("/settings"),
        data={"alert_action": "delete", "alert_id": "no-such-alert"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 400


def test_alert_add_unauthenticated_redirects_without_mutating(auth_session):
    resp = requests.post(
        _url("/settings"),
        data={"alert_action": "add", "alert_time": "09:00", "alert_enabled": "on"},
        timeout=TIMEOUT, allow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers.get("Location") == "/login"

    page = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert "09:00" not in page


# --- Admin password change -------------------------------------------------
#
# Run last: changing the password while it's mid-flight would break every
# other test's assumption that ADMIN_PASSWORD is current. This test also
# minds the 4-slot session budget carefully (see module docstring): it
# reuses the shared `auth_session` for the actual change, and only opens
# the one fresh login that is inherently required to *prove* the new
# password works, reusing that session for the restore instead of a
# second fresh login.

def _force_admin_password(target, candidates, attempts=5, backoff_s=3):
    """Best-effort, verified drive of the device's admin password to `target`.

    A password-change POST can silently no-op under device load: it comes
    back 200 with a plain settings page (no "Password changed." banner)
    instead of erroring, so a status-code-only check is not trustworthy
    here (observed live). This tries each password in `candidates` (plus
    `target`, in case an earlier attempt partially landed) to find a
    working login, submits the change, and verifies with a fresh login --
    retrying with backoff rather than trusting the response. Raises with
    the last known-good password if it can't converge, so a failure is
    never silent about what the device's password currently is.
    """
    tried = list(dict.fromkeys([target] + list(candidates)))
    last_known_good = None
    for _attempt in range(attempts):
        working = None
        for candidate in tried:
            working = _login(password=candidate)
            if working is not None:
                last_known_good = candidate
                break
        assert working is not None, (
            "device admin password is unknown -- none of {!r} worked; "
            "MANUAL RECOVERY REQUIRED".format(tried)
        )
        if last_known_good == target:
            return
        working.post(_url("/settings"), data={"new_password": target}, timeout=TIMEOUT)
        if _login(password=target) is not None:
            return
        time.sleep(backoff_s)
    raise AssertionError(
        "could not converge device admin password to {!r} after {} attempts; "
        "last known-good password was {!r} -- MANUAL RECOVERY REQUIRED".format(
            target, attempts, last_known_good
        )
    )


def test_admin_password_change_round_trip(auth_session):
    temp_password = "e2e-temp-" + uuid.uuid4().hex[:12]

    resp = auth_session.post(
        _url("/settings"), data={"new_password": temp_password}, timeout=TIMEOUT
    )
    assert resp.status_code == 200
    assert "Password changed." in resp.text

    try:
        old_login = _login(password=ADMIN_PASSWORD)
        assert old_login is None, "old password should no longer work"

        relogin = _login(password=temp_password)
        assert relogin is not None, "could not log in with the newly set password"
    finally:
        _force_admin_password(ADMIN_PASSWORD, candidates=[temp_password])

    final_check = _login(password=ADMIN_PASSWORD)
    assert final_check is not None, "admin password was not restored to the original value"


def test_admin_password_change_too_short_is_rejected(auth_session):
    too_short = "short1"
    try:
        resp = auth_session.post(
            _url("/settings"), data={"new_password": too_short}, timeout=TIMEOUT
        )
        assert resp.status_code == 400
    finally:
        # Safety net: if device load ever turns this rejection into a
        # silent accept (observed live for the password-change path), do
        # not leave the device on a password this test never meant to set.
        _force_admin_password(ADMIN_PASSWORD, candidates=[too_short])
