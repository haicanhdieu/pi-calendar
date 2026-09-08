"""HTTP response builders (pure).

The three page-HTML builders (setup/login/settings) each live in their own
``page_*_content`` module and are imported lazily inside the wrapper that
needs them. Importing this module must stay cheap: the CSS/JS/HTML string
constants for a page a caller never renders must never enter memory, since a
single admin request otherwise forces the whole combined page set into RAM
at once (measured ~50KB resident just from importing one merged module).
"""

def setup_page_html(state=None):
    from src.device.web.page_setup_content import setup_page_html as _impl

    return _impl(state)


def login_page_html(incorrect=False):
    from src.device.web.page_login_content import login_page_html as _impl

    return _impl(incorrect=incorrect)


def settings_page_html(password_changed=False):
    from src.device.web.page_settings_content import settings_page_html as _impl

    return _impl(password_changed=password_changed)


def http_response(
    status_code,
    reason,
    body,
    content_type="text/html; charset=utf-8",
    location=None,
    set_cookie=None,
):
    """Build a fixed HTTP/1.0 response bytes (Connection: close)."""
    if isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = body or b""
    extra = ""
    if location is not None:
        extra += "Location: {loc}\r\n".format(loc=location)
    if set_cookie is not None:
        if isinstance(set_cookie, (list, tuple)):
            for cookie in set_cookie:
                extra += "Set-Cookie: {c}\r\n".format(c=cookie)
        else:
            extra += "Set-Cookie: {c}\r\n".format(c=set_cookie)
    header = (
        "HTTP/1.0 {code} {reason}\r\n"
        "Content-Type: {ctype}\r\n"
        "Content-Length: {length}\r\n"
        "Connection: close\r\n"
        "{extra}"
        "\r\n"
    ).format(
        code=int(status_code),
        reason=reason,
        ctype=content_type,
        length=len(body_bytes),
        extra=extra,
    )
    return header.encode("ascii") + body_bytes


def session_cookie_value(session_id, clear=False):
    """Build the ``Set-Cookie`` attribute string for the Config session."""
    from src import config

    name = config.SESSION_COOKIE_NAME
    if clear:
        return "{name}=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/".format(
            name=name
        )
    return "{name}={value}; HttpOnly; SameSite=Strict; Path=/".format(
        name=name, value=session_id
    )


def response_setup_page(state=None):
    return http_response(200, "OK", setup_page_html(state))


def response_scan_json(ssids):
    # Minimal JSON array payload: {"ssids":["a","b"]}
    parts = []
    for ssid in ssids:
        safe = (
            str(ssid)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        parts.append('"' + safe + '"')
    body = '{"ssids":[' + ",".join(parts) + "]}"
    return http_response(200, "OK", body, "application/json")


def response_busy():
    return http_response(503, "Busy", "Busy")


def response_bad_request():
    return http_response(400, "Bad Request", "Bad Request")


def response_not_found():
    return http_response(404, "Not Found", "Not Found")


def response_too_large():
    return http_response(413, "Payload Too Large", "Payload Too Large")


def response_unsupported():
    return http_response(405, "Method Not Allowed", "Method Not Allowed")


def response_redirect_login(clear_cookie=False):
    cookie = session_cookie_value("", clear=True) if clear_cookie else None
    return http_response(
        302, "Found", "", location="/login", set_cookie=cookie
    )


def response_login_page(incorrect=False):
    return http_response(200, "OK", login_page_html(incorrect=incorrect))


def response_settings_page(password_changed=False):
    return http_response(
        200, "OK", settings_page_html(password_changed=password_changed)
    )


def response_login_success(session_id):
    return http_response(
        302,
        "Found",
        "",
        location="/settings",
        set_cookie=session_cookie_value(session_id),
    )


def response_join_failure(ssid, admin_password=""):
    return response_setup_page(
        {
            "status": "failure",
            "ssid": ssid,
            "admin_password": admin_password,
        }
    )


def response_join_success(ssid):
    return response_setup_page({"status": "success", "ssid": ssid})


def response_for_parse_error(error_code):
    if error_code == "too_large":
        return response_too_large()
    if error_code == "unsupported":
        return response_unsupported()
    return response_bad_request()
