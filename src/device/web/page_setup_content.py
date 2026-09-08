"""Setup two-screen page HTML (pure). Imported lazily by pages.setup_page_html
so a plain admin-site response never pays for this content's heap footprint.
"""

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
