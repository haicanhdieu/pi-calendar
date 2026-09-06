"""Allowlisted setup/config HTTP routing (pure)."""

from src import config
from src.device.web.http_parse import cookie_header_value, parse_form_urlencoded
from src.device.web import pages
from src.provisioning.validation import (
    validate_admin_password_field,
    validate_setup_form_fields,
)

ACTION_RESPOND = "respond"
ACTION_SCAN = "scan"
ACTION_CONNECT = "connect"
ACTION_HOLD = "hold"
ACTION_LOGIN_KDF = "login_kdf"
ACTION_PASSWORD_CHANGE_KDF = "password_change_kdf"


class RouteResult:
    """Outcome of routing one completed request."""

    __slots__ = (
        "action",
        "response",
        "candidate",
        "error_code",
        "password",
        "renew_session_id",
    )

    def __init__(
        self,
        action,
        response=None,
        candidate=None,
        error_code=None,
        password=None,
        renew_session_id=None,
    ):
        self.action = action
        self.response = response
        self.candidate = candidate
        self.error_code = error_code
        self.password = password
        self.renew_session_id = renew_session_id


class SetupCandidate:
    """Volatile pending setup join (secrets held only until terminal outcome)."""

    __slots__ = ("ssid", "wifi_password", "admin_password")

    def __init__(self, ssid, wifi_password, admin_password):
        self.ssid = ssid
        self.wifi_password = wifi_password
        self.admin_password = admin_password

    def clear_secrets(self):
        self.wifi_password = ""
        self.admin_password = ""


def route_setup_request(request, mode, candidate_active):
    """
    Route an allowlisted setup request.

    Setup routes exist only when ``mode == \"SETUP_AP\"``. Returns a
    :class:`RouteResult` that either carries a fixed response, requests a
    scan payload, or creates one Connect candidate.
    """
    if mode != "SETUP_AP":
        return RouteResult(ACTION_RESPOND, pages.response_not_found())

    method = request.method
    path = request.path

    if path == "/" and method == "GET":
        return RouteResult(ACTION_RESPOND, pages.response_setup_page())

    if path == "/scan" and method == "GET":
        return RouteResult(ACTION_SCAN)

    if path == "/connect" and method == "POST":
        return _route_connect(request, candidate_active)

    if path in ("/", "/scan", "/connect"):
        return RouteResult(ACTION_RESPOND, pages.response_unsupported())

    return RouteResult(ACTION_RESPOND, pages.response_not_found())


def route_config_request(request, mode, session_table, now, kdf_busy):
    """
    Route Config login/settings requests (``STATION_ONLINE`` only).

    ``session_table`` is the coordinator-owned table. Login POST returns
    ``ACTION_LOGIN_KDF`` with a password bytearray (caller owns wipe).
    Authenticated settings POST returns ``ACTION_PASSWORD_CHANGE_KDF``.
    Concurrent KDF admission returns fixed ``503 Busy``.
    """
    if mode != "STATION_ONLINE":
        return RouteResult(ACTION_RESPOND, pages.response_not_found())

    method = request.method
    path = request.path

    if path == "/login" and method == "GET":
        return RouteResult(ACTION_RESPOND, pages.response_login_page())

    if path == "/login" and method == "POST":
        return _route_login_post(request, kdf_busy)

    if path in ("/", "/settings") and method == "GET":
        return _route_protected_get(request, session_table, now)

    if path in ("/", "/settings") and method == "POST":
        return _route_password_change_post(request, session_table, now, kdf_busy)

    if path in ("/", "/settings", "/login"):
        return RouteResult(ACTION_RESPOND, pages.response_unsupported())

    return RouteResult(ACTION_RESPOND, pages.response_not_found())


def _lookup_session(request, session_table, now):
    raw_cookie = request.headers.get("cookie")
    token = cookie_header_value(raw_cookie, config.SESSION_COOKIE_NAME)
    if token is None:
        return None, RouteResult(ACTION_RESPOND, pages.response_redirect_login())

    entry = session_table.lookup(token, now)
    if entry is None:
        return None, RouteResult(
            ACTION_RESPOND, pages.response_redirect_login(clear_cookie=True)
        )
    return entry, None


def _route_protected_get(request, session_table, now):
    entry, reject = _lookup_session(request, session_table, now)
    if reject is not None:
        return reject

    return RouteResult(
        ACTION_RESPOND,
        pages.response_settings_page(),
        renew_session_id=entry.encoded_id,
    )


def _route_password_change_post(request, session_table, now, kdf_busy):
    entry, reject = _lookup_session(request, session_table, now)
    if reject is not None:
        return reject

    if kdf_busy:
        return RouteResult(
            ACTION_RESPOND, pages.response_busy(), error_code="busy"
        )

    ctype = request.headers.get("content-type", "")
    if ctype and "application/x-www-form-urlencoded" not in ctype.lower():
        return RouteResult(ACTION_RESPOND, pages.response_bad_request())

    fields = parse_form_urlencoded(request.body)
    if fields is None:
        return RouteResult(ACTION_RESPOND, pages.response_bad_request())

    new_password = fields.get("new_password", "")
    if not isinstance(new_password, str):
        new_password = str(new_password)
    check = validate_admin_password_field(new_password)
    if not check.ok:
        new_password = None
        fields = None
        request.body = b""
        return RouteResult(ACTION_RESPOND, pages.response_bad_request())

    password_ba = bytearray(new_password.encode("utf-8"))
    new_password = None
    check = None
    fields = None
    request.body = b""

    return RouteResult(
        ACTION_PASSWORD_CHANGE_KDF,
        password=password_ba,
        renew_session_id=entry.encoded_id,
    )


def _route_login_post(request, kdf_busy):
    if kdf_busy:
        return RouteResult(
            ACTION_RESPOND, pages.response_busy(), error_code="busy"
        )

    ctype = request.headers.get("content-type", "")
    if ctype and "application/x-www-form-urlencoded" not in ctype.lower():
        return RouteResult(ACTION_RESPOND, pages.response_bad_request())

    fields = parse_form_urlencoded(request.body)
    if fields is None:
        return RouteResult(ACTION_RESPOND, pages.response_bad_request())

    # Drop body reference ASAP; only retain password bytes for the KDF job.
    password = fields.get("password", "")
    if not isinstance(password, str):
        password = str(password)
    password_ba = bytearray(password.encode("utf-8"))
    password = None
    fields = None
    request.body = b""

    return RouteResult(ACTION_LOGIN_KDF, password=password_ba)


def _route_connect(request, candidate_active):
    if candidate_active:
        return RouteResult(
            ACTION_RESPOND, pages.response_busy(), error_code="busy"
        )

    ctype = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" not in ctype.lower():
        # Allow missing content-type on small embedded clients if body parses.
        if ctype and "urlencoded" not in ctype.lower() and "form" not in ctype.lower():
            return RouteResult(ACTION_RESPOND, pages.response_bad_request())

    fields = parse_form_urlencoded(request.body)
    if fields is None:
        return RouteResult(ACTION_RESPOND, pages.response_bad_request())

    ssid = fields.get("ssid", "")
    wifi_password = fields.get("wifi_password", "")
    admin_password = fields.get("admin_password", "")
    check = validate_setup_form_fields(ssid, wifi_password, admin_password)
    if not check.ok:
        return RouteResult(ACTION_RESPOND, pages.response_bad_request())

    candidate = SetupCandidate(
        check.settings["ssid"],
        check.settings["wifi_password"],
        check.settings["admin_password"],
    )
    return RouteResult(ACTION_CONNECT, candidate=candidate)


def scan_response(ssids):
    return pages.response_scan_json(ssids)
