"""Minimal station-online login page."""

_CSS_HREF = "https://cdn.jsdelivr.net/npm/water.css@2/out/water.css"


def login_page_html(incorrect=False):
    banner = '<p aria-live="polite">Incorrect password</p>' if incorrect else ""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="stylesheet" href="' + _CSS_HREF + '"><title>Pi Calendar Log In</title></head><body>'
        '<main><h1>Log In</h1>' + banner + '<form method="POST" action="/login">'
        '<label for="admin-password">Admin Password</label><input id="admin-password" name="password" type="password" autocomplete="current-password" required>'
        '<button type="submit">Log In</button></form></main></body></html>')
