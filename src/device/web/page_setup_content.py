"""Small, self-contained server-rendered setup page."""

from src.device.web.http_parse import html_escape

_CSS = "body{background:#12161c;color:#e8ecf1;font:15px sans-serif;max-width:480px;margin:0 auto;padding:20px}label{display:block;margin:16px 0 6px;font-weight:600}input,select,button{box-sizing:border-box;width:100%;min-height:44px;padding:10px;border-radius:10px;border:1px solid #2a323d}input,select{background:#1b212a;color:#e8ecf1}button{margin-top:20px;background:#7c6cf6;color:#0a0f16;font-weight:700}.banner{padding:12px;border-radius:999px;margin:16px 0}.failure{color:#ff5c5c;border:1px solid #ff5c5c}.success{color:#3ddc84;border:1px solid #3ddc84}.rescan{display:block;margin-top:12px;background:none;color:#7c6cf6;text-align:center}"


def setup_page_html(state=None):
    """Render scan results and setup state without browser-side requests."""
    state = state or {}
    status = state.get("status")
    ssid = str(state.get("ssid") or "")
    admin = str(state.get("admin_password") or "")
    ssids = state.get("ssids") or ()
    if not ssids and ssid:
        ssids = (ssid,)
    options = ['<option value="">Choose a network</option>']
    for value in ssids:
        value = str(value)
        selected = ' selected' if value == ssid else ''
        options.append('<option value="{}"{}>{}</option>'.format(html_escape(value), selected, html_escape(value)))
    if not ssids:
        options = ['<option value="">No networks found</option>']
    if status == "connecting":
        banner = '<p class="banner" aria-live="polite">Connecting…</p>'
    elif status == "failure":
        banner = '<p class="banner failure" aria-live="polite">Couldn\'t join {}. Check the password and try again.</p>'.format(html_escape(ssid or "the network"))
    elif status == "success":
        banner = '<p class="banner success" aria-live="polite">Connected to {}.</p>'.format(html_escape(ssid or "Wi-Fi"))
    elif status == "form_error":
        banner = '<p class="banner failure" aria-live="polite">Choose a network and use passwords between 8 and 63 characters.</p>'
    elif state.get("scan_failed"):
        banner = '<p class="banner failure" aria-live="polite">Could not scan networks. Select Rescan networks to try again.</p>'
    else:
        banner = ""
    if state.get("message"):
        banner = '<p class="banner" aria-live="polite">{}</p>'.format(html_escape(state["message"]))
    if not ssids and not banner:
        banner = '<p class="banner" aria-live="polite">No networks found. Select Rescan networks to try again.</p>'
    elif not banner:
        banner = '<p aria-live="polite"></p>'
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Pi Calendar Setup</title><style>' + _CSS + '</style></head><body>'
        '<h1>Set Up Wi-Fi</h1>' + banner + '<form method="POST" action="/connect">'
        '<label for="ssid">Network</label><select id="ssid" name="ssid" required>'
        + ''.join(options) + '</select><a class="rescan" href="/">Rescan networks</a>'
        '<label for="wifi-password">Wi-Fi Password</label>'
        '<input id="wifi-password" name="wifi_password" type="password" autocomplete="current-password" minlength="8" maxlength="63" required value="">'
        '<label for="admin-password">Admin Password</label>'
        '<input id="admin-password" name="admin_password" type="password" autocomplete="new-password" minlength="8" maxlength="63" required value="' + html_escape(admin) + '">'
        '<button type="submit"' + (' disabled' if status in ("connecting", "success") else '') + '>Connect</button></form></body></html>')
