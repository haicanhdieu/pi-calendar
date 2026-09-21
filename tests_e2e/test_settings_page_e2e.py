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
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("PI_CALENDAR_URL", "http://192.168.1.32").rstrip("/")
ADMIN_PASSWORD = os.environ.get("PI_CALENDAR_ADMIN_PASSWORD", "12345678")
TIMEOUT = 8


def _url(path):
    return BASE_URL + path


@pytest.fixture(scope="module", autouse=True)
def _require_device():
    try:
        requests.get(_url("/login"), timeout=TIMEOUT)
    except requests.exceptions.RequestException as exc:
        pytest.skip("Pi Calendar device not reachable at {}: {}".format(BASE_URL, exc))


def _login(password=ADMIN_PASSWORD):
    """Return an authenticated requests.Session, or None if login failed."""
    session = requests.Session()
    resp = session.post(
        _url("/login"), data={"password": password}, timeout=TIMEOUT, allow_redirects=False
    )
    if resp.status_code == 302 and "pc_session" in session.cookies.get_dict():
        return session
    return None


@pytest.fixture
def auth_session():
    session = _login()
    assert session is not None, "setup login with configured admin password failed"
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


def test_login_correct_password_redirects_and_sets_session_cookie():
    session = requests.Session()
    resp = session.post(
        _url("/login"), data={"password": ADMIN_PASSWORD},
        timeout=TIMEOUT, allow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers.get("Location") == "/settings"
    cookie = session.cookies.get("pc_session")
    assert cookie
    assert session.cookies.get_dict().get("pc_session") == cookie


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


def test_postpone_save_unauthenticated_redirects_without_mutating():
    before = _login().get(_url("/settings"), timeout=TIMEOUT).text
    assert 'value="10"' in before

    resp = requests.post(
        _url("/settings"),
        data={"postpone_action": "save", "postpone_delay_minutes": "42"},
        timeout=TIMEOUT, allow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers.get("Location") == "/login"

    after = _login().get(_url("/settings"), timeout=TIMEOUT).text
    assert 'value="10"' in after


# --- Alert lifecycle -------------------------------------------------------

def test_alert_add_edit_delete_round_trip(auth_session):
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
    start = page.index('href="/settings/edit/')
    alert_id = page[start:].split('"')[1].rsplit("/", 1)[-1]

    try:
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


def test_alert_add_unauthenticated_redirects_without_mutating():
    resp = requests.post(
        _url("/settings"),
        data={"alert_action": "add", "alert_time": "09:00", "alert_enabled": "on"},
        timeout=TIMEOUT, allow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers.get("Location") == "/login"

    page = _login().get(_url("/settings"), timeout=TIMEOUT).text
    assert "09:00" not in page


# --- Admin password change -------------------------------------------------

def test_admin_password_change_round_trip():
    session = _login()
    assert session is not None

    temp_password = "e2e-temp-" + uuid.uuid4().hex[:12]
    try:
        resp = session.post(
            _url("/settings"), data={"new_password": temp_password}, timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert "Password changed." in resp.text

        relogin = _login(password=temp_password)
        assert relogin is not None, "could not log in with the newly set password"

        old_login = _login(password=ADMIN_PASSWORD)
        assert old_login is None, "old password should no longer work"
    finally:
        current = session.post(
            _url("/settings"), data={"new_password": ADMIN_PASSWORD}, timeout=TIMEOUT
        )
        if current.status_code != 200 or "Password changed." not in current.text:
            restorer = _login(password=temp_password)
            assert restorer is not None, (
                "FAILED TO RESTORE ORIGINAL ADMIN PASSWORD; device password is now "
                + temp_password
            )
            restore = restorer.post(
                _url("/settings"), data={"new_password": ADMIN_PASSWORD}, timeout=TIMEOUT
            )
            assert restore.status_code == 200 and "Password changed." in restore.text

    final_check = _login(password=ADMIN_PASSWORD)
    assert final_check is not None, "admin password was not restored to the original value"


def test_admin_password_change_too_short_is_rejected(auth_session):
    resp = auth_session.post(_url("/settings"), data={"new_password": "short1"}, timeout=TIMEOUT)
    assert resp.status_code == 400

    still_works = _login(password=ADMIN_PASSWORD)
    assert still_works is not None
