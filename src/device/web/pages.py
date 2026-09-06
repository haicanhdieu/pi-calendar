"""Fixed Setup page assets and HTTP response builders (pure)."""

from src.device.web.http_parse import html_escape

# DESIGN.md tokens (dark utility; never green/amber Device palette).
_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#12161c;color:#e8ecf1;font-family:-apple-system,"Segoe UI",Roboto,sans-serif;
padding:20px;max-width:480px;margin:0 auto;min-height:100vh;display:flex;flex-direction:column}
h1{font-size:20px;font-weight:700;margin-bottom:20px}
.section{font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
color:#9aa5b1;margin-bottom:12px}
.ssid-list{display:flex;flex-direction:column;gap:10px;margin-bottom:28px}
.ssid-row{min-height:44px;background:#1b212a;border:1px solid #2a323d;border-radius:14px;
padding:13px 16px;font-size:15px;color:#e8ecf1;text-align:left;width:100%;cursor:pointer}
.ssid-row.selected{border:2px solid #7c6cf6;padding:12px 15px}
.field{margin-bottom:28px}
label{font-size:13px;font-weight:600;display:block;margin-bottom:8px}
.pw{display:flex;align-items:center;min-height:44px;background:#1b212a;border:1px solid #2a323d;
border-radius:10px;padding:12px 15px}
.pw:focus-within{border:2px solid #7c6cf6;padding:11px 14px}
.pw input{border:none;background:transparent;color:#e8ecf1;font-size:15px;width:100%;outline:none;
font-family:inherit}
.toggle{font-size:13px;font-weight:600;color:#7c6cf6;background:none;border:none;
flex-shrink:0;padding-left:12px;min-height:44px;cursor:pointer}
.spacer{flex:1}
.btn{width:100%;min-height:44px;border:none;border-radius:10px;background:#7c6cf6;color:#0a0f16;
font-size:15px;font-weight:700;font-family:inherit;padding:13px 0;cursor:pointer}
.btn:disabled{background:#2a323d;color:#9aa5b1;opacity:.7;cursor:default}
.empty{background:#1b212a;border:1px solid #2a323d;border-radius:14px;padding:20px 16px;
text-align:center;margin-bottom:20px}
.empty p{font-size:15px;color:#9aa5b1;line-height:1.5;margin-bottom:14px}
.rescan{font-size:15px;font-weight:600;color:#7c6cf6;background:none;border:none;
min-height:44px;cursor:pointer}
.banner{min-height:44px;border-radius:999px;padding:11px 16px;font-size:14px;font-weight:600;
margin-bottom:20px;display:flex;align-items:center}
.banner.connecting{background:#1b212a;color:#9aa5b1;border:1px solid #2a323d}
.banner.failure{background:#1b212a;color:#ff5c5c;border:1px solid #ff5c5c}
.banner.success{background:#1b212a;color:#3ddc84;border:1px solid #3ddc84}
.screen{display:none;flex-direction:column;flex:1}
.screen.active{display:flex}
.hidden{display:none!important}
"""

_JS = """
(function(){
var prefill=window.__setupPrefill||{};
var ssid=prefill.ssid||null,wifiPw="",adminPw=prefill.admin||"";
var listEl=document.getElementById("ssid-list");
var emptyEl=document.getElementById("empty");
var nextBtn=document.getElementById("next-btn");
var connectBtn=document.getElementById("connect-btn");
var wifiInput=document.getElementById("wifi-password");
var adminInput=document.getElementById("admin-password");
var wifiBlock=document.getElementById("wifi-block");
var banner=document.getElementById("banner");
var s1=document.getElementById("screen1");
var s2=document.getElementById("screen2");

function showBanner(kind,text){
  banner.className="banner "+kind;
  banner.setAttribute("aria-live","polite");
  banner.textContent=text;
  banner.classList.remove("hidden");
}
function hideBanner(){banner.classList.add("hidden");banner.textContent="";}

function setNext(){
  nextBtn.disabled=!(ssid && wifiInput.value.length>0);
}
function selectSsid(name,btn){
  ssid=name;
  var rows=listEl.querySelectorAll(".ssid-row");
  for(var i=0;i<rows.length;i++){rows[i].classList.remove("selected");}
  if(btn) btn.classList.add("selected");
  wifiBlock.classList.remove("hidden");
  setNext();
}
function renderSsids(items){
  listEl.innerHTML="";
  if(!items || !items.length){
    emptyEl.classList.remove("hidden");
    listEl.classList.add("hidden");
    wifiBlock.classList.add("hidden");
    if(!prefill.ssid){ssid=null;}
    nextBtn.disabled=true;
    return;
  }
  emptyEl.classList.add("hidden");
  listEl.classList.remove("hidden");
  for(var i=0;i<items.length;i++){
    (function(name){
      var b=document.createElement("button");
      b.type="button";
      b.className="ssid-row";
      b.textContent=name;
      b.addEventListener("click",function(){selectSsid(name,b);});
      listEl.appendChild(b);
    })(items[i]);
  }
}
function applyPrefillSelection(){
  if(!prefill.ssid) return;
  var rows=listEl.querySelectorAll(".ssid-row");
  for(var i=0;i<rows.length;i++){
    if(rows[i].textContent===prefill.ssid){selectSsid(prefill.ssid,rows[i]);break;}
  }
  if(adminInput && prefill.admin) adminInput.value=prefill.admin;
  wifiInput.value="";
  wifiPw="";
  if(connectBtn) connectBtn.disabled=!(adminInput && adminInput.value.length>0);
}
function scan(){
  return fetch("/scan").then(function(r){return r.json();}).then(function(data){
    renderSsids(data && data.ssids ? data.ssids : []);
    applyPrefillSelection();
  }).catch(function(){renderSsids([]);applyPrefillSelection();});
}
document.getElementById("rescan").addEventListener("click",function(e){
  e.preventDefault();scan();
});
wifiInput.addEventListener("input",setNext);
adminInput.addEventListener("input",function(){
  connectBtn.disabled=adminInput.value.length===0;
});
document.getElementById("toggle-wifi").addEventListener("click",function(){
  var t=wifiInput.type==="password";
  wifiInput.type=t?"text":"password";
  this.textContent=t?"Hide":"Show";
  this.setAttribute("aria-label",t?"Hide Wi-Fi password":"Show Wi-Fi password");
});
document.getElementById("toggle-admin").addEventListener("click",function(){
  var t=adminInput.type==="password";
  adminInput.type=t?"text":"password";
  this.textContent=t?"Hide":"Show";
  this.setAttribute("aria-label",t?"Hide Admin password":"Show Admin password");
});
nextBtn.addEventListener("click",function(){
  if(nextBtn.disabled) return;
  wifiPw=wifiInput.value;
  s1.classList.remove("active");
  s2.classList.add("active");
  document.getElementById("title").textContent="Set Admin Password";
  hideBanner();
});
document.getElementById("connect-form").addEventListener("submit",function(e){
  e.preventDefault();
  if(connectBtn.disabled) return;
  adminPw=adminInput.value;
  showBanner("connecting","Connecting…");
  connectBtn.disabled=true;
  var body="ssid="+encodeURIComponent(ssid)
    +"&wifi_password="+encodeURIComponent(wifiPw)
    +"&admin_password="+encodeURIComponent(adminPw);
  fetch("/connect",{
    method:"POST",
    headers:{"Content-Type":"application/x-www-form-urlencoded"},
    body:body
  }).then(function(r){return r.text();}).then(function(text){
    var trimmed=String(text||"").replace(/^\\s+/,"");
    if(trimmed.charAt(0)==="<"){
      document.open();document.write(text);document.close();
      return;
    }
    showBanner("failure","Couldn't join "+(ssid||"the network")+". Check the password and try again.");
    wifiInput.value="";
    wifiPw="";
    connectBtn.disabled=false;
  }).catch(function(){
    showBanner("failure","Couldn't join "+(ssid||"the network")+". Check the password and try again.");
    wifiInput.value="";
    wifiPw="";
    connectBtn.disabled=false;
  });
});
if(prefill.status==="failure"){
  wifiInput.value="";
  wifiPw="";
  if(prefill.admin && adminInput) adminInput.value=prefill.admin;
  if(connectBtn) connectBtn.disabled=!(adminInput && adminInput.value.length>0);
}
scan();
})();
"""


def setup_page_html(state=None):
    """
    Build the Setup two-screen page.

    ``state`` may include:
      - status: ``None`` | ``connecting`` | ``failure`` | ``success``
      - ssid, admin_password (retained on failure; wifi password cleared)
      - message override
    """
    state = state or {}
    status = state.get("status")
    ssid = state.get("ssid") or ""
    admin = state.get("admin_password") or ""
    esc_ssid = html_escape(ssid)
    esc_admin = html_escape(admin)

    banner_html = '<div id="banner" class="banner hidden" aria-live="polite"></div>'
    screen1_active = "active"
    screen2_active = ""
    title = "Set Up Wi-Fi"
    if status == "connecting":
        banner_html = (
            '<div id="banner" class="banner connecting" aria-live="polite">'
            "Connecting…</div>"
        )
        screen1_active = ""
        screen2_active = "active"
        title = "Set Admin Password"
    elif status == "failure":
        msg = state.get("message") or (
            "Couldn't join {ssid}. Check the password and try again.".format(
                ssid=esc_ssid or "the network"
            )
        )
        banner_html = (
            '<div id="banner" class="banner failure" aria-live="polite">'
            + msg
            + "</div>"
        )
        screen1_active = ""
        screen2_active = "active"
        title = "Set Admin Password"
    elif status == "success":
        msg = state.get("message") or (
            "Connected to {ssid}.".format(ssid=esc_ssid or "Wi-Fi")
        )
        banner_html = (
            '<div id="banner" class="banner success" aria-live="polite">'
            + msg
            + "</div>"
        )
        screen1_active = ""
        screen2_active = "active"
        title = "Connected!"

    prefill_boot = ""
    if status == "failure" and (ssid or admin):
        prefill_boot = (
            "<script>window.__setupPrefill={{ssid:{ssid_js},admin:{admin_js},"
            "status:'failure'}};</script>"
        ).format(ssid_js=_js_string(ssid), admin_js=_js_string(admin))

    return (
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Pi Calendar Setup</title>"
        "<style>" + _CSS + "</style></head><body>"
        + prefill_boot
        + "<h1 id=\"title\">" + html_escape(title) + "</h1>"
        + banner_html
        + '<div id="screen1" class="screen '
        + screen1_active
        + '">'
        '<div class="section">Network</div>'
        '<div id="empty" class="empty hidden">'
        "<p>No networks found — move closer to your router and reload</p>"
        '<button type="button" class="rescan" id="rescan">Rescan</button>'
        "</div>"
        '<div id="ssid-list" class="ssid-list"></div>'
        '<div id="wifi-block" class="field hidden">'
        '<label for="wifi-password">Wi-Fi Password</label>'
        '<div class="pw">'
        '<input id="wifi-password" name="wifi_password" type="password" '
        'autocomplete="current-password" value="">'
        '<button type="button" class="toggle" id="toggle-wifi" '
        'aria-label="Show Wi-Fi password">Show</button>'
        "</div></div>"
        '<div class="spacer"></div>'
        '<button type="button" class="btn" id="next-btn" disabled>Next</button>'
        "</div>"
        '<div id="screen2" class="screen '
        + screen2_active
        + '">'
        '<form id="connect-form" method="POST" action="/connect">'
        '<div class="field">'
        '<div class="section">Admin Password</div>'
        '<label for="admin-password" class="hidden">Admin Password</label>'
        '<div class="pw">'
        '<input id="admin-password" name="admin_password" type="password" '
        'autocomplete="new-password" value="' + esc_admin + '">'
        '<button type="button" class="toggle" id="toggle-admin" '
        'aria-label="Show Admin password">Show</button>'
        "</div></div>"
        '<div class="spacer"></div>'
        '<button type="submit" class="btn" id="connect-btn"'
        + (" disabled" if status == "connecting" or status == "success" else "")
        + ">Connect</button>"
        "</form></div>"
        "<script>" + _JS + "</script>"
        + "</body></html>"
    )


def _js_string(value):
    """JSON-ish string literal for safe embedding in JS (no secrets logged)."""
    text = str(value)
    escaped = (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("</", "<\\/")
    )
    return "'" + escaped + "'"


_CONFIG_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#12161c;color:#e8ecf1;font-family:-apple-system,"Segoe UI",Roboto,sans-serif;
padding:20px;max-width:480px;margin:0 auto;min-height:100vh}
h1{font-size:20px;font-weight:700;margin-bottom:28px}
.login-wrap{display:flex;flex-direction:column;justify-content:center;min-height:70vh}
.login-card{display:flex;flex-direction:column;gap:16px}
.login-card h1{text-align:center;margin-bottom:12px}
.field{margin-bottom:0}
label{font-size:13px;font-weight:600;display:block;margin-bottom:8px}
.pw{display:flex;align-items:center;min-height:44px;background:#1b212a;border:1px solid #2a323d;
border-radius:10px;padding:12px 15px}
.pw:focus-within{border:2px solid #7c6cf6;padding:11px 14px}
.pw.error{border:2px solid #ff5c5c;padding:11px 14px}
.pw input{border:none;background:transparent;color:#e8ecf1;font-size:15px;width:100%;outline:none;
font-family:inherit}
.toggle{font-size:13px;font-weight:600;color:#7c6cf6;background:none;border:none;
flex-shrink:0;padding-left:12px;min-height:44px;cursor:pointer}
.btn{width:100%;min-height:44px;border:none;border-radius:10px;background:#7c6cf6;color:#0a0f16;
font-size:15px;font-weight:700;font-family:inherit;padding:13px 0;cursor:pointer;margin-top:4px}
.banner{min-height:44px;border-radius:999px;padding:11px 16px;font-size:14px;font-weight:600;
display:flex;align-items:center;justify-content:center;background:#1b212a;color:#ff5c5c;
border:1px solid #ff5c5c;text-align:center;margin-bottom:20px}
.banner.success{color:#3ddc84;border:1px solid #3ddc84}
.settings-list{display:flex;flex-direction:column;gap:10px}
.settings-row{background:#1b212a;border:1px solid #2a323d;border-radius:14px;overflow:hidden}
.settings-row-head{min-height:44px;padding:14px 16px;display:flex;align-items:center;
justify-content:space-between;font-size:15px;font-weight:600;color:#e8ecf1;width:100%;
background:none;border:none;font-family:inherit;cursor:pointer;text-align:left}
.chevron{color:#9aa5b1;font-size:13px}
.settings-row-body{padding:4px 16px 20px;border-top:1px solid #2a323d;display:none}
.settings-row.open .settings-row-body{display:block}
.settings-row.open .chevron{transform:rotate(0deg)}
.theme-option{margin-top:12px;min-height:44px;display:flex;align-items:center;
justify-content:space-between;background:#12161c;border:1px solid #2a323d;border-radius:10px;
padding:12px 15px;opacity:.6}
.theme-option-label{font-size:15px;color:#9aa5b1}
.theme-check{width:20px;height:20px;border-radius:50%;background:#2a323d;color:#9aa5b1;
font-size:12px;font-weight:700;display:inline-flex;align-items:center;justify-content:center}
.theme-note{font-size:13px;color:#9aa5b1;margin-top:10px;line-height:1.5}
.settings-row .pw{background:#12161c;margin-top:0}
.settings-row .input-label{margin:16px 0 8px}
"""

_LOGIN_JS = """
(function(){
var input=document.getElementById("admin-password");
var toggle=document.getElementById("toggle-admin");
if(toggle&&input){
  toggle.addEventListener("click",function(){
    var show=input.type==="password";
    input.type=show?"text":"password";
    toggle.textContent=show?"Hide":"Show";
    toggle.setAttribute("aria-label",show?"Hide Admin password":"Show Admin password");
  });
}
})();
"""

_SETTINGS_JS = """
(function(){
var rows=document.querySelectorAll(".settings-row");
for(var i=0;i<rows.length;i++){
  (function(row){
    var head=row.querySelector(".settings-row-head");
    if(!head) return;
    head.addEventListener("click",function(){
      row.classList.toggle("open");
      var open=row.classList.contains("open");
      head.setAttribute("aria-expanded",open?"true":"false");
    });
  })(rows[i]);
}
var input=document.getElementById("new-password");
var toggle=document.getElementById("toggle-new");
if(toggle&&input){
  toggle.addEventListener("click",function(){
    var show=input.type==="password";
    input.type=show?"text":"password";
    toggle.textContent=show?"Hide":"Show";
    toggle.setAttribute("aria-label",show?"Hide new password":"Show new password");
  });
}
})();
"""


def login_page_html(incorrect=False):
    """Password-only Config login form (no username)."""
    banner = ""
    pw_class = "pw"
    if incorrect:
        banner = (
            '<div class="banner" aria-live="polite">Incorrect password</div>'
        )
        pw_class = "pw error"
    return (
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Pi Calendar Log In</title>"
        "<style>" + _CONFIG_CSS + "</style></head><body>"
        '<div class="login-wrap"><div class="login-card">'
        "<h1>Log In</h1>"
        + banner
        + '<form method="POST" action="/login">'
        '<div class="field">'
        '<label for="admin-password">Admin Password</label>'
        '<div class="' + pw_class + '">'
        '<input id="admin-password" name="password" type="password" '
        'autocomplete="current-password" value="">'
        '<button type="button" class="toggle" id="toggle-admin" '
        'aria-label="Show Admin password">Show</button>'
        "</div></div>"
        '<button type="submit" class="btn">Log In</button>'
        "</form></div></div>"
        "<script>" + _LOGIN_JS + "</script>"
        "</body></html>"
    )


def settings_page_html(password_changed=False):
    """Authenticated mobile flat settings shell (password change + theme stub)."""
    banner = ""
    row_class = "settings-row"
    aria_expanded = "false"
    if password_changed:
        banner = (
            '<div class="banner success" aria-live="polite">'
            "Password changed.</div>"
        )
        row_class = "settings-row open"
        aria_expanded = "true"
    return (
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Pi Calendar Settings</title>"
        "<style>" + _CONFIG_CSS + "</style></head><body>"
        "<h1>Device Settings</h1>"
        + banner
        + '<div class="settings-list">'
        '<div class="' + row_class + '" id="row-password">'
        '<button type="button" class="settings-row-head" aria-expanded="'
        + aria_expanded
        + '" aria-controls="body-password">'
        "<span>Admin Password</span><span class=\"chevron\">▾</span></button>"
        '<div class="settings-row-body" id="body-password">'
        '<form method="POST" action="/settings">'
        '<label class="input-label" for="new-password">New Password</label>'
        '<div class="pw">'
        '<input id="new-password" name="new_password" type="password" '
        'autocomplete="new-password" value="">'
        '<button type="button" class="toggle" id="toggle-new" '
        'aria-label="Show new password">Show</button>'
        "</div>"
        '<button type="submit" class="btn" id="save-password">Save</button>'
        "</form>"
        "</div></div>"
        '<div class="settings-row" id="row-theme">'
        '<button type="button" class="settings-row-head" aria-expanded="false" '
        'aria-controls="body-theme">'
        "<span>Color Scheme</span><span class=\"chevron\">▾</span></button>"
        '<div class="settings-row-body" id="body-theme">'
        '<div class="theme-option" aria-disabled="true">'
        '<span class="theme-option-label">Forest &amp; Amber</span>'
        '<span class="theme-check">✓</span></div>'
        '<div class="theme-note">Only theme available in this version.</div>'
        "</div></div></div>"
        "<script>" + _SETTINGS_JS + "</script>"
        "</body></html>"
    )


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
