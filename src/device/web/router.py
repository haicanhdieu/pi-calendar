"""Allowlisted setup HTTP routing and form→candidate mapping (pure)."""

from src.device.web.http_parse import parse_form_urlencoded
from src.device.web import pages
from src.provisioning.validation import validate_setup_form_fields

ACTION_RESPOND = "respond"
ACTION_SCAN = "scan"
ACTION_CONNECT = "connect"
ACTION_HOLD = "hold"


class RouteResult:
    """Outcome of routing one completed request."""

    __slots__ = ("action", "response", "candidate", "error_code")

    def __init__(self, action, response=None, candidate=None, error_code=None):
        self.action = action
        self.response = response
        self.candidate = candidate
        self.error_code = error_code


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
