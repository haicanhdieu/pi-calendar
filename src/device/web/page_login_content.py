"""Config login page HTML (pure). Imported lazily by pages.login_page_html
so a plain admin-site response never pays for this content's heap footprint.
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
