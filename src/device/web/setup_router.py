"""Pure allowlisted routes required by the open setup AP only."""

from src.device.web.http_parse import parse_form_urlencoded
from src.device.web import setup_pages as pages
from src.provisioning.validation import validate_setup_form_fields

ACTION_RESPOND = "respond"
ACTION_SCAN = "scan"
ACTION_CONNECT = "connect"


class SetupCandidate:
    __slots__ = ("ssid", "wifi_password", "admin_password")
    def __init__(self, ssid, wifi_password, admin_password):
        self.ssid, self.wifi_password, self.admin_password = ssid, wifi_password, admin_password
    def clear_secrets(self):
        self.wifi_password = self.admin_password = ""


class RouteResult:
    __slots__ = ("action", "response", "candidate")
    def __init__(self, action, response=None, candidate=None):
        self.action, self.response, self.candidate = action, response, candidate


def route_setup_request(request, mode, candidate_active):
    if mode != "SETUP_AP": return RouteResult(ACTION_RESPOND, pages.response_not_found())
    if request.path == "/" and request.method == "GET": return RouteResult(ACTION_RESPOND, pages.response_setup_page())
    if request.path == "/scan" and request.method == "GET": return RouteResult(ACTION_SCAN)
    if request.path != "/connect" or request.method != "POST":
        return RouteResult(ACTION_RESPOND, pages.response_unsupported() if request.path in ("/", "/scan", "/connect") else pages.response_not_found())
    if candidate_active: return RouteResult(ACTION_RESPOND, pages.response_busy())
    content_type = request.headers.get("content-type", "")
    if content_type and "application/x-www-form-urlencoded" not in content_type.lower(): return RouteResult(ACTION_RESPOND, pages.response_bad_request())
    fields = parse_form_urlencoded(request.body)
    if fields is None: return RouteResult(ACTION_RESPOND, pages.response_bad_request())
    check = validate_setup_form_fields(fields.get("ssid", ""), fields.get("wifi_password", ""), fields.get("admin_password", ""))
    if not check.ok: return RouteResult(ACTION_RESPOND, pages.response_bad_request())
    return RouteResult(ACTION_CONNECT, candidate=SetupCandidate(check.settings["ssid"], check.settings["wifi_password"], check.settings["admin_password"]))


def scan_response(ssids): return pages.response_scan_json(ssids)
