"""Lazy inline alert editor."""

from src.device.web.http_parse import html_escape

_DAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"

_START = (
    '<details open><summary>Add alert</summary><form method=POST action=/settings>'
    '<input name="alert_action" value=add type=hidden><label>Time '
    '<input name="alert_time" type=time required></label>'
    '<label><input name="alert_enabled" type=checkbox checked>Enabled</label>'
    '<fieldset><legend>Repeat on</legend>'
)
_END = (
    '</fieldset><button type="submit">Save</button>'
    '<a href="/settings" role="button">Cancel</a>{delete_control}'
    '</form></details>'
)


def alert_editor_html(alert=None):
    editing = alert is not None
    action = "edit" if editing else "add"
    title = "Edit alert" if editing else "Add alert"
    time_value = "" if alert is None else "{:02d}:{:02d}".format(alert["hour"], alert["minute"])
    enabled = " checked" if alert is None or alert["enabled"] else ""
    alert_id = "" if alert is None else (
        '<input name="alert_id" value="{}" type="hidden">'.format(html_escape(alert["id"]))
    )
    start = _START.replace("Add alert", title).replace('value=add', 'value={}'.format(action))
    start = start.replace('type=time required>', 'type=time required value="{}">'.format(html_escape(time_value)))
    start = start.replace(' type=checkbox checked>Enabled', ' type=checkbox{}>Enabled'.format(enabled))
    start = start.replace('<form method=POST action=/settings>', '<form method="POST" action="/settings">' + alert_id)
    selected = set(alert.get("weekdays", [])) if editing else set()
    fields = []
    for index, name in enumerate(_DAYS.split("|")):
        checked = " checked" if index in selected else ""
        fields.append('<label><input name=weekday_{} type=checkbox{}>{}</label>'.format(index, checked, name))
    delete_control = (
        '<button class="danger" type="submit" name="alert_action" value="delete" '
        'onclick="return confirm(\'Delete this alert?\')">Delete</button>'
        if editing else '<button type="button" disabled>Delete</button>'
    )
    return start + "".join(fields) + _END.format(delete_control=delete_control)
