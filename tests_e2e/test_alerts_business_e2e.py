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

KNOWN, PRE-EXISTING FAILURE MODE: any early station-mode HTTP request on
this device -- not narrowly the alert-editor render, that was this
session's first hypothesis and turned out to be too narrow -- can hit a
genuine MemoryError, confirmed via serial capture with a temporary
sys.print_exception (added and reverted; not left in the tree). Some
requests succeed, some don't, from run to run, on an otherwise-identical
clean boot. This is the same documented, previously-investigated,
unresolved heap-fragmentation class of issue as
``_bmad-output/implementation-artifacts/touch-ui/
settings-page-fragmentation-attempts-log.md`` (originally about
session.py's first-use import). It is NOT the same as two real,
deterministic bugs this session found and fixed on these code paths,
both invisible to every host test because they only reproduce on
MicroPython's builtins, not CPython's:
  1. page_settings_content.py called MicroPython's ``__import__`` with a
     ``fromlist=`` keyword argument, which CPython accepts and
     MicroPython's built-in does not (TypeError). Fixed with plain
     ``from ... import ...`` statements.
  2. alert_route.py's edit_alert used ``next(generator, None)``;
     MicroPython's built-in ``next()`` does not accept the two-argument
     default form CPython's does (TypeError). Fixed with an explicit loop.
Both fixes are verified correct via mpremote exec, before and after, and
the full host suite (648) still passes. The MemoryError that remains is
the open hardware issue, not these fixes; expect occasional failures
here until that is resolved, and do not re-attempt the same
already-ruled-out mitigations (see the attempts log) without new data.

Because a MemoryError can strike *after* a mutation has already committed
but *before* the response finishes rendering (observed live: an add
persisted while the client only ever saw a 503 for it), retrying a
"failed" mutating request is not safe here -- this API isn't idempotent,
and the add might have actually succeeded. This suite does not auto-retry
mutating calls; instead a module-scoped `_sweep_stray_alerts` fixture
deletes whatever alerts the device reports at teardown, regardless of
which test (if any) is credited with creating them, so a mid-run failure
here can't leave stray state for the next run.
"""

import os
import time

import pytest
import requests

from tests_e2e.config_mode import DeviceUnreachable, ensure_config_mode

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
    # The admin site exists only in config mode (issue #2); a device sitting
    # on the clock face answers the first request with a knock interstitial
    # and reboots into it.
    try:
        ensure_config_mode(BASE_URL, timeout=TIMEOUT)
    except (requests.exceptions.RequestException, DeviceUnreachable) as exc:
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


def _all_alert_ids(page_text):
    ids = []
    marker = 'href="/settings/edit/'
    pos = 0
    while True:
        start = page_text.find(marker, pos)
        if start == -1:
            break
        end = page_text.index('"', start + len(marker))
        ids.append(page_text[start + len(marker):end])
        pos = end
    return ids


@pytest.fixture(scope="module", autouse=True)
def _sweep_stray_alerts(auth_session):
    """Unconditionally delete any alert left over at module teardown.

    A MemoryError can strike *after* a mutation has already committed but
    *before* the response finishes rendering (observed live: an add
    persisted while the client only ever saw a 503 for it), so a failed
    request is not proof nothing changed. Retrying mutating requests isn't
    safe here either -- this API isn't idempotent, and a "failed" add that
    actually committed would duplicate on retry. Sweeping at the end,
    keyed off whatever the device says currently exists rather than what
    tests think they created, is the only reliable way to leave the
    device in the state this suite found it.
    """
    yield
    try:
        page = auth_session.get(_url("/settings"), timeout=TIMEOUT).text
    except requests.exceptions.RequestException:
        return
    for alert_id in _all_alert_ids(page):
        try:
            _delete_alert(auth_session, alert_id)
        except requests.exceptions.RequestException:
            pass


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
