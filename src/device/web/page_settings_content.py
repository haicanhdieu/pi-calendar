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
    '{0}</section><details{1}>'
    '<summary>Admin Password</summary>'
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


def _alert_rows(settings, editing_alert_id=None):
    alerts = settings.get("alerts", []) if settings else []
    if not alerts:
        return '<p class="empty-state" aria-live="polite">No alerts stored.</p>'
    rows = []
    for alert in alerts:
        time_text = "{:02d}:{:02d}".format(alert["hour"], alert["minute"])
        state = "On" if alert["enabled"] else "Off"
        recurrence = _weekday_text(alert["weekdays"])
        editor = ""
        if alert.get("id") == editing_alert_id:
            from src.device.web.page_alert_editor import alert_editor_html
            editor = alert_editor_html(alert)
        rows.append(
            '<article><strong>{time}</strong>'
            '<span>{recurrence} \u00b7 {state}</span>'
            '<a href="/settings/edit/{id}">Edit</a>{editor}'
            "</article>".format(
                time=time_text,
                id=html_escape(alert["id"]),
                recurrence=html_escape(recurrence),
                state=state,
                editor=editor,
            )
        )
    return "".join(rows)


def settings_page_html(password_changed=False, settings=None, alert_saved=False,
                       alert_error=None, alert_editor=False, editing_alert_id=None,
                       postpone_saved=False, postpone_error=None):
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
    from src.device.web.postpone_route import postpone_section_html
    postpone_section = postpone_section_html(
        settings.get("postpone_delay_minutes", 10), postpone_saved, postpone_error
    )
    alerts = settings.get("alerts", [])
    if len(alerts) >= 10:
        add_control = '<p class="limit-note">Ten-alert limit reached. Delete an alert before adding another.</p>'
    elif alert_editor:
        from src.device.web.page_alert_editor import alert_editor_html
        add_control = alert_editor_html()
    else:
        add_control = '<p><a href="/settings/add">Add alert</a></p>'
    return (
        _PAGE_START + banner + alert_feedback + _alert_rows(settings, editing_alert_id) + add_control
        + _PAGE_END.format(postpone_section, " open" if password_changed else "")
    )
