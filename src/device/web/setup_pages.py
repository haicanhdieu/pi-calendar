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
    """The scan-driven two-screen setup flow, without config/admin assets."""
    state = state or {}
    status, ssid = state.get("status"), state.get("ssid") or ""
    admin = state.get("admin_password") or ""
    # The failed Wi-Fi password is deliberately not retained, so retry begins
    # on screen one while the SSID and admin-password prefill remain usable.
    screen1 = "" if status in ("success", "connecting") else " active"
    screen2 = " active" if status in ("success", "connecting") else ""
    if status == "failure":
        banner = "Couldn't join {}. Check the password and try again.".format(html_escape(ssid or "the network"))
    elif status == "success":
        banner = "Connected to {}.".format(html_escape(ssid or "Wi-Fi"))
    else:
        banner = ""
    prefill = "<script>window.__setupPrefill={ssid:%s,admin:%s};</script>" % (_js_string(ssid), _js_string(admin))
    return ("<!doctype html><html><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Pi Calendar Setup</title><style>body{background:#12161c;color:#e8ecf1;font-family:sans-serif;max-width:28rem;margin:2rem auto;padding:0 1rem}.screen{display:none}.screen.active{display:block}button,input,select{min-height:44px;margin:.4rem 0;box-sizing:border-box;width:100%}button{background:#7c6cf6}</style>"
            "<h1>Set Up Wi-Fi</h1><p id=banner aria-live=polite>" + banner + "</p>" + prefill +
            '<section id="screen1" class="screen' + screen1 + '"><label for="ssid">Network<select id="ssid"><option value="">Loading networks…</option></select></label><button id="rescan" type="button">Rescan</button><label>Wi-Fi Password<input id="wifi-password" type="password" autocomplete="current-password"></label><button id="next-btn" type="button">Next</button></section>'
            '<section id="screen2" class="screen' + screen2 + '"><form id="connect-form" method="POST" action="/connect"><label>Admin Password<input id="admin-password" name="admin_password" type="password" autocomplete="new-password" value="' + html_escape(admin) + '"></label><button id="connect-btn" type="submit">Connect</button></form></section>'
            "<script>(function(){var p=window.__setupPrefill||{},ssid=p.ssid||'',select=document.getElementById('ssid'),wifiInput=document.getElementById('wifi-password'),adminInput=document.getElementById('admin-password'),next=document.getElementById('next-btn'),connect=document.getElementById('connect-btn'),s1=document.getElementById('screen1'),s2=document.getElementById('screen2'),banner=document.getElementById('banner');function show(m){banner.textContent=m}function scan(){select.innerHTML='<option value=\"\">Loading networks…</option>';fetch('/scan').then(function(r){return r.json()}).then(function(d){var old=ssid;select.innerHTML='<option value=\"\">Choose a network</option>';(d.ssids||[]).forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;select.appendChild(o)});select.value=old;ssid=select.value;if(!select.options.length||select.options.length===1)show('No networks found. Rescan to try again.')}).catch(function(){select.innerHTML='<option value=\"\">No networks found</option>';ssid='';show('Could not scan networks. Rescan to try again.')})}select.onchange=function(){ssid=select.value};document.getElementById('rescan').onclick=scan;next.onclick=function(){ssid=select.value;var wifi=wifiInput.value;if(!ssid){show('Choose a network first');return}if(!wifi){show('Enter the Wi-Fi password');return}s1.className='screen';s2.className='screen active';adminInput.focus()};document.getElementById('connect-form').onsubmit=function(e){e.preventDefault();ssid=select.value;var wifi=wifiInput.value,admin=adminInput.value;if(!ssid||!wifi||!admin){show('Choose a network and enter both passwords');s1.className='screen active';s2.className='screen';return}show('Connecting…');connect.disabled=true;fetch('/connect',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'ssid='+encodeURIComponent(ssid)+'&wifi_password='+encodeURIComponent(wifi)+'&admin_password='+encodeURIComponent(admin)}).then(function(r){return r.text()}).then(function(t){if(String(t).replace(/^\\s+/,'').charAt(0)==='<'){document.open();document.write(t);document.close();return}throw Error('unexpected response')}).catch(function(){show(\"Couldn't join \"+(ssid||'the network')+'. Check the password and try again.');connect.disabled=false;wifiInput.value='';s1.className='screen active';s2.className='screen'})};scan()})();</script></html>")


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
def response_scan_json(ssids): return http_response("200 OK", '{"ssids":[' + ','.join(_json_string(value) for value in ssids) + ']}', "application/json")
def response_busy(): return http_response("503 Service Unavailable", "Busy")
def response_bad_request(): return http_response("400 Bad Request", "Bad Request")
def response_not_found(): return http_response("404 Not Found", "Not Found")
def response_too_large(): return http_response("413 Payload Too Large", "Too Large")
def response_unsupported(): return http_response("405 Method Not Allowed", "Method Not Allowed")
def response_join_failure(ssid, admin_password=""): return response_setup_page({"status": "failure", "ssid": ssid, "admin_password": admin_password})
def response_join_success(ssid): return response_setup_page({"status": "success", "ssid": ssid})
def response_for_parse_error(error_code): return response_too_large() if error_code == "too_large" else (response_unsupported() if error_code == "unsupported" else response_bad_request())
