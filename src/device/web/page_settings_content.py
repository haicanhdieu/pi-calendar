"""Minimal station-online settings page using native controls."""

from src.device.web.http_parse import html_escape

_WEEKDAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"

_PAGE_START = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/water.css@2/out/water.css">'
    '</head><body><main><h1>Device Settings</h1>'
    '<section><h2>ALERTS</h2>'
)
_PAGE_END = (
    '</section><section><h2>POSTPONE</h2><p>Postpone delay: <span>'
    '</span></p></section><details{password_open}><summary>Admin Password</summary>'
    '<form method="POST" action="/settings"><label>New Password</label>'
    '<input name="new_password"><button>Save</button></form></details>'
    '<details aria-disabled="true"><summary>Color Scheme</summary>'
    '<input disabled> Forest &amp; Amber</details></main></body></html>'
)


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
            '<article><strong>{time}</strong>'
            '<span>{recurrence} \u00b7 {state}</span>'
            "</article>".format(
                time=time_text,
                recurrence=html_escape(recurrence),
                state=state,
            )
        )
    return "".join(rows)


def settings_page_html(password_changed=False, settings=None, alert_saved=False,
                       alert_error=None, alert_editor=False):
    banner = '<p class="banner success" aria-live="polite">Password changed.</p>' if password_changed else ""
    alert_feedback = (
        '<p class="banner success" aria-live="polite">Alert saved.</p>'
        if alert_saved else ""
    )
    if alert_error:
        alert_feedback += '<p class="banner danger" role="alert">{}</p>'.format(
            html_escape(alert_error)
        )
    settings = settings or {}
    postpone = settings.get("postpone_delay_minutes", 10)
    alerts = settings.get("alerts", [])
    add_control = (
        '<p class="limit-note">Ten-alert limit reached. Delete an alert before adding another.</p>'
        if len(alerts) >= 10 else (
            __import__("src.device.web.page_alert_editor", fromlist=["alert_editor_html"])
            .alert_editor_html() if alert_editor else '<p><a href="/settings/add">Add alert</a></p>'
        )
    )
    return (
        _PAGE_START + banner + alert_feedback + _alert_rows(settings) + add_control
        + _PAGE_END.format(
            password_open=" open" if password_changed else "",
        ).replace("</span>", html_escape(str(postpone)) + " minutes</span>", 1)
    )
