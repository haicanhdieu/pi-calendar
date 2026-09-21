"""Minimal station-online settings page using native controls."""

from src.device.web.http_parse import html_escape

_CSS_HREF = "https://cdn.jsdelivr.net/npm/water.css@2/out/water.css"


_WEEKDAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"


def _weekday_text(days):
    days = sorted(set(days or ()))
    if not days:
        return "One time"
    if days == list(range(7)):
        return "Every day"
    if days == [0, 1, 2, 3, 4]:
        return "Monday\u2013Friday"
    names = _WEEKDAYS.split("|")
    return ", ".join(names[index] for index in days)


def _alert_rows(settings):
    alerts = settings.get("alerts", []) if settings else []
    if not alerts:
        return '<p class="empty-state" aria-live="polite">No alerts stored.</p>'
    rows = []
    for alert in alerts:
        time_text = "{:02d}:{:02d}".format(alert["hour"], alert["minute"])
        state = "On" if alert["enabled"] else "Off"
        recurrence = _weekday_text(alert["weekdays"])
        rows.append(
            '<article class="alert-row" data-alert-id="{id}">'
            '<strong class="alert-time">{time}</strong>'
            '<span>{recurrence} \u00b7 {state}</span>'
            "</article>".format(
                id=html_escape(alert["id"]),
                time=html_escape(time_text),
                recurrence=html_escape(recurrence),
                state=state,
            )
        )
    return "".join(rows)


def settings_page_html(password_changed=False, settings=None):
    banner = '<p class="banner success" aria-live="polite">Password changed.</p>' if password_changed else ""
    settings = settings or {}
    postpone = settings.get("postpone_delay_minutes", 10)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        + '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + '<link rel="stylesheet" href="' + _CSS_HREF + '">'
        + '<title>Pi Calendar Settings</title></head><body>'
        + '<main><h1>Device Settings</h1>' + banner
        + '<section class="settings-section" aria-labelledby="alerts-heading"><h2 id="alerts-heading">ALERTS</h2>'
        + _alert_rows(settings)
        + '</section>'
        + '<section class="settings-section" aria-labelledby="postpone-heading"><h2 id="postpone-heading">POSTPONE</h2>'
        + '<p>Postpone delay: <span>' + html_escape(str(postpone)) + ' minutes</span></p></section>'
        + '<details' + (' open' if password_changed else '') + '><summary>Admin Password</summary>'
        + '<form method="POST" action="/settings"><label for="new-password">New Password</label>'
        + '<input id="new-password" name="new_password" type="password" autocomplete="new-password" required>'
        + '<button type="submit">Save</button></form></details>'
        + '<details aria-disabled="true"><summary>Color Scheme</summary><label><input type="radio" checked disabled> Forest &amp; Amber</label>'
        + '<p>Only theme available in this version.</p></details></main></body></html>')
