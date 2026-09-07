"""Fixed, setup-only assets for the open provisioning AP."""

from src.device.web.http_parse import html_escape


def http_response(status, body, content_type="text/html; charset=utf-8"):
    payload = body.encode("utf-8") if isinstance(body, str) else body
    header = ("HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
              "Connection: close\r\n\r\n").format(status, content_type, len(payload))
    return header.encode("ascii") + payload


def _js_string(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r").replace("</", "<\\/") + "'"


def setup_page_html(state=None):
    """The scan-driven setup form, without config/admin assets."""
    state = state or {}
    status, ssid = state.get("status"), state.get("ssid") or ""
    admin = state.get("admin_password") or ""
    if status == "failure":
        banner = "Couldn't join {}. Check the password and try again.".format(html_escape(ssid or "the network"))
    elif status == "success":
        banner = "Connected to {}.".format(html_escape(ssid or "Wi-Fi"))
    elif status == "form_error":
        banner = "Choose a network and use passwords between 8 and 63 characters."
    else:
        banner = ""
    prefill = "<script>window.__setupPrefill={ssid:%s};</script>" % _js_string(ssid)
    return ("<!doctype html><html><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Pi Calendar Setup</title><style>body{background:#12161c;color:#e8ecf1;font-family:sans-serif;max-width:28rem;margin:2rem auto;padding:0 1rem}button,input,select{min-height:44px;margin:.4rem 0;box-sizing:border-box;width:100%}button{background:#7c6cf6}</style>"
            "<h1>Set Up Wi-Fi</h1><p id=banner aria-live=polite>" + banner + "</p>" + prefill +
            '<form method="POST" action="/connect"><label for="ssid">Network<select id="ssid" name="ssid" required><option value="">Loading networks…</option></select></label><button id="rescan" type="button">Rescan</button><label>Wi-Fi Password<input name="wifi_password" type="password" autocomplete="current-password" minlength="8" maxlength="63" required></label><label>Admin Password<input name="admin_password" type="password" autocomplete="new-password" minlength="8" maxlength="63" value="' + html_escape(admin) + '" required></label><button type="submit">Connect</button></form>'
            "<script>(function(){var p=window.__setupPrefill||{},select=document.getElementById('ssid'),banner=document.getElementById('banner');function scan(){select.innerHTML='<option value=\"\">Loading networks…</option>';fetch('/scan').then(function(r){return r.json()}).then(function(d){select.innerHTML='<option value=\"\">Choose a network</option>';(d.ssids||[]).forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;select.appendChild(o)});select.value=p.ssid||'';if(select.options.length===1)banner.textContent='No networks found. Rescan to try again.'}).catch(function(){select.innerHTML='<option value=\"\">No networks found</option>';banner.textContent='Could not scan networks. Rescan to try again.'})}document.getElementById('rescan').onclick=scan;scan()})();</script></html>")


def _json_string(value):
    out = ['"']
    for char in str(value):
        code = ord(char)
        if char == '"': out.append('\\"')
        elif char == '\\': out.append('\\\\')
        elif char == '\b': out.append('\\b')
        elif char == '\f': out.append('\\f')
        elif char == '\n': out.append('\\n')
        elif char == '\r': out.append('\\r')
        elif char == '\t': out.append('\\t')
        elif code < 32: out.append('\\u%04x' % code)
        else: out.append(char)
    out.append('"')
    return ''.join(out)


def response_setup_page(state=None): return http_response("200 OK", setup_page_html(state))
def response_setup_form_error(): return response_setup_page({"status": "form_error"})
def response_scan_json(ssids): return http_response("200 OK", '{"ssids":[' + ','.join(_json_string(value) for value in ssids) + ']}', "application/json")
def response_busy(): return http_response("503 Service Unavailable", "Busy")
def response_bad_request(): return http_response("400 Bad Request", "Bad Request")
def response_not_found(): return http_response("404 Not Found", "Not Found")
def response_too_large(): return http_response("413 Payload Too Large", "Too Large")
def response_unsupported(): return http_response("405 Method Not Allowed", "Method Not Allowed")
def response_join_failure(ssid, admin_password=""): return response_setup_page({"status": "failure", "ssid": ssid, "admin_password": admin_password})
def response_join_success(ssid):
    # The setup server is at its tightest heap point after KDF completion.
    # Avoid rebuilding the full scan page while the held client is waiting.
    return http_response(
        "200 OK",
        "<!doctype html><meta name=viewport content=width=device-width>"
        "<title>Pi Calendar Connected</title>"
        "<h1>Connected to %s.</h1><p>Reconnect your phone to your home Wi-Fi, "
        "then open the IP shown on the clock.</p>" % html_escape(ssid or "Wi-Fi"),
    )
def response_for_parse_error(error_code): return response_too_large() if error_code == "too_large" else (response_unsupported() if error_code == "unsupported" else response_bad_request())
