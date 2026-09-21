"""Live-device E2E tests for the alert business rules on the settings page.

Companion to test_settings_page_e2e.py, split into its own file so it can
be run standalone against a freshly booted device rather than competing
for the same request budget (see both files' module docstrings on the
device's ~20-request-per-boot ceiling and 4-slot session table).

Deliberately NOT covered here: the ten-alert limit. Reaching it needs ten
individual add POSTs plus cleanup, which alone approaches this device's
demonstrated safe request budget, and the business rule (limit=10, and
re-enabling add after a delete) is already exhaustively covered on the
host in tests/test_config_auth.py (test_add_alert_is_unavailable_and_
rejected_at_ten, test_delete_from_ten_alerts_reenables_add_and_commit_
failure_preserves_record) via the exact same code path this suite already
exercises for a single add/edit/delete. Re-running that volume on real
hardware adds device risk without adding confidence.

Configure the target with env vars (defaults match the current bench unit):
    PI_CALENDAR_URL="http://192.168.1.32"
    PI_CALENDAR_ADMIN_PASSWORD="12345678"

Run explicitly:
    pytest tests_e2e/test_alerts_business_e2e.py -v

KNOWN, PRE-EXISTING FAILURE MODE for every test that renders the inline
alert-editor form (a rejected add re-showing the editor with an error, or
GET /settings/edit/<id>): the first such request after boot reliably hits
a MemoryError on this device (confirmed via serial capture -- not a code
bug in this codebase's request handling). This is the same documented,
previously-investigated, unresolved heap-fragmentation class of issue as
``_bmad-output/implementation-artifacts/touch-ui/
settings-page-fragmentation-attempts-log.md`` (which was about
session.py's first-use import; the alert-editor's first-use import hits
the same wall). It is NOT the same as a real bug this session already
found and fixed on the same code path: page_settings_content.py used to
call MicroPython's ``__import__`` with a ``fromlist=`` keyword argument,
which CPython accepts but MicroPython's built-in does not -- a 100%
deterministic TypeError, invisible to every host test, fixed by switching
to plain ``from ... import ...`` statements. That fix is verified correct
(via mpremote exec, both before and after). The MemoryError that remains
is the open hardware issue, not this fix; expect these tests to keep
failing until that is resolved, and do not re-attempt the same
already-ruled-out mitigations (see the attempts log) without new data.
"""

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("PI_CALENDAR_URL", "http://192.168.1.32").rstrip("/")
ADMIN_PASSWORD = os.environ.get("PI_CALENDAR_ADMIN_PASSWORD", "12345678")
TIMEOUT = 8

_REQUEST_PACE_S = float(os.environ.get("PI_CALENDAR_REQUEST_PACE_S", "1.5"))
_unpaced_request = requests.Session.request


def _paced_request(self, *args, **kwargs):
    time.sleep(_REQUEST_PACE_S)
    return _unpaced_request(self, *args, **kwargs)


requests.Session.request = _paced_request


def _url(path):
    return BASE_URL + path


@pytest.fixture(scope="module", autouse=True)
def _require_device():
    try:
        requests.get(_url("/login"), timeout=TIMEOUT)
    except requests.exceptions.RequestException as exc:
        pytest.skip("Pi Calendar device not reachable at {}: {}".format(BASE_URL, exc))


@pytest.fixture(scope="module")
def auth_session():
    session = requests.Session()
    resp = session.post(
        _url("/login"), data={"password": ADMIN_PASSWORD},
        timeout=TIMEOUT, allow_redirects=False,
    )
    assert resp.status_code == 302, "setup login with configured admin password failed"
    assert session.cookies.get("pc_session")
    return session


def _extract_alert_id(page_text, needle='href="/settings/edit/'):
    start = page_text.index(needle)
    return page_text[start:].split('"')[1].rsplit("/", 1)[-1]


def _delete_alert(session, alert_id):
    return session.post(
        _url("/settings"),
        data={"alert_action": "delete", "alert_id": alert_id},
        timeout=TIMEOUT,
    )


# --- Time validation --------------------------------------------------

def test_add_alert_rejects_out_of_range_time_without_mutating(auth_session):
    before = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert "No alerts stored." in before

    resp = auth_session.post(
        _url("/settings"),
        data={"alert_action": "add", "alert_time": "24:00", "alert_enabled": "on"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 400
    assert "Invalid Time." in resp.text

    after = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert "No alerts stored." in after


# --- Weekday recurrence --------------------------------------------------

def test_add_alert_with_multiple_weekdays_renders_and_persists_recurrence(auth_session):
    resp = auth_session.post(
        _url("/settings"),
        data={
            "alert_action": "add",
            "alert_time": "06:45",
            "alert_enabled": "on",
            "weekday_0": "on",
            "weekday_2": "on",
            "weekday_4": "on",
        },
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200
    assert "Alert saved." in resp.text
    assert "06:45" in resp.text
    assert "Monday, Wednesday, Friday" in resp.text

    try:
        page = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
        assert "Monday, Wednesday, Friday" in page
        alert_id = _extract_alert_id(page)

        edit_page = auth_session.get(_url("/settings/edit/" + alert_id), timeout=TIMEOUT).text
        assert 'name=weekday_0 type=checkbox checked' in edit_page
        assert 'name=weekday_2 type=checkbox checked' in edit_page
        assert 'name=weekday_4 type=checkbox checked' in edit_page
        assert 'name=weekday_1 type=checkbox>' in edit_page
    finally:
        deleted = _delete_alert(auth_session, alert_id)
        assert deleted.status_code == 200
        assert "Alert deleted." in deleted.text


# --- Edit / delete edge cases ----------------------------------------------

def test_edit_unknown_alert_id_is_rejected_without_mutating(auth_session):
    before = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert "No alerts stored." in before

    resp = auth_session.post(
        _url("/settings"),
        data={"alert_action": "edit", "alert_id": "no-such-alert", "alert_time": "05:00"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 400
    assert "Alert not found." in resp.text

    after = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    assert "No alerts stored." in after


def test_delete_with_extra_field_is_rejected(auth_session):
    resp = auth_session.post(
        _url("/settings"),
        data={"alert_action": "delete", "alert_id": "whatever", "extra": "1"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 400
    assert "Invalid alert action." in resp.text


def test_delete_missing_alert_id_is_rejected(auth_session):
    resp = auth_session.post(
        _url("/settings"),
        data={"alert_action": "delete", "bogus": "1"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 400
    assert "Invalid alert fields." in resp.text


# --- Disabled alert round trip --------------------------------------------

def test_add_disabled_alert_and_toggle_enabled_via_edit(auth_session):
    resp = auth_session.post(
        _url("/settings"),
        data={"alert_action": "add", "alert_time": "21:15"},  # alert_enabled omitted = off
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200
    assert "Alert saved." in resp.text
    assert "21:15" in resp.text
    assert "Off" in resp.text

    try:
        page = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
        alert_id = _extract_alert_id(page)

        enabled = auth_session.post(
            _url("/settings"),
            data={
                "alert_action": "edit", "alert_id": alert_id,
                "alert_time": "21:15", "alert_enabled": "on",
            },
            timeout=TIMEOUT,
        )
        assert enabled.status_code == 200
        assert "On" in enabled.text
    finally:
        deleted = _delete_alert(auth_session, alert_id)
        assert deleted.status_code == 200
        assert "Alert deleted." in deleted.text
