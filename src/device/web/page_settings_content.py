"""Authenticated settings page HTML (pure). Imported lazily by
pages.settings_page_html so a plain admin-site response never pays for this
content's heap footprint.
"""

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
