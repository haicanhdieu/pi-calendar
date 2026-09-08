"""Minimal station-online settings page using native controls."""

_CSS_HREF = "https://cdn.jsdelivr.net/npm/water.css@2/out/water.css"


def settings_page_html(password_changed=False):
    banner = '<p class="banner success" aria-live="polite">Password changed.</p>' if password_changed else ""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        + '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + '<link rel="stylesheet" href="' + _CSS_HREF + '"><title>Pi Calendar Settings</title></head><body>'
        + '<main><h1>Device Settings</h1>' + banner
        + '<details' + (' open' if password_changed else '') + '><summary>Admin Password</summary>'
        + '<form method="POST" action="/settings"><label for="new-password">New Password</label>'
        + '<input id="new-password" name="new_password" type="password" autocomplete="new-password" required>'
        + '<button type="submit">Save</button></form></details>'
        + '<details aria-disabled="true"><summary>Color Scheme</summary><label><input type="radio" checked disabled> Forest &amp; Amber</label>'
        + '<p>Only theme available in this version.</p></details></main></body></html>')
