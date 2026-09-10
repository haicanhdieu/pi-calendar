"""Fixed, setup-only responses for the open provisioning AP."""

from src.device.web.page_setup_content import setup_page_html
from src.device.web.http_parse import html_escape


def http_response(status, body, content_type="text/html; charset=utf-8"):
    payload = body.encode("utf-8") if isinstance(body, str) else body
    header = ("HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
              "Connection: close\r\n\r\n").format(status, content_type, len(payload))
    return header.encode("ascii") + payload


def response_setup_page(state=None): return http_response("200 OK", setup_page_html(state))
def response_setup_form_error(): return response_setup_page({"status": "form_error"})


def _json_string(value):
    out = ['"']
    for char in str(value):
        code = ord(char)
        if char == '"': out.append('\\"')
        elif char == "\\": out.append("\\\\")
        elif char == "\n": out.append("\\n")
        elif char == "\r": out.append("\\r")
        elif char == "\t": out.append("\\t")
        elif code < 32: out.append("\\u%04x" % code)
        else: out.append(char)
    out.append('"')
    return "".join(out)


def response_scan_json(ssids):
    payload = bytearray(b'{"ssids":[')
    for index, value in enumerate(ssids):
        if index: payload.extend(b",")
        payload.extend(_json_string(value).encode("utf-8"))
    payload.extend(b"]}")
    return http_response("200 OK", payload, "application/json")


def response_join_started(ssid):
    return http_response("200 OK", '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pi Calendar Connecting</title><style>body{background:#12161c;color:#e8ecf1;font:15px sans-serif;max-width:480px;margin:0 auto;padding:20px}.banner{padding:12px;border-radius:12px;border:1px solid #3ddc84;color:#3ddc84;margin:16px 0}</style></head><body><h1>Setup Saved</h1><p class="banner">Joining %s now.</p><p>The <b>PiCalendar-Setup</b> network is shutting down, so this page will stop responding. That is expected.</p><p>The clock shows its new IP address once it is online. Reconnect your phone to your home Wi-Fi and open that address.</p><p>If the join fails, <b>PiCalendar-Setup</b> comes back within a minute. Reconnect to it and reload this page to see what went wrong.</p></body></html>' % html_escape(ssid or "the network"))


def response_busy(): return http_response("503 Service Unavailable", "Busy")
def response_bad_request(): return http_response("400 Bad Request", "Bad Request")
def response_not_found(): return http_response("404 Not Found", "Not Found")
def response_too_large(): return http_response("413 Payload Too Large", "Too Large")
def response_unsupported(): return http_response("405 Method Not Allowed", "Method Not Allowed")
def response_join_failure(ssid, admin_password=""):
    return response_setup_page({"status": "failure", "ssid": ssid, "admin_password": admin_password, "ssids": (ssid,)})
def response_join_success(ssid):
    return http_response("200 OK", '<!doctype html><meta name=viewport content=width=device-width><title>Pi Calendar Connected</title><h1>Connected to %s.</h1><p>Reconnect your phone to your home Wi-Fi, then open the IP shown on the clock.</p>' % html_escape(ssid or "Wi-Fi"))
def response_for_parse_error(error_code):
    return response_too_large() if error_code == "too_large" else (response_unsupported() if error_code == "unsupported" else response_bad_request())
